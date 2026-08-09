"""
Event Runtime Engine (Async Proactive Queue & Worker Isolation)
Location: src/autonomy/event_runtime.py

Runs the proactive event loop, evaluates scheduled triggers, listens to system events,
queues execution items via an in-process asyncio.Queue, enforces M19 ExecutionPolicy risk rules,
dispatches to ExecutionCoordinator, and updates trigger state lifecycle.
"""

import asyncio
from datetime import datetime
import logging
from typing import Any
import uuid

from brain.execution_coordinator import ExecutionCoordinator
from core.orchestration.execution_policy import ExecutionPolicy

from .models import ConcurrencyPolicy, EventProvenance, Trigger, TriggerState, TriggerType
from .trigger_registry import TriggerRegistry

logger = logging.getLogger(__name__)


class EventRuntime:
    """
    Proactive Event Runtime Engine.
    """

    def __init__(
        self,
        registry: TriggerRegistry | None = None,
        coordinator: ExecutionCoordinator | None = None,
        policy: ExecutionPolicy | None = None,
    ):
        self.registry = registry or TriggerRegistry()
        self.coordinator = coordinator or ExecutionCoordinator()
        self.policy = policy or ExecutionPolicy.get_instance()

        self._queue: asyncio.Queue[tuple[Trigger, EventProvenance]] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._loop_task: asyncio.Task | None = None
        self._active_events: set[str] = set()  # Currently processing dedup_keys

    async def start(self) -> None:
        """Start the event runtime loop and worker pool."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue_worker())
        self._loop_task = asyncio.create_task(self._scheduler_loop())
        logger.info("[EventRuntime] Started proactive event runtime loop and queue worker.")

    async def stop(self) -> None:
        """Stop the event runtime loop cleanly."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
        if self._worker_task:
            self._worker_task.cancel()
        logger.info("[EventRuntime] Stopped proactive event runtime.")

    async def emit_event(self, event_type: str, payload: dict[str, Any] | None = None) -> int:
        """
        Emit a system event. Finds matching triggers and queues them for execution.
        """
        payload = payload or {}
        matched_count = 0
        triggers = self.registry.list_triggers(enabled_only=True)

        for trigger in triggers:
            if trigger.trigger_type == TriggerType.SYSTEM_EVENT:
                if not trigger.event_pattern or trigger.event_pattern == event_type or trigger.event_pattern in event_type:
                    await self._fire_trigger(trigger, fired_payload=payload)
                    matched_count += 1

        return matched_count

    async def _scheduler_loop(self) -> None:
        """Periodically evaluates SCHEDULED triggers."""
        while self._running:
            try:
                triggers = self.registry.list_triggers(enabled_only=True)
                for trigger in triggers:
                    if trigger.trigger_type == TriggerType.SCHEDULED and trigger.state in [TriggerState.ARMED, TriggerState.REGISTERED]:
                        # Evaluate scheduled trigger
                        await self._fire_trigger(trigger)
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EventRuntime] Error in scheduler loop: {e}")
                await asyncio.sleep(1.0)

    async def _fire_trigger(self, trigger: Trigger, fired_payload: dict[str, Any] | None = None) -> bool:
        """
        Fire a trigger: check concurrency policy, create EventProvenance, transition state to FIRED,
        and place into in-process queue.
        """
        # Concurrency & Duplicate Check
        if trigger.state == TriggerState.RUNNING:
            if trigger.concurrency_policy == ConcurrencyPolicy.REJECT:
                logger.warning(f"[EventRuntime] Trigger '{trigger.trigger_id}' is already RUNNING — rejecting duplicate execution.")
                return False
            elif trigger.concurrency_policy == ConcurrencyPolicy.COALESCE:
                logger.info(f"[EventRuntime] Trigger '{trigger.trigger_id}' is already RUNNING — coalescing trigger event.")
                return False

        if trigger.dedup_key and trigger.dedup_key in self._active_events:
            logger.warning(f"[EventRuntime] Active event with dedup_key '{trigger.dedup_key}' is already processing — coalescing.")
            return False

        provenance = EventProvenance(
            trigger_id=trigger.trigger_id,
            dedup_key=trigger.dedup_key or trigger.trigger_id,
            trigger_type=trigger.trigger_type.value,
            fired_at=datetime.now().isoformat(),
        )

        self.registry.update_state(trigger.trigger_id, TriggerState.FIRED, provenance=provenance)
        await self._queue.put((trigger, provenance))
        logger.info(f"[EventRuntime] Trigger '{trigger.trigger_id}' FIRED -> Event {provenance.event_id} queued.")
        return True

    async def _process_queue_worker(self) -> None:
        """Worker task processing queued events in order with isolated task execution context."""
        while self._running:
            try:
                trigger, provenance = await self._queue.get()
                dedup_key = provenance.dedup_key or trigger.trigger_id
                self._active_events.add(dedup_key)

                # Execute task in worker isolation
                try:
                    await self._execute_trigger_task(trigger, provenance)
                finally:
                    self._active_events.discard(dedup_key)
                    self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EventRuntime] Worker error processing trigger: {e}")

    async def _execute_trigger_task(self, trigger: Trigger, provenance: EventProvenance) -> None:
        """
        Worker isolation task execution:
        1. Update state to RUNNING
        2. Evaluate M19 Policy & Governance
        3. Dispatch to ExecutionCoordinator
        4. Independent Verification & Failure Recovery
        5. Update state to VERIFIED / BLOCKED / FAILED
        """
        self.registry.update_state(trigger.trigger_id, TriggerState.RUNNING, provenance=provenance)

        # 1. M19 Policy & Governance Check
        exec_map = trigger.execution_map or {}
        # Ensure goal in exec_map has trigger provenance attached
        exec_map["goal"] = f"[Trigger: {trigger.trigger_type.value} | Event: {provenance.event_id}] {trigger.action_goal}"

        from core.orchestration.execution_policy import PolicyAction

        # Evaluate risk level of trigger steps using ExecutionPolicy
        steps = exec_map.get("steps", [])
        for step in steps:
            engine = step.get("engine", "desktop")
            action = step.get("action", "")
            params = step.get("parameters", {})
            policy_decision = self.policy.evaluate_action(engine, action, params)

            # High risk or policy blocked triggers must halt as BLOCKED unless authorized
            if policy_decision.action == PolicyAction.ASK_USER and not params.get("user_authorized", False):
                provenance.result_status = "BLOCKED"
                self.registry.update_state(trigger.trigger_id, TriggerState.BLOCKED, provenance=provenance)
                logger.warning(f"[EventRuntime] Autonomous trigger '{trigger.trigger_id}' HALTED by ExecutionPolicy: {policy_decision.message}")
                return

        # 2. Dispatch to ExecutionCoordinator
        try:
            res = await self.coordinator.coordinate(exec_map)
            provenance.execution_id = res.execution_id if hasattr(res, "execution_id") else uuid.uuid4().hex[:8]

            if res.success:
                provenance.result_status = "VERIFIED"
                self.registry.update_state(trigger.trigger_id, TriggerState.VERIFIED, provenance=provenance)
                logger.info(f"[EventRuntime] Autonomous trigger '{trigger.trigger_id}' VERIFIED SUCCESS (Goal verified).")
            else:
                # Determine if blocked or failed
                is_blocked = False
                for s in res.step_results:
                    d = s.data if hasattr(s, "data") and isinstance(s.data, dict) else {}
                    r = d.get("result") if isinstance(d.get("result"), dict) else {}
                    obs_str = " ".join(getattr(s, "observations", [])).lower()
                    err_str = str(getattr(s, "error", "")).lower()
                    d_str = str(d).lower()
                    if d.get("status") == "BLOCKED" or r.get("status") == "BLOCKED" or "captcha" in d_str or "security" in d_str or "blocked" in obs_str or "captcha" in obs_str or "blocked" in err_str or "security" in err_str:
                        is_blocked = True
                        break

                final_state = TriggerState.BLOCKED if is_blocked else TriggerState.FAILED
                provenance.result_status = final_state.value
                self.registry.update_state(trigger.trigger_id, final_state, provenance=provenance)
                logger.warning(f"[EventRuntime] Autonomous trigger '{trigger.trigger_id}' ended in state '{final_state.value}'")

        except Exception as e:
            provenance.result_status = "FAILED"
            self.registry.update_state(trigger.trigger_id, TriggerState.FAILED, provenance=provenance)
            logger.error(f"[EventRuntime] Execution exception in trigger '{trigger.trigger_id}': {e}")
