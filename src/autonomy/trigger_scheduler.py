"""
Autonomous Trigger Scheduler & Lifecycle Daemon
Location: src/autonomy/trigger_scheduler.py

Manages the autonomous evaluation, concurrency control, policy gating,
and execution dispatch of proactive system, scheduled, and condition triggers.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any
import uuid

from .models import ConcurrencyPolicy, EventProvenance, Trigger, TriggerState, TriggerType
from .trigger_registry import TriggerRegistry

from brain.execution_coordinator import ExecutionCoordinator
from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction

logger = logging.getLogger(__name__)


class TriggerScheduler:
    """
    Autonomous Trigger Scheduler Daemon.
    Evaluates scheduled and event-driven triggers registered in TriggerRegistry.
    """

    def __init__(
        self,
        registry: TriggerRegistry | None = None,
        coordinator: Any | None = None,
        policy: ExecutionPolicy | None = None,
        poll_interval_seconds: float = 1.0,
        state_store: Any | None = None,
        audit_logger: Any | None = None,
        orchestrator: Any | None = None,
    ):
        self.registry = registry or TriggerRegistry()
        self.coordinator = coordinator
        self.policy = policy
        self.poll_interval_seconds = poll_interval_seconds
        self.state_store = state_store
        self.audit_logger = audit_logger
        self.orchestrator = orchestrator

        self._is_running = False
        self._scheduler_task: asyncio.Task[None] | None = None
        self._active_events: set[str] = set()
        self._running_tasks: set[asyncio.Task[None]] = set()

    @property
    def is_running(self) -> bool:
        """Returns whether the scheduler daemon is active."""
        return self._is_running

    # Compatibility property for legacy callers
    @property
    def _running(self) -> bool:
        return self._is_running

    async def start(self) -> None:
        """Start the background trigger scheduler evaluation loop."""
        if self._is_running:
            return

        self._is_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("[TriggerScheduler] Daemon started.")

    async def stop(self) -> None:
        """Stop the background trigger scheduler evaluation loop."""
        self._is_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
        logger.info("[TriggerScheduler] Daemon stopped.")

    async def emit_event(self, event_type: str, payload: dict[str, Any] | None = None) -> int:
        """
        Emit a system event. Finds matching triggers in the registry and dispatches them.
        Returns the number of matching triggers fired.
        """
        payload = payload or {}
        matched_count = 0
        triggers = self.registry.list_triggers(enabled_only=True)

        for trigger in triggers:
            if trigger.trigger_type == TriggerType.SYSTEM_EVENT:
                if not trigger.event_pattern or trigger.event_pattern == event_type or trigger.event_pattern in event_type:
                    fired = await self.fire_trigger(trigger, event_data=payload)
                    if fired:
                        matched_count += 1

        return matched_count

    async def fire_trigger(self, trigger: Trigger, event_data: dict[str, Any] | None = None) -> bool:
        """
        Fires a trigger, updating its state and evaluating actions against policy.
        """
        if not trigger.enabled:
            logger.info(f"[TriggerScheduler] Trigger '{trigger.trigger_id}' is disabled — skipping.")
            return False

        if trigger.dedup_key:
            if trigger.dedup_key in self._active_events:
                policy = trigger.concurrency_policy
                if policy == ConcurrencyPolicy.COALESCE:
                    logger.info(f"[TriggerScheduler] Coalescing duplicate active trigger: '{trigger.trigger_id}'")
                    return False
                elif policy == ConcurrencyPolicy.REJECT:
                    logger.warning(f"[TriggerScheduler] Rejecting duplicate active trigger: '{trigger.trigger_id}'")
                    return False
            self._active_events.add(trigger.dedup_key)

        provenance = EventProvenance(
            trigger_id=trigger.trigger_id,
            dedup_key=trigger.dedup_key,
            trigger_type=trigger.trigger_type.value,
            fired_at=datetime.now().isoformat(),
        )

        task = asyncio.create_task(self._execute_trigger_task(trigger, provenance))
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)
        return True

    async def _execute_trigger_task(self, trigger: Trigger, provenance: EventProvenance) -> None:
        """Worker task executing policy evaluation and coordinator dispatch for a fired trigger."""
        try:
            self.registry.update_state(trigger.trigger_id, TriggerState.RUNNING, provenance=provenance)
            exec_map = dict(trigger.execution_map or {})
            exec_map["goal"] = f"[Trigger: {trigger.trigger_type} | Event: {provenance.event_id}] {trigger.action_goal}"

            policy = self.policy or ExecutionPolicy.get_instance()
            steps = exec_map.get("steps", [])

            # M26 — Goal-based Orchestration Path for Autonomous Triggers
            if not steps and trigger.action_goal:
                try:
                    from core.orchestration.master_orchestrator import MasterOrchestrator
                    from core.orchestration.request_source import RequestSource
                    from desktop.native.security.audit_logger import SecurityAuditLogger
                    from personal_os.state_store import PersonalOSStateStore
                except (ImportError, ModuleNotFoundError):
                    from core.orchestration.master_orchestrator import MasterOrchestrator
                    from core.orchestration.request_source import RequestSource
                    from desktop.native.security.audit_logger import SecurityAuditLogger
                    from personal_os.state_store import PersonalOSStateStore

                # 1. Audit ledger logging for autonomous goal dispatch (FAIL-CLOSED)
                try:
                    audit_logger = self.audit_logger or SecurityAuditLogger.get_instance()
                    audit_logger.log_event(
                        event_type="AUTONOMOUS_GOAL_DISPATCH",
                        action_type="trigger_goal_fired",
                        target=trigger.trigger_id,
                        status="DISPATCHED",
                        details={
                            "request_source": RequestSource.TRIGGER_AUTONOMOUS.value,
                            "goal_text": trigger.action_goal[:200],
                            "trigger_name": getattr(trigger, "name", trigger.trigger_id),
                            "fired_at": provenance.fired_at,
                        },
                    )
                except Exception as audit_exc:
                    logger.error(
                        f"[TriggerScheduler] Audit log failure for trigger '{trigger.trigger_id}' — "
                        f"HALTING dispatch (fail-closed): {audit_exc}"
                    )
                    provenance.result_status = "BLOCKED"
                    self.registry.update_state(trigger.trigger_id, TriggerState.BLOCKED, provenance=provenance)
                    return

                # 2. Get injected or singleton MasterOrchestrator
                orch = self.orchestrator or MasterOrchestrator.get_instance()
                res = await orch.process_request_async(
                    goal_text=trigger.action_goal,
                    source=RequestSource.TRIGGER_AUTONOMOUS,
                    parameters={"trigger_id": trigger.trigger_id, "fired_at": provenance.fired_at},
                )

                # 3. Persist run summary in PersonalOSStateStore
                try:
                    p_store = self.state_store or PersonalOSStateStore.get_instance()
                    obs_summary = " ".join(res.observations or [])[:200] if res.observations else ("Success" if res.success else "Failed")
                    p_store.update_trigger_run(
                        trigger_id=trigger.trigger_id,
                        fired_at=provenance.fired_at,
                        result_summary=obs_summary,
                    )
                except Exception as p_exc:
                    logger.warning(f"[TriggerScheduler] StateStore update warning for '{trigger.trigger_id}': {p_exc}")

                if res.success:
                    provenance.result_status = "VERIFIED"
                    self.registry.update_state(trigger.trigger_id, TriggerState.VERIFIED, provenance=provenance)
                else:
                    provenance.result_status = "FAILED"
                    self.registry.update_state(trigger.trigger_id, TriggerState.FAILED, provenance=provenance)
                return

            from core.capabilities.capability_registry import CapabilityRegistry
            from desktop.native.security.approval_authority import CryptographicApprovalAuthority

            cap_reg = CapabilityRegistry.get_instance()
            auth = CryptographicApprovalAuthority.get_instance()

            for step in steps:
                engine = step.get("engine", "desktop")
                action = step.get("action", "")
                params = step.get("parameters", {})

                # 1. Verify capability exists and is live in CapabilityRegistry
                cap_desc = cap_reg.get(action)
                if cap_desc is None:
                    provenance.result_status = "BLOCKED"
                    self.registry.update_state(trigger.trigger_id, TriggerState.BLOCKED, provenance=provenance)
                    logger.warning(
                        f"[TriggerScheduler] Autonomous trigger '{trigger.trigger_id}' HALTED: "
                        f"Unknown or unregistered capability '{action}'."
                    )
                    return

                if not getattr(cap_desc, "is_live", True):
                    provenance.result_status = "BLOCKED"
                    self.registry.update_state(trigger.trigger_id, TriggerState.BLOCKED, provenance=provenance)
                    logger.warning(
                        f"[TriggerScheduler] Autonomous trigger '{trigger.trigger_id}' HALTED: "
                        f"Capability '{action}' is scaffolded/unwired."
                    )
                    return

                # 2. Evaluate against ExecutionPolicy & High-Risk Confirmation
                policy_decision = policy.evaluate_action(engine, action, params)
                requires_human_approval = (
                    policy_decision.action == PolicyAction.ASK_USER
                    or getattr(cap_desc, "requires_confirmation", False)
                )

                if requires_human_approval:
                    is_pre_authorized = False
                    if trigger.auth_signature and trigger.is_recurring_authorized:
                        valid_trig_sig, _ = auth.verify_trigger_signature(
                            trigger_id=trigger.trigger_id,
                            action_goal=trigger.action_goal,
                            execution_map=trigger.execution_map,
                            signature=trigger.auth_signature,
                        )
                        is_pre_authorized = valid_trig_sig

                    if not is_pre_authorized:
                        ticket_id = params.get("approval_ticket_id")
                        signature = params.get("approval_signature")
                        target_str = str(params.get("target") or params.get("path") or params.get("command") or action)

                        if not (ticket_id and signature):
                            provenance.result_status = "BLOCKED"
                            self.registry.update_state(trigger.trigger_id, TriggerState.BLOCKED, provenance=provenance)
                            logger.warning(
                                f"[TriggerScheduler] Autonomous trigger '{trigger.trigger_id}' HALTED: "
                                f"Action '{action}' requires confirmation, but no valid cryptographic ticket provided."
                            )
                            return

                        valid_sig, sig_err = auth.verify_and_redeem(
                            ticket_id=ticket_id,
                            signature=signature,
                            action_type=action,
                            target=target_str,
                            parameters=params,
                        )
                        if not valid_sig:
                            provenance.result_status = "BLOCKED"
                            self.registry.update_state(trigger.trigger_id, TriggerState.BLOCKED, provenance=provenance)
                            logger.warning(
                                f"[TriggerScheduler] Autonomous trigger '{trigger.trigger_id}' HALTED: "
                                f"Cryptographic verification failed ({sig_err})."
                            )
                            return

            if self.coordinator:
                try:
                    res = await self.coordinator.coordinate(exec_map)
                    provenance.execution_id = getattr(res, "execution_id", uuid.uuid4().hex[:8])
                    if getattr(res, "success", False):
                        provenance.result_status = "VERIFIED"
                        self.registry.update_state(trigger.trigger_id, TriggerState.VERIFIED, provenance=provenance)
                    else:
                        provenance.result_status = "FAILED"
                        self.registry.update_state(trigger.trigger_id, TriggerState.FAILED, provenance=provenance)
                except Exception as exc:
                    logger.error(f"[TriggerScheduler] Coordinator execution error for '{trigger.trigger_id}': {exc}")
                    provenance.result_status = "FAILED"
                    self.registry.update_state(trigger.trigger_id, TriggerState.FAILED, provenance=provenance)
            else:
                provenance.result_status = "VERIFIED"
                self.registry.update_state(trigger.trigger_id, TriggerState.VERIFIED, provenance=provenance)

        finally:
            if trigger.dedup_key:
                self._active_events.discard(trigger.dedup_key)

    async def _scheduler_loop(self) -> None:
        """Periodically evaluates SCHEDULED triggers from registry."""
        while self._is_running:
            try:
                triggers = self.registry.list_triggers(enabled_only=True)
                for trigger in triggers:
                    if trigger.trigger_type == TriggerType.SCHEDULED and trigger.state in [TriggerState.ARMED, TriggerState.REGISTERED]:
                        await self.fire_trigger(trigger)
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TriggerScheduler] Error in scheduler loop: {e}")
                await asyncio.sleep(self.poll_interval_seconds)
