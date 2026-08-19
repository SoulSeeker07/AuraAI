"""
Unit Tests for M24 Phase 2: EventRuntime Core Engine
Location: tests/unit/test_event_runtime_core.py

Verifies:
1. Single choke-point ingestion: accepts only AuraEvent, rejects invalid inputs.
2. Semantic path & resource normalization.
3. High-volume sliding window deduplication (e.g., 3,000 rapid burst events -> 1 emitted, 2,999 suppressed).
4. Multi-signal event correlation grouping.
5. Causal EventTraceRecord creation with full metadata.
6. Safe downstream dispatch to handler (zero direct capability execution or OS calls).
7. Thread-safe concurrent ingestion across worker threads.
8. Bounded queue overflow & backpressure management.
9. Clean lifecycle start / stop / queue drain.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest

from autonomy.events import (
    AuraEvent,
    EventSource,
    EventType,
    EventUrgency,
    EventValidationError,
)
from autonomy.event_runtime import (
    CorrelatedEventGroup,
    EventRuntime,
    EventTraceRecord,
    compute_semantic_fingerprint,
    normalize_resource_key,
)


def test_ingest_type_enforcement():
    """Verify that ingest rejects any object that is not an AuraEvent."""
    runtime = EventRuntime()

    with pytest.raises(EventValidationError, match="EventRuntime.ingest requires an AuraEvent instance"):
        runtime.ingest({"event_type": "filesystem.created", "payload": {}})  # type: ignore

    with pytest.raises(EventValidationError, match="EventRuntime.ingest requires an AuraEvent instance"):
        runtime.ingest("raw_string_event")  # type: ignore


def test_resource_key_normalization():
    """Verify deterministic resource normalization across Windows paths and process names."""
    # Windows path case-folding and backslash normalization
    p1 = {"path": "C:\\Workspace\\Project\\main.py"}
    p2 = {"path": "c:/workspace/project/main.py"}
    norm1 = normalize_resource_key(EventSource.FILESYSTEM, p1)
    norm2 = normalize_resource_key(EventSource.FILESYSTEM, p2)
    assert norm1 == norm2
    assert "main.py" in norm1

    # Process name normalization
    proc_p = {"process_name": "  PYTHON.EXE  "}
    assert normalize_resource_key(EventSource.PROCESS, proc_p) == "python.exe"

    # Network endpoint normalization
    net_p = {"url": "HTTPS://API.GITHUB.COM/EVENTS"}
    assert normalize_resource_key(EventSource.NETWORK, net_p) == "https://api.github.com/events"


def test_windowed_deduplication_basic():
    """Verify that identical events within temporal window are suppressed."""
    runtime = EventRuntime(dedup_window_seconds=1.0)

    event1 = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "C:\\repo\\src\\main.py"},
    )
    event2 = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "C:\\repo\\src\\main.py"},
    )

    trace1 = runtime.ingest(event1)
    trace2 = runtime.ingest(event2)

    assert trace1.dedup_status == "EMITTED"
    assert trace1.duplicate_count == 1

    assert trace2.dedup_status == "SUPPRESSED_DUPLICATE"
    assert trace2.duplicate_count == 2
    assert trace2.metadata.get("primary_event_id") == event1.event_id

    metrics = runtime.get_metrics()
    assert metrics["ingested"] == 2
    assert metrics["emitted"] == 1
    assert metrics["suppressed"] == 1


def test_high_volume_event_burst_storm_3000():
    """
    CRITICAL ARCHITECTURAL SAFETY TEST:
    3,000 rapid file modification events during e.g. git checkout
    must produce exactly ONE emitted trace and 2,999 suppressed duplicates.
    """
    runtime = EventRuntime(dedup_window_seconds=2.0)

    traces = [
        runtime.ingest(
            AuraEvent.create(
                event_type=EventType.FILESYSTEM_MODIFIED,
                source=EventSource.FILESYSTEM,
                payload={"path": "D:\\projects\\AuraAI\\src\\core\\orchestration\\master_orchestrator.py"},
            )
        )
        for _ in range(3000)
    ]

    assert len(traces) == 3000
    assert traces[0].dedup_status == "EMITTED"
    assert traces[0].duplicate_count == 1

    for t in traces[1:]:
        assert t.dedup_status == "SUPPRESSED_DUPLICATE"

    assert traces[-1].duplicate_count == 3000

    metrics = runtime.get_metrics()
    assert metrics["ingested"] == 3000
    assert metrics["emitted"] == 1
    assert metrics["suppressed"] == 2999


def test_multi_signal_correlation_grouping():
    """Verify that multi-signal events sharing a correlation_id are properly grouped."""
    runtime = EventRuntime()
    shared_corr_id = "corr_test_failure_group_001"

    # Signal 1: Python file modified
    evt1 = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "src/core/app.py"},
        correlation_id=shared_corr_id,
    )
    # Signal 2: Pytest exited with code 1
    evt2 = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process": "pytest.exe", "exit_code": 1},
        correlation_id=shared_corr_id,
    )

    t1 = runtime.ingest(evt1)
    t2 = runtime.ingest(evt2)

    assert t1.dedup_status == "EMITTED"
    assert t2.dedup_status == "EMITTED"

    group = runtime.correlation_engine.get_group(shared_corr_id)
    assert group is not None
    assert len(group.events) == 2
    assert group.events[0].event_id == evt1.event_id
    assert group.events[1].event_id == evt2.event_id


def test_concurrent_ingestion_thread_safety():
    """Verify thread-safety when multiple worker threads ingest events concurrently."""
    runtime = EventRuntime(dedup_window_seconds=1.0)
    num_threads = 8
    events_per_thread = 200

    def ingest_worker(thread_idx: int):
        for i in range(events_per_thread):
            runtime.ingest(
                AuraEvent.create(
                    event_type=EventType.FILESYSTEM_CREATED,
                    source=EventSource.FILESYSTEM,
                    payload={"path": f"C:\\workspace\\thread_{thread_idx}_file_{i % 5}.py"},
                )
            )

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(ingest_worker, idx) for idx in range(num_threads)]
        for f in futures:
            f.result()

    metrics = runtime.get_metrics()
    assert metrics["ingested"] == num_threads * events_per_thread
    # Each thread touches only 5 distinct files -> exactly 8 * 5 = 40 unique fingerprints emitted
    assert metrics["emitted"] == num_threads * 5
    assert metrics["suppressed"] == (num_threads * events_per_thread) - (num_threads * 5)


@pytest.mark.asyncio
async def test_async_dispatch_worker_safe_handoff():
    """
    Verify asynchronous dispatch worker delivers candidate events strictly to registered handler
    without executing capabilities or modifying external OS state.
    """
    dispatched_events: list[tuple[AuraEvent, EventTraceRecord]] = []

    async def mock_event_interpreter_handler(event: AuraEvent, trace: EventTraceRecord):
        # Pure intelligence inspection simulation
        dispatched_events.append((event, trace))

    runtime = EventRuntime(dispatch_handler=mock_event_interpreter_handler)
    await runtime.start()

    evt1 = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process": "build.exe", "exit_code": 0},
    )
    evt2 = AuraEvent.create(
        event_type=EventType.APPLICATION_FOCUSED,
        source=EventSource.APPLICATION,
        payload={"app_name": "Visual Studio Code"},
    )

    t1 = runtime.ingest(evt1)
    t2 = runtime.ingest(evt2)

    # Allow worker to process queue
    await asyncio.sleep(0.1)
    await runtime.stop()

    assert len(dispatched_events) == 2
    assert dispatched_events[0][0].event_id == evt1.event_id
    assert dispatched_events[1][0].event_id == evt2.event_id

    # Check updated trace statuses in runtime
    trace1_updated = runtime.get_trace(evt1.event_id)
    assert trace1_updated is not None
    assert trace1_updated.dispatch_status == "DISPATCHED"
    assert trace1_updated.dispatched_at is not None


@pytest.mark.asyncio
async def test_queue_overflow_and_backpressure():
    """Verify bounded queue rejects or marks overflow cleanly when capacity exceeded."""
    # Small queue of size 2
    runtime = EventRuntime(max_queue_size=2)
    # Start runtime but with a slow handler to fill queue
    slow_lock = asyncio.Event()

    async def blocking_handler(event: AuraEvent, trace: EventTraceRecord):
        await slow_lock.wait()

    runtime.set_dispatch_handler(blocking_handler)
    await runtime.start()

    # Ingest 5 distinct events
    traces = [
        runtime.ingest(
            AuraEvent.create(
                event_type=EventType.CUSTOM,
                source=EventSource.SYSTEM,
                payload={"index": i},
            )
        )
        for i in range(5)
    ]

    # Unblock handler and stop
    slow_lock.set()
    await runtime.stop()

    metrics = runtime.get_metrics()
    assert metrics["ingested"] == 5
    # The excess events beyond queue capacity were recorded with DROPPED_OVERFLOW
    overflow_traces = [t for t in traces if t.dispatch_status == "DROPPED_OVERFLOW"]
    assert len(overflow_traces) > 0
    assert metrics["dropped"] == len(overflow_traces)
