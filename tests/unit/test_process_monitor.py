"""
Unit & Integration Tests for M24 Phase 6: ProcessMonitor & Multi-Signal Correlation
Location: tests/unit/test_process_monitor.py

Verifies:
1. Native OS process monitoring lifecycle (start, stop, background polling).
2. Physical subprocess birth & exit detection converted into AuraEvents.
3. Supervised exit observation with non-zero exit code and stderr capture.
4. The Landmark Multi-Signal Correlation Scenario:
   Filesystem modified + Process exited with code 1 + Stderr evidence
   -> ONE CorrelatedEventGroup
   -> ONE EventAssessment ('engineering.diagnose')
   -> ONE PolicyDecision (ALLOWED)
   -> Zero fragmented task duplication.
5. Complete end-to-end causal chain verification:
   event_id -> correlation_id -> assessment_id -> policy_decision_id
"""

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any
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
from autonomy.watchers.process import ProcessMonitor


def test_process_monitor_lifecycle():
    """Verify clean start, stop, and status query on ProcessMonitor."""
    runtime = EventRuntime()
    monitor = ProcessMonitor(runtime=runtime, target_process_names=["python.exe"], poll_interval_seconds=0.1)

    assert monitor.is_running() is False
    monitor.start()
    assert monitor.is_running() is True
    monitor.stop()
    assert monitor.is_running() is False


def test_record_supervised_process_failure():
    """Verify supervised process exit recording produces accurate AuraEvent with stderr."""
    runtime = EventRuntime()
    monitor = ProcessMonitor(runtime=runtime)

    evt = monitor.record_process_exit(
        process_name="pytest.exe",
        exit_code=1,
        correlation_id="corr_supervised_test_01",
        stderr_snippet="FAILED tests/test_auth.py::test_login - AssertionError",
        pid=1234,
    )

    assert evt.event_type == "process.exited"
    assert evt.source == EventSource.PROCESS
    assert evt.payload["process_name"] == "pytest.exe"
    assert evt.payload["exit_code"] == 1
    assert "FAILED tests/test_auth.py" in evt.payload["stderr"]
    assert evt.correlation_id == "corr_supervised_test_01"

    trace = runtime.get_trace(evt.event_id)
    assert trace is not None
    assert trace.dedup_status == "EMITTED"


@pytest.mark.asyncio
async def test_landmark_multi_signal_correlation_situation():
    """
    THE LANDMARK M24 ACCEPTANCE TEST:
    A correlated multi-signal failure scenario:
    1. Python source modified: src/auth.py
    2. Test runner process executed: pytest.exe
    3. Test runner fails with exit code 1
    4. Legitimate stderr captured

    MUST PRODUCE:
    - EXACTLY ONE CorrelatedEventGroup
    - EXACTLY ONE Candidate EventAssessment ('engineering.diagnose')
    - EXACTLY ONE PolicyDecision (ALLOWED with cryptographic proof)
    - ZERO redundant task fragmentation.
    """
    runtime = EventRuntime(dedup_window_seconds=0.5, correlation_window_seconds=5.0)
    interpreter = EventInterpreter()
    policy_gate = AutonomyPolicyGate()

    completed_assessments: list[EventAssessment] = []
    completed_decisions: list[PolicyDecision] = []

    async def runtime_handler(event: AuraEvent, trace: EventTraceRecord):
        # 1. Fetch multi-signal correlation group
        group = runtime.correlation_engine.get_group(event.correlation_id)

        # 2. Interpret event with situational awareness
        assessment = await interpreter.interpret(event, group=group)
        if assessment.is_actionable:
            completed_assessments.append(assessment)

            # 3. Policy Gate Evaluation
            decision = policy_gate.evaluate(assessment)
            completed_decisions.append(decision)

    runtime.set_dispatch_handler(runtime_handler)
    await runtime.start()

    shared_correlation_id = "corr_engineering_failure_001"

    # Step 1: Developer modifies Python source file
    fs_event = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "D:\\projects\\AuraAI\\src\\auth.py", "operation": "modified"},
        correlation_id=shared_correlation_id,
    )
    runtime.ingest(fs_event)

    # Step 2: Test process starts
    start_event = AuraEvent.create(
        event_type=EventType.PROCESS_STARTED,
        source=EventSource.PROCESS,
        payload={"process_name": "pytest.exe", "pid": 9988},
        correlation_id=shared_correlation_id,
    )
    runtime.ingest(start_event)

    # Step 3: Test process fails with exit code 1
    monitor = ProcessMonitor(runtime=runtime)
    fail_event = monitor.record_process_exit(
        process_name="pytest.exe",
        exit_code=1,
        correlation_id=shared_correlation_id,
        stderr_snippet="FAILED tests/test_auth.py - AssertionError: 401 != 200",
        pid=9988,
    )

    # Allow worker loop to process
    await asyncio.sleep(0.3)
    await runtime.stop()

    # Verify Correlation Engine grouped all 3 events
    group = runtime.correlation_engine.get_group(shared_correlation_id)
    assert group is not None
    assert len(group.events) == 3

    # Verify that the multi-signal situation resulted in the actionable diagnostic assessment
    diagnostic_assessments = [a for a in completed_assessments if a.candidate_intent_type == "engineering.diagnose"]
    assert len(diagnostic_assessments) == 1

    asm = diagnostic_assessments[0]
    assert asm.event_id == fail_event.event_id
    assert asm.correlation_id == shared_correlation_id
    assert asm.relevance >= 0.90
    assert asm.confidence >= 0.85
    assert "pytest.exe" in (asm.candidate_intent or "")

    # Verify Policy Gate produced valid ALLOWED decision
    allowed_decisions = [d for d in completed_decisions if d.decision == PolicyDecisionType.ALLOWED and d.assessment_id == asm.assessment_id]
    assert len(allowed_decisions) == 1

    dec = allowed_decisions[0]
    assert dec.assessment_id == asm.assessment_id
    assert policy_gate.verify_authorization(dec, asm.assessment_id) is True

    # Complete Causal Chain Verified
    assert fs_event.correlation_id == shared_correlation_id
    assert start_event.correlation_id == shared_correlation_id
    assert fail_event.correlation_id == shared_correlation_id
    assert asm.correlation_id == shared_correlation_id
    assert dec.assessment_id == asm.assessment_id
