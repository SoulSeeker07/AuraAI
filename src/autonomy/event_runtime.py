"""
EventRuntime Core Engine (M24 Phase 2)
Location: src/autonomy/event_runtime.py

The central, single choke point for all autonomous system, hardware, and environment telemetry.

Architectural Responsibilities:
1. Ingest: Strictly accepts valid, immutable AuraEvent instances.
2. Normalize: Standardizes runtime resource keys (paths, process names, network endpoints).
3. Deduplicate: Semantic fingerprinting within sliding temporal windows to suppress noise storms.
4. Correlate: Links multi-signal events describing the same situation into CorrelatedEventGroups.
5. Dispatch: Forwards filtered candidate events strictly to EventInterpreter (NO direct capability execution).
6. Causal Tracing: Generates immutable EventTraceRecords forming the root of the auditable causal chain.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import threading
from types import MappingProxyType
from typing import Any, Callable, Coroutine, Mapping
import uuid

from .events import AuraEvent, EventSource, EventType, EventUrgency, EventValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventTraceRecord:
    """
    Immutable trace record capturing the ingress and runtime processing of an event.
    Forms the first link in the deterministic causal audit chain:
    event_id -> correlation_id -> assessment_id -> policy_decision_id -> plan_id -> execution_id -> observation_id
    """
    event_id: str
    correlation_id: str
    received_at: str
    source: str
    event_type: str
    semantic_fingerprint: str
    dedup_status: str  # "EMITTED", "SUPPRESSED_DUPLICATE", "COALESCED"
    duplicate_count: int
    dispatch_status: str  # "PENDING", "DISPATCHED", "SUPPRESSED", "DROPPED_OVERFLOW", "NO_HANDLER"
    dispatched_at: str | None = None
    normalized_resource: str | None = None
    metadata: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "received_at": self.received_at,
            "source": self.source,
            "event_type": self.event_type,
            "semantic_fingerprint": self.semantic_fingerprint,
            "dedup_status": self.dedup_status,
            "duplicate_count": self.duplicate_count,
            "dispatch_status": self.dispatch_status,
            "dispatched_at": self.dispatched_at,
            "normalized_resource": self.normalized_resource,
            "metadata": dict(self.metadata),
        }


@dataclass
class CorrelatedEventGroup:
    """
    Groups multi-signal events occurring within a temporal correlation window.
    """
    correlation_id: str
    events: list[AuraEvent] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    primary_source: str = ""
    inferred_context: dict[str, Any] = field(default_factory=dict)

    def add_event(self, event: AuraEvent) -> None:
        self.events.append(event)
        self.last_updated_at = datetime.now(timezone.utc).isoformat()
        if not self.primary_source:
            self.primary_source = event.source.value


def normalize_resource_key(source: EventSource | str, payload: Mapping[str, Any]) -> str:
    """
    Extracts and standardizes the primary resource identity from an event payload.
    e.g. normalizing filesystem paths on Windows (case-fold, forward slashes).
    """
    source_val = source.value if isinstance(source, EventSource) else str(source).lower()

    if source_val == EventSource.FILESYSTEM.value:
        path_val = payload.get("path") or payload.get("file") or payload.get("deleted_path") or payload.get("directory")
        if path_val:
            try:
                norm = os.path.normpath(str(path_val)).lower()
                return norm
            except Exception:
                return str(path_val).lower()

    elif source_val == EventSource.PROCESS.value:
        proc = payload.get("process_name") or payload.get("process") or payload.get("name")
        if proc:
            return str(proc).lower().strip()

    elif source_val == EventSource.NETWORK.value:
        endpoint = payload.get("endpoint") or payload.get("ip") or payload.get("url") or payload.get("host")
        if endpoint:
            return str(endpoint).lower().strip()

    elif source_val == EventSource.APPLICATION.value:
        app = payload.get("app_name") or payload.get("window_title") or payload.get("title")
        if app:
            return str(app).lower().strip()

    # Fallback to key subset
    return json.dumps({k: payload[k] for k in sorted(payload.keys()) if k not in ["timestamp", "time"]}, default=str)


def compute_semantic_fingerprint(event: AuraEvent) -> tuple[str, str]:
    """
    Computes a deterministic hash fingerprint representing the semantic identity of the event.
    Returns (fingerprint_hash, normalized_resource_key).
    """
    norm_resource = normalize_resource_key(event.source, event.payload)
    identity_str = f"{event.source.value}|{event.event_type}|{norm_resource}"
    fingerprint = hashlib.sha256(identity_str.encode("utf-8")).hexdigest()[:16]
    return fingerprint, norm_resource


class DeduplicationEngine:
    """
    Sliding window semantic deduplication engine.
    Suppresses rapid burst events matching identical semantic fingerprints.
    """

    def __init__(self, window_seconds: float = 1.0) -> None:
        self.window_seconds = window_seconds
        # fingerprint -> (first_seen_monotonic, last_seen_monotonic, count, first_event_id)
        self._cache: dict[str, tuple[float, float, int, str]] = {}
        self._lock = threading.Lock()

    def evaluate(self, fingerprint: str, event_id: str, now_mono: float) -> tuple[bool, int, str]:
        """
        Evaluates an event fingerprint against the sliding temporal window.
        Returns: (is_duplicate, duplicate_count, primary_event_id)
        """
        with self._lock:
            # Clean expired records periodically
            self._prune_expired(now_mono)

            if fingerprint in self._cache:
                first_seen, _, count, primary_id = self._cache[fingerprint]
                if (now_mono - first_seen) <= self.window_seconds:
                    new_count = count + 1
                    self._cache[fingerprint] = (first_seen, now_mono, new_count, primary_id)
                    return True, new_count, primary_id

            # New or outside window
            self._cache[fingerprint] = (now_mono, now_mono, 1, event_id)
            return False, 1, event_id

    def _prune_expired(self, now_mono: float) -> None:
        """Removes entries older than 2x window duration."""
        cutoff = now_mono - (self.window_seconds * 2.0)
        expired = [k for k, (first_seen, last_seen, _, _) in self._cache.items() if last_seen < cutoff]
        for k in expired:
            del self._cache[k]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class CorrelationEngine:
    """
    Correlates multi-signal events sharing correlation_id or contextual resource bindings.
    """

    def __init__(self, correlation_window_seconds: float = 5.0) -> None:
        self.correlation_window_seconds = correlation_window_seconds
        self._groups: dict[str, CorrelatedEventGroup] = {}
        self._lock = threading.Lock()

    def correlate(self, event: AuraEvent) -> CorrelatedEventGroup:
        with self._lock:
            corr_id = event.correlation_id
            if corr_id not in self._groups:
                self._groups[corr_id] = CorrelatedEventGroup(correlation_id=corr_id)

            group = self._groups[corr_id]
            group.add_event(event)
            return group

    def get_group(self, correlation_id: str) -> CorrelatedEventGroup | None:
        with self._lock:
            return self._groups.get(correlation_id)

    def clear(self) -> None:
        with self._lock:
            self._groups.clear()


# Type alias for downstream dispatch handler (e.g. EventInterpreter callback)
DispatchHandler = Callable[[AuraEvent, EventTraceRecord], Coroutine[Any, Any, None]]


class EventRuntime:
    """
    Canonical EventRuntime Engine (Single Autonomous-Event Choke Point).
    """

    def __init__(
        self,
        dedup_window_seconds: float = 1.0,
        correlation_window_seconds: float = 5.0,
        max_queue_size: int = 10000,
        dispatch_handler: DispatchHandler | None = None,
        registry: Any | None = None,
        coordinator: Any | None = None,
        policy: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.registry = registry
        self.coordinator = coordinator
        self.policy = policy
        self.dedup_engine = DeduplicationEngine(window_seconds=dedup_window_seconds)
        self.correlation_engine = CorrelationEngine(correlation_window_seconds=correlation_window_seconds)
        self.max_queue_size = max_queue_size
        self._dispatch_handler = dispatch_handler

        # Internal state & queues
        self._queue: asyncio.Queue[tuple[AuraEvent, EventTraceRecord]] | None = None
        self._traces: dict[str, EventTraceRecord] = {}
        self._trace_lock = threading.Lock()
        self._is_running = False
        self._worker_task: asyncio.Task[None] | None = None

        # Metrics
        self._total_ingested = 0
        self._total_emitted = 0
        self._total_suppressed = 0
        self._total_dispatched = 0
        self._total_dropped = 0

        self._scheduler_task: asyncio.Task[None] | None = None
        self._active_events: set[str] = set()

    @property
    def _running(self) -> bool:
        return self._is_running

    @_running.setter
    def _running(self, val: bool) -> None:
        self._is_running = val

    def set_dispatch_handler(self, handler: DispatchHandler) -> None:
        """Register downstream handler (EventInterpreter)."""
        self._dispatch_handler = handler

    async def start(self) -> None:
        """Start the asynchronous event dispatch loop."""
        if self._is_running:
            return

        self._queue = asyncio.Queue(maxsize=self.max_queue_size)
        self._is_running = True
        self._worker_task = asyncio.create_task(self._dispatch_worker())
        if self.registry:
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("[EventRuntime] Core event runtime started.")

    async def stop(self, drain_timeout: float = 2.0) -> None:
        """Stop the event runtime and drain pending dispatches."""
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

        if self._queue and not self._queue.empty():
            try:
                await asyncio.wait_for(self._queue.join(), timeout=drain_timeout)
            except asyncio.TimeoutError:
                logger.warning("[EventRuntime] Shutdown timeout draining event queue.")

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        logger.info("[EventRuntime] Core event runtime stopped.")

    async def emit_event(self, event_type: str, payload: dict[str, Any] | None = None) -> int:
        """Emit a system event. Finds matching triggers and queues them for execution."""
        if not self.registry:
            return 0
        payload = payload or {}
        matched_count = 0
        triggers = self.registry.list_triggers(enabled_only=True)

        from .models import TriggerType
        for trigger in triggers:
            if trigger.trigger_type == TriggerType.SYSTEM_EVENT:
                if not trigger.event_pattern or trigger.event_pattern == event_type or trigger.event_pattern in event_type:
                    await self._fire_trigger(trigger, fired_payload=payload)
                    matched_count += 1

        return matched_count

    async def _scheduler_loop(self) -> None:
        """Periodically evaluates SCHEDULED triggers."""
        from .models import TriggerType, TriggerState
        while self._is_running:
            try:
                if self.registry:
                    triggers = self.registry.list_triggers(enabled_only=True)
                    for trigger in triggers:
                        if trigger.trigger_type == TriggerType.SCHEDULED and trigger.state in [TriggerState.ARMED, TriggerState.REGISTERED]:
                            await self._fire_trigger(trigger)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EventRuntime] Error in scheduler loop: {e}")
                await asyncio.sleep(0.1)

    async def _fire_trigger(self, trigger: Any, fired_payload: dict[str, Any] | None = None) -> bool:
        """Fire a trigger and route to coordinator."""
        from .models import ConcurrencyPolicy, EventProvenance, TriggerState
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
        asyncio.create_task(self._execute_trigger_task(trigger, provenance))
        logger.info(f"[EventRuntime] Trigger '{trigger.trigger_id}' FIRED -> Event {provenance.event_id} queued.")
        return True

    async def _execute_trigger_task(self, trigger: Any, provenance: Any) -> None:
        """Worker task execution for trigger."""
        from .models import TriggerState
        self.registry.update_state(trigger.trigger_id, TriggerState.RUNNING, provenance=provenance)
        exec_map = trigger.execution_map or {}
        exec_map["goal"] = f"[Trigger: {trigger.trigger_type.value} | Event: {provenance.event_id}] {trigger.action_goal}"

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
                logger.warning(f"[EventRuntime] Autonomous trigger '{trigger.trigger_id}' HALTED by ExecutionPolicy: {policy_decision.message}")
                return

        if self.coordinator:
            try:
                res = await self.coordinator.coordinate(exec_map)
                provenance.execution_id = res.execution_id if hasattr(res, "execution_id") else uuid.uuid4().hex[:8]
                if res.success:
                    provenance.result_status = "VERIFIED"
                    self.registry.update_state(trigger.trigger_id, TriggerState.VERIFIED, provenance=provenance)
                else:
                    self.registry.update_state(trigger.trigger_id, TriggerState.FAILED, provenance=provenance)
            except Exception as e:
                provenance.result_status = "FAILED"
                self.registry.update_state(trigger.trigger_id, TriggerState.FAILED, provenance=provenance)

    def ingest(self, event: AuraEvent) -> EventTraceRecord:
        """
        Synchronous / Thread-safe ingress point for an AuraEvent.
        Applies contract validation, semantic deduplication, and correlation.
        """
        if not isinstance(event, AuraEvent):
            raise EventValidationError(f"EventRuntime.ingest requires an AuraEvent instance, got {type(event).__name__}")

        now_utc = datetime.now(timezone.utc).isoformat()
        now_mono = asyncio.get_event_loop().time() if asyncio._get_running_loop() else 0.0

        self._total_ingested += 1

        # 1. Compute semantic fingerprint & normalized resource key
        fingerprint, norm_resource = compute_semantic_fingerprint(event)

        # 2. Evaluate windowed deduplication
        is_dup, dup_count, primary_id = self.dedup_engine.evaluate(fingerprint, event.event_id, now_mono)

        # 3. Correlate multi-signal events
        self.correlation_engine.correlate(event)

        if is_dup:
            self._total_suppressed += 1
            trace = EventTraceRecord(
                event_id=event.event_id,
                correlation_id=event.correlation_id,
                received_at=now_utc,
                source=event.source.value,
                event_type=event.event_type,
                semantic_fingerprint=fingerprint,
                dedup_status="SUPPRESSED_DUPLICATE",
                duplicate_count=dup_count,
                dispatch_status="SUPPRESSED",
                normalized_resource=norm_resource,
                metadata=MappingProxyType({"primary_event_id": primary_id}),
            )
            self._record_trace(trace)
            return trace

        # 4. First / Emitted Event
        self._total_emitted += 1
        trace = EventTraceRecord(
            event_id=event.event_id,
            correlation_id=event.correlation_id,
            received_at=now_utc,
            source=event.source.value,
            event_type=event.event_type,
            semantic_fingerprint=fingerprint,
            dedup_status="EMITTED",
            duplicate_count=1,
            dispatch_status="PENDING",
            normalized_resource=norm_resource,
        )
        self._record_trace(trace)

        # 5. Enqueue for async dispatch if runtime is active
        if self._is_running and self._queue is not None:
            try:
                self._queue.put_nowait((event, trace))
            except asyncio.QueueFull:
                self._total_dropped += 1
                overflow_trace = EventTraceRecord(
                    event_id=event.event_id,
                    correlation_id=event.correlation_id,
                    received_at=now_utc,
                    source=event.source.value,
                    event_type=event.event_type,
                    semantic_fingerprint=fingerprint,
                    dedup_status="EMITTED",
                    duplicate_count=1,
                    dispatch_status="DROPPED_OVERFLOW",
                    normalized_resource=norm_resource,
                )
                self._record_trace(overflow_trace)
                return overflow_trace

        return trace

    async def ingest_async(self, event: AuraEvent) -> EventTraceRecord:
        """Async convenience wrapper for ingest."""
        return self.ingest(event)

    def _record_trace(self, trace: EventTraceRecord) -> None:
        with self._trace_lock:
            self._traces[trace.event_id] = trace

    def get_trace(self, event_id: str) -> EventTraceRecord | None:
        with self._trace_lock:
            return self._traces.get(event_id)

    def list_traces(self, correlation_id: str | None = None, limit: int = 100) -> list[EventTraceRecord]:
        with self._trace_lock:
            traces = list(self._traces.values())
            if correlation_id:
                traces = [t for t in traces if t.correlation_id == correlation_id]
            return traces[-limit:]

    def get_metrics(self) -> dict[str, int]:
        return {
            "ingested": self._total_ingested,
            "emitted": self._total_emitted,
            "suppressed": self._total_suppressed,
            "dispatched": self._total_dispatched,
            "dropped": self._total_dropped,
        }

    async def _dispatch_worker(self) -> None:
        """
        Background worker that processes queued events and passes them strictly to downstream handler.
        Guarantees: Zero capability execution, zero Windows API invocations.
        """
        while self._is_running and self._queue is not None:
            try:
                event, trace = await self._queue.get()
                now_utc = datetime.now(timezone.utc).isoformat()

                if self._dispatch_handler is not None:
                    try:
                        await self._dispatch_handler(event, trace)
                        self._total_dispatched += 1
                        dispatched_trace = EventTraceRecord(
                            event_id=trace.event_id,
                            correlation_id=trace.correlation_id,
                            received_at=trace.received_at,
                            source=trace.source,
                            event_type=trace.event_type,
                            semantic_fingerprint=trace.semantic_fingerprint,
                            dedup_status=trace.dedup_status,
                            duplicate_count=trace.duplicate_count,
                            dispatch_status="DISPATCHED",
                            dispatched_at=now_utc,
                            normalized_resource=trace.normalized_resource,
                            metadata=trace.metadata,
                        )
                        self._record_trace(dispatched_trace)
                    except Exception as e:
                        logger.error(f"[EventRuntime] Downstream dispatch handler error for {event.event_id}: {e}")
                else:
                    # No handler registered
                    no_handler_trace = EventTraceRecord(
                        event_id=trace.event_id,
                        correlation_id=trace.correlation_id,
                        received_at=trace.received_at,
                        source=trace.source,
                        event_type=trace.event_type,
                        semantic_fingerprint=trace.semantic_fingerprint,
                        dedup_status=trace.dedup_status,
                        duplicate_count=trace.duplicate_count,
                        dispatch_status="NO_HANDLER",
                        dispatched_at=now_utc,
                        normalized_resource=trace.normalized_resource,
                        metadata=trace.metadata,
                    )
                    self._record_trace(no_handler_trace)

                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EventRuntime] Unexpected worker loop exception: {e}")
