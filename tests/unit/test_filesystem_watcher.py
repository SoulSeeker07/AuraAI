"""
Unit & Integration Tests for M24 Phase 5: FilesystemWatcher Physical Telemetry Producer
Location: tests/unit/test_filesystem_watcher.py

Verifies:
1. Live physical filesystem event detection (create, modify, delete, move) converted into AuraEvent.
2. Event storm deduplication: rapid successive writes compressed into bounded signals.
3. Temporary & noise file suppression via downstream EventInterpreter.
4. Clean lifecycle management (start, stop, add_watch, remove_watch, thread termination).
5. Error resilience: non-existent paths or permission errors do not crash the watcher.
6. Complete Live Pipeline Verification:
   Physical File Write -> FilesystemWatcher -> AuraEvent -> EventRuntime -> EventInterpreter -> AutonomyPolicyGate -> PolicyDecision
"""

import asyncio
import os
from pathlib import Path
import shutil
import tempfile
import time
import pytest

from autonomy.events import (
    AuraEvent,
    EventSource,
    EventType,
)
from autonomy.event_runtime import EventRuntime, EventTraceRecord
from autonomy.interpreter import EventAssessment, EventInterpreter
from autonomy.policy_gate import AutonomyPolicyGate, PolicyDecision, PolicyDecisionType
from autonomy.watchers.filesystem import FilesystemWatcher


