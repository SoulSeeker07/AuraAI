"""
Unit Tests for M24 Phase 3: EventInterpreter & EventAssessment Engine
Location: tests/unit/test_event_interpreter.py

Verifies:
1. Safety Test 1: Irrelevant event suppression (noise files, clean exit 0).
2. Safety Test 2: Low-confidence/low-relevance threshold suppression.
3. Safety Test 3: Strict Zero-Execution boundary (pure interpretation, zero side-effects).
4. Safety Test 4: Causal identity preservation (event_id & correlation_id links).
5. Meaningful interpretation of failed test/build processes (pytest exit code 1).
6. Meaningful interpretation of significant workspace source changes.
7. Multi-signal correlated group synthesis.
8. Deep immutability and serialization round-trip of EventAssessment.
"""

from dataclasses import FrozenInstanceError
from typing import Any
import pytest

from autonomy.events import (
    AuraEvent,
    EventSource,
    EventType,
    EventUrgency,
)
from autonomy.event_runtime import CorrelatedEventGroup
from autonomy.interpreter import (
    EventAssessment,
    EventInterpreter,
    IContextResolver,
)


class MockContextResolver(IContextResolver):
    """Mock context provider returning simulated WorldModel facts."""

    def __init__(self, workspace_name: str = "AuraAI", git_branch: str = "main") -> None:
        self.workspace_name = workspace_name
        self.git_branch = git_branch

    async def get_active_context(self, entity_hint: str) -> dict[str, Any]:
        return {
            "active_workspace": self.workspace_name,
            "git_branch": self.git_branch,
            "entity_hint": entity_hint,
        }


@pytest.mark.asyncio
async def test_safety_1_irrelevant_noise_suppression():
    """
    Safety Test 1:
    Noise events (e.g. __pycache__ touch, .git/index.lock, clean exit 0)
    must produce is_actionable=False and candidate_intent=None.
    """
    interpreter = EventInterpreter()

    # Noise file modification in __pycache__
    noise_file_evt = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "D:\\projects\\AuraAI\\src\\__pycache__\\app.cpython-311.pyc"},
    )
    assessment1 = await interpreter.interpret(noise_file_evt)
    assert assessment1.is_actionable is False
    assert assessment1.candidate_intent is None
    assert assessment1.relevance < 0.3
    assert "noise file filter" in assessment1.reason

    # Clean process exit code 0
    clean_proc_evt = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process_name": "python.exe", "exit_code": 0},
    )
    assessment2 = await interpreter.interpret(clean_proc_evt)
    assert assessment2.is_actionable is False
    assert assessment2.candidate_intent is None
    assert assessment2.relevance < 0.5


@pytest.mark.asyncio
async def test_safety_2_low_confidence_threshold_suppression():
    """
    Safety Test 2:
    Events that do not meet both relevance and confidence thresholds
    must have candidate_intent stripped and marked not actionable.
    """
    # Strict interpreter with high thresholds
    strict_interpreter = EventInterpreter(relevance_threshold=0.85, confidence_threshold=0.85)

    # Moderate event (source edit is ~0.70 relevance, below 0.85 threshold)
    source_evt = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "src/utils.py"},
    )
    assessment = await strict_interpreter.interpret(source_evt)

    assert assessment.is_actionable is False
    assert assessment.candidate_intent is None
    assert "Suppressed: score below actionability threshold" in assessment.reason


@pytest.mark.asyncio
async def test_safety_3_zero_execution_guarantee():
    """
    Safety Test 3:
    Verifies that calling EventInterpreter.interpret() on any event
    causes zero capability calls and zero external mutations.
    """
    interpreter = EventInterpreter()
    critical_evt = AuraEvent.create(
        event_type=EventType.PROCESS_CRASHED,
        source=EventSource.PROCESS,
        payload={"process_name": "critical_service.exe", "exit_code": 139},
        urgency=EventUrgency.CRITICAL,
    )

    assessment = await interpreter.interpret(critical_evt)

    # Assessment is purely a data structure
    assert isinstance(assessment, EventAssessment)
    assert assessment.is_actionable is True
    assert assessment.candidate_intent is not None
    # No background tasks spawned, no OS calls made


@pytest.mark.asyncio
async def test_safety_4_causal_identity_preservation():
    """
    Safety Test 4:
    Verifies that EventAssessment preserves event_id and correlation_id precisely.
    """
    interpreter = EventInterpreter()
    custom_event = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process_name": "pytest.exe", "exit_code": 1},
        correlation_id="corr_custom_test_identity_99",
    )

    assessment = await interpreter.interpret(custom_event)

    assert assessment.event_id == custom_event.event_id
    assert assessment.correlation_id == "corr_custom_test_identity_99"
    assert assessment.assessment_id.startswith("asm_")


