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

logger = logging.getLogger(__name__)


class TriggerScheduler:
    """
    Autonomous Trigger Scheduler Daemon.
    Evaluates scheduled and event-driven triggers registered in TriggerRegistry.
    """

    def __init__(
        self,
        registry: TriggerRegistry,
        coordinator: Any | None = None,
        policy: Any | None = None,
        event_runtime: Any | None = None,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        self.registry = registry
        self.coordinator = coordinator
        self.policy = policy
        self.event_runtime = event_runtime
        self.poll_interval_seconds = poll_interval_seconds

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
        logger.info("[TriggerScheduler] Autonomous trigger scheduler daemon started.")

    async def stop(self, drain_timeout: float = 2.0) -> None:
        """Stop the trigger scheduler daemon and cancel pending evaluation."""
        if not self._is_running:
            return

        self._is_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None

        # Await running trigger tasks with drain timeout
        if self._running_tasks:
            pending = [t for t in self._running_tasks if not t.done()]
            if pending:
                try:
                    await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=drain_timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"[TriggerScheduler] Shutdown timeout draining {len(pending)} running trigger tasks.")

        logger.info("[TriggerScheduler] Autonomous trigger scheduler daemon stopped.")

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
                    fired = await self.fire_trigger(trigger, fired_payload=payload)
                    if fired:
                        matched_count += 1

        return matched_count

    async def fire_trigger(self, trigger: Trigger, fired_payload: dict[str, Any] | None = None) -> bool:
        """
        Fire a single trigger with concurrency policy enforcement and provenance tracking.
        """
        if trigger.state == TriggerState.RUNNING:
            if trigger.concurrency_policy == ConcurrencyPolicy.REJECT:
                logger.warning(f"[TriggerScheduler] Trigger '{trigger.trigger_id}' is already RUNNING — rejecting duplicate execution.")
                return False
            elif trigger.concurrency_policy == ConcurrencyPolicy.COALESCE:
                logger.info(f"[TriggerScheduler] Trigger '{trigger.trigger_id}' is already RUNNING — coalescing trigger event.")
                return False

        if trigger.dedup_key and trigger.dedup_key in self._active_events:
            logger.warning(f"[TriggerScheduler] Active event with dedup_key '{trigger.dedup_key}' is already processing — coalescing.")
            return False

        provenance = EventProvenance(
            trigger_id=trigger.trigger_id,
            dedup_key=trigger.dedup_key or trigger.trigger_id,
            trigger_type=trigger.trigger_type.value if hasattr(trigger.trigger_type, "value") else str(trigger.trigger_type),
            fired_at=datetime.now().isoformat(),
        )

        if trigger.dedup_key:
            self._active_events.add(trigger.dedup_key)

        self.registry.update_state(trigger.trigger_id, TriggerState.FIRED, provenance=provenance)

        # Launch async execution task
        task = asyncio.create_task(self._execute_trigger_task(trigger, provenance))
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)

        logger.info(f"[TriggerScheduler] Trigger '{trigger.trigger_id}' FIRED -> Event {provenance.event_id} queued.")
        return True

    async def _execute_trigger_task(self, trigger: Trigger, provenance: EventProvenance) -> None:
        """Worker task executing policy evaluation and coordinator dispatch for a fired trigger."""
        try:
            self.registry.update_state(trigger.trigger_id, TriggerState.RUNNING, provenance=provenance)
            exec_map = dict(trigger.execution_map or {})
            exec_map["goal"] = f"[Trigger: {trigger.trigger_type} | Event: {provenance.event_id}] {trigger.action_goal}"

            from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction
            policy = self.policy or ExecutionPolicy.get_instance()
            steps = exec_map.get("steps", [])

            for step in steps:
                engine = step.get("engine", "desktop")
                action = step.get("action", "")
                params = step.get("parameters", {})
                policy_decision = policy.evaluate_action(engine, action, params)
                if policy_decision.action == PolicyAction.ASK_USER and not params.get("user_authorized", False):
                    provenance.result_status = "BLOCKED"
                    self.registry.update_state(trigger.trigger_id, TriggerState.BLOCKED, provenance=provenance)
                    logger.warning(f"[TriggerScheduler] Autonomous trigger '{trigger.trigger_id}' HALTED by ExecutionPolicy: {policy_decision.message}")
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