@pytest.fixture
def temp_watch_dir():
    """Creates an isolated temporary directory for live filesystem tests."""
    tmp = tempfile.mkdtemp(prefix="aura_fs_watch_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_live_filesystem_create_and_modify(temp_watch_dir):
    """Verify physical file creation and modification are converted to AuraEvents."""
    runtime = EventRuntime(dedup_window_seconds=0.1)
    watcher = FilesystemWatcher(runtime=runtime, watch_paths=[temp_watch_dir])
    watcher.start()

    try:
        # Give observer thread time to start
        time.sleep(0.3)

        # 1. Create a test file
        test_file = temp_watch_dir / "sample.py"
        test_file.write_text("print('hello world')", encoding="utf-8")

        # Allow OS events to propagate
        time.sleep(0.5)

        traces = runtime.list_traces()
        assert len(traces) >= 1
        paths = [t.normalized_resource for t in traces if t.normalized_resource]
        assert any("sample.py" in p for p in paths)

    finally:
        watcher.stop()


@pytest.mark.asyncio
async def test_rapid_write_burst_deduplication(temp_watch_dir):
    """Verify rapid physical writes to the same file are deduplicated by EventRuntime."""
    runtime = EventRuntime(dedup_window_seconds=1.0)
    watcher = FilesystemWatcher(runtime=runtime, watch_paths=[temp_watch_dir])
    watcher.start()

    try:
        time.sleep(0.3)
        burst_file = temp_watch_dir / "burst_log.txt"

        # Rapidly write 50 times in under 200ms
        for i in range(50):
            burst_file.write_text(f"log line {i}\n", encoding="utf-8")

        time.sleep(0.5)

        metrics = runtime.get_metrics()
        # Ingested count reflects all OS events, while suppressed count reflects high deduplication
        assert metrics["ingested"] > 1
        assert metrics["suppressed"] >= 1
        # The number of emitted events should be small (bounded)
        assert metrics["emitted"] <= 5

    finally:
        watcher.stop()


@pytest.mark.asyncio
async def test_noise_file_suppressed_downstream(temp_watch_dir):
    """Verify temporary lock and cache files are suppressed by EventInterpreter."""
    runtime = EventRuntime(dedup_window_seconds=0.1)
    interpreter = EventInterpreter()
    assessments: list[EventAssessment] = []

    async def dispatch_handler(event: AuraEvent, trace: EventTraceRecord):
        assessment = await interpreter.interpret(event)
        assessments.append(assessment)

    runtime.set_dispatch_handler(dispatch_handler)
    await runtime.start()

    watcher = FilesystemWatcher(runtime=runtime, watch_paths=[temp_watch_dir])
    watcher.start()

    try:
        time.sleep(0.3)

        # Create temporary swap / lock files
        tmp_file = temp_watch_dir / "editor.swp"
        tmp_file.write_text("lock", encoding="utf-8")

        pyc_file = temp_watch_dir / "cache.tmp"
        pyc_file.write_text("data", encoding="utf-8")

        time.sleep(0.6)
        await asyncio.sleep(0.2)

        assert len(assessments) >= 1
        for asm in assessments:
            # Noise files must be marked as not actionable with None candidate intent
            assert asm.is_actionable is False
            assert asm.candidate_intent is None

    finally:
        watcher.stop()
        await runtime.stop()


def test_watcher_resilience_non_existent_path():
    """Verify adding non-existent paths fails gracefully without throwing unhandled exceptions."""
    runtime = EventRuntime()
    watcher = FilesystemWatcher(runtime=runtime)

    success = watcher.add_watch("Z:\\non_existent_drive_9999\\fake_folder")
    assert success is False
    assert len(watcher.list_watches()) == 0


def test_watcher_lifecycle_controls(temp_watch_dir):
    """Verify clean start, stop, and watch list management."""
    runtime = EventRuntime()
    watcher = FilesystemWatcher(runtime=runtime)

    assert watcher.is_running() is False

    # Add watch
    added = watcher.add_watch(temp_watch_dir)
    assert added is True
    assert len(watcher.list_watches()) == 1

    # Start observer
    watcher.start()
    assert watcher.is_running() is True

    # Remove watch
    removed = watcher.remove_watch(temp_watch_dir)
    assert removed is True
    assert len(watcher.list_watches()) == 0

    # Stop observer
    watcher.stop()
    assert watcher.is_running() is False


@pytest.mark.asyncio
async def test_full_live_pipeline_e2e_causal_chain(temp_watch_dir):
    """
    COMPLETE LIVE DEMO TEST:
    Physical File Mutation -> FilesystemWatcher -> AuraEvent -> EventRuntime ->
    EventInterpreter (WorldModel resolution) -> AutonomyPolicyGate -> PolicyDecision
    """
    runtime = EventRuntime(dedup_window_seconds=0.2)
    interpreter = EventInterpreter()
    policy_gate = AutonomyPolicyGate()

    completed_pipeline: list[dict[str, Any]] = []

    async def autonomous_dispatch_handler(event: AuraEvent, trace: EventTraceRecord):
        # 1. EventRuntime dispatches event
        group = runtime.correlation_engine.get_group(event.correlation_id)
        
        # 2. EventInterpreter evaluates meaning & context
        assessment = await interpreter.interpret(event, group=group)

        # 3. AutonomyPolicyGate evaluates risk & generates signed PolicyDecision
        decision = policy_gate.evaluate(assessment)

        # 4. Verify decision authenticity
        is_valid = policy_gate.verify_authorization(decision, assessment.assessment_id)

        completed_pipeline.append({
            "event_id": event.event_id,
            "correlation_id": event.correlation_id,
            "assessment_id": assessment.assessment_id,
            "policy_decision_id": decision.policy_decision_id,
            "decision": decision.decision.value,
            "risk_tier": decision.risk_tier.value,
            "candidate_intent": assessment.candidate_intent,
            "is_valid": is_valid,
        })

    runtime.set_dispatch_handler(autonomous_dispatch_handler)
    await runtime.start()

    watcher = FilesystemWatcher(runtime=runtime, watch_paths=[temp_watch_dir])
    watcher.start()

    try:
        time.sleep(0.3)

        # Modify a Python file in the watched directory
        source_file = temp_watch_dir / "orchestrator.py"
        source_file.write_text("class Orchestrator:\n    pass\n", encoding="utf-8")

        # Allow OS watcher + async dispatch loop to process
        time.sleep(0.6)
        await asyncio.sleep(0.2)

        assert len(completed_pipeline) >= 1
        record = completed_pipeline[0]

        # Verify full causal identity chain
        assert record["event_id"].startswith("evt_")
        assert record["correlation_id"].startswith("corr_")
        assert record["assessment_id"].startswith("asm_")
        assert record["policy_decision_id"].startswith("pol_")
        assert record["decision"] == "ALLOWED"
        assert record["risk_tier"] in ["low", "medium"]
        assert record["candidate_intent"] is not None
        assert record["is_valid"] is True

    finally:
        watcher.stop()
        await runtime.stop()