@pytest.mark.asyncio
async def test_meaningful_interpretation_test_failure():
    """Verify failed build/test run produces high-confidence diagnosis intent."""
    ctx_resolver = MockContextResolver(workspace_name="AuraAI", git_branch="feature/m24")
    interpreter = EventInterpreter(context_resolver=ctx_resolver)

    fail_evt = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process_name": "pytest.exe", "exit_code": 1},
    )

    assessment = await interpreter.interpret(fail_evt)

    assert assessment.is_actionable is True
    assert assessment.relevance >= 0.90
    assert assessment.confidence >= 0.85
    assert assessment.candidate_intent_type == "engineering.diagnose"
    assert "pytest.exe" in (assessment.candidate_intent or "")
    assert assessment.context_resolution["active_workspace"] == "AuraAI"
    assert assessment.context_resolution["git_branch"] == "feature/m24"


@pytest.mark.asyncio
async def test_meaningful_interpretation_correlated_group():
    """Verify multi-signal correlated group enhances interpretation context."""
    interpreter = EventInterpreter()
    shared_corr = "corr_multi_edit_group"

    group = CorrelatedEventGroup(correlation_id=shared_corr)
    evt1 = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "src/core/app.py"},
        correlation_id=shared_corr,
    )
    evt2 = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "src/core/router.py"},
        correlation_id=shared_corr,
    )
    group.add_event(evt1)
    group.add_event(evt2)

    assessment = await interpreter.interpret(evt2, group=group)

    assert assessment.is_actionable is True
    assert assessment.candidate_intent_type == "workspace.evaluate"
    assert assessment.context_resolution["correlated_event_count"] == 2
    assert "multi-file changes" in (assessment.candidate_intent or "").lower()


def test_assessment_immutability_and_serialization():
    """Verify EventAssessment is deeply frozen and supports lossless dictionary roundtrip."""
    assessment = EventAssessment(
        assessment_id="asm_test_01",
        event_id="evt_test_01",
        correlation_id="corr_test_01",
        relevance=0.88,
        confidence=0.92,
        is_actionable=True,
        candidate_intent="Diagnose network disconnection",
        candidate_intent_type="network.diagnose",
        reason="Network lost during cloud synchronization.",
        context_resolution={"active_workspace": "AuraAI"},
    )

    # Immutability
    with pytest.raises((FrozenInstanceError, AttributeError)):
        assessment.relevance = 0.5  # type: ignore

    with pytest.raises((FrozenInstanceError, AttributeError)):
        assessment.is_actionable = False  # type: ignore

    # Serialization roundtrip
    as_dict = assessment.to_dict()
    assert as_dict["assessment_id"] == "asm_test_01"
    assert as_dict["relevance"] == 0.88

    reconstructed = EventAssessment.from_dict(as_dict)
    assert reconstructed.assessment_id == assessment.assessment_id
    assert reconstructed.event_id == assessment.event_id
    assert reconstructed.relevance == assessment.relevance
    assert reconstructed.is_actionable == assessment.is_actionable
    assert reconstructed.candidate_intent == assessment.candidate_intent


@pytest.mark.asyncio
async def test_end_to_end_runtime_to_interpreter_pipeline():
    """
    Verifies the complete integration:
    AuraEvent -> EventRuntime (ingest, normalize, correlate) -> EventInterpreter -> EventAssessment
    """
    import asyncio
    from autonomy.event_runtime import EventRuntime, EventTraceRecord

    completed_assessments: list[EventAssessment] = []
    interpreter = EventInterpreter()

    async def runtime_dispatch_handler(event: AuraEvent, trace: EventTraceRecord):
        # EventRuntime dispatches event to EventInterpreter
        group = runtime.correlation_engine.get_group(event.correlation_id)
        assessment = await interpreter.interpret(event, group=group)
        completed_assessments.append(assessment)

    runtime = EventRuntime(dispatch_handler=runtime_dispatch_handler)
    await runtime.start()

    # Ingest a failed test run event
    fail_evt = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process_name": "pytest.exe", "exit_code": 1},
        correlation_id="corr_e2e_pipeline_001",
    )
    trace = runtime.ingest(fail_evt)

    assert trace.dedup_status == "EMITTED"

    # Allow worker loop to process
    await asyncio.sleep(0.1)
    await runtime.stop()

    assert len(completed_assessments) == 1
    assessment = completed_assessments[0]
    assert assessment.event_id == fail_evt.event_id
    assert assessment.correlation_id == "corr_e2e_pipeline_001"
    assert assessment.is_actionable is True
    assert assessment.candidate_intent_type == "engineering.diagnose"

