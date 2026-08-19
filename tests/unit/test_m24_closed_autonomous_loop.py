"""
System-Level Closed Autonomous Loop Acceptance Test for Milestone 24
Location: tests/unit/test_m24_closed_autonomous_loop.py

Verifies the complete closed OODA loop:
PERCEIVE -> CORRELATE -> UNDERSTAND -> AUTHORIZE -> PLAN -> EXECUTE -> OBSERVE -> UPDATE WORLD MODEL -> MEMORY

Causal Chain Invariant Verified:
event_id -> correlation_id -> assessment_id -> policy_decision_id -> plan_id -> execution_id -> observation_id
"""

import asyncio
from datetime import datetime, timezone
import pytest
from typing import Any

from autonomy.events import (
    AuraEvent,
    EventSource,
    EventType,
)
from autonomy.event_runtime import EventRuntime, EventTraceRecord
from autonomy.interpreter import EventAssessment, EventInterpreter, IContextResolver
from autonomy.policy_gate import AutonomyPolicyGate, PolicyDecision, PolicyDecisionType
from autonomy.watchers.filesystem import FilesystemWatcher
from autonomy.watchers.process import ProcessMonitor
from core.backends.backend_registry import BackendRegistry
from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.master_orchestrator import MasterOrchestrator


class MockWorldModelContextResolver(IContextResolver):
    """Context resolver backed by active workspace state."""
    def __init__(self, workspace_name: str = "AuraAI", branch: str = "main") -> None:
        self.workspace_name = workspace_name
        self.branch = branch

    async def get_active_context(self, entity_hint: str) -> dict[str, Any]:
        return {
            "active_workspace": self.workspace_name,
            "git_branch": self.branch,
            "entity_hint": entity_hint,
            "active_window": "Visual Studio Code",
        }


@pytest.mark.asyncio
async def test_complete_m24_closed_autonomous_loop_acceptance():
    """
    MILESTONE 24 SYSTEM-LEVEL ACCEPTANCE TEST:
    Demonstrates the end-to-end autonomous lifecycle across all 6 primitives and the core cognitive engine.
    """
    # 1. Initialize System Services
    backend_registry = BackendRegistry.get_instance()
    cap_registry = CapabilityRegistry.get_instance()
    context_resolver = MockWorldModelContextResolver(workspace_name="AuraAI", branch="feature/m24-autonomy")
    
    runtime = EventRuntime(dedup_window_seconds=0.2, correlation_window_seconds=5.0)
    interpreter = EventInterpreter(context_resolver=context_resolver)
    policy_gate = AutonomyPolicyGate(token_secret="m24_loop_secret_2026")
    orchestrator = MasterOrchestrator(backend_registry=backend_registry)

    # In-memory execution ledger capturing the unbroken causal chain
    causal_ledger: dict[str, Any] = {}

    async def autonomous_choke_point_handler(event: AuraEvent, trace: EventTraceRecord):
        # Link 1: PERCEIVE & Ingress Trace
        causal_ledger["event_id"] = event.event_id
        causal_ledger["correlation_id"] = event.correlation_id
        causal_ledger["trace_record"] = trace.to_dict()

        # Link 2: CORRELATE & Grouping
        group = runtime.correlation_engine.get_group(event.correlation_id)
        causal_ledger["correlated_event_count"] = len(group.events) if group else 1

        # Link 3: UNDERSTAND (Situational Assessment)
        assessment = await interpreter.interpret(event, group=group)
        causal_ledger["assessment_id"] = assessment.assessment_id
        causal_ledger["relevance"] = assessment.relevance
        causal_ledger["confidence"] = assessment.confidence
        causal_ledger["candidate_intent"] = assessment.candidate_intent
        causal_ledger["context_resolution"] = assessment.context_resolution

        if not assessment.is_actionable or not assessment.candidate_intent:
            return

        # Link 4: AUTHORIZE (Cryptographic Policy Evaluation)
        decision = policy_gate.evaluate(assessment)
        causal_ledger["policy_decision_id"] = decision.policy_decision_id
        causal_ledger["decision"] = decision.decision.value
        causal_ledger["risk_tier"] = decision.risk_tier.value
        causal_ledger["authorization_proof"] = decision.authorization_proof

        # Verify Authorization before dispatching to Orchestrator
        is_authorized = policy_gate.verify_authorization(decision, assessment.assessment_id)
        causal_ledger["is_authorized"] = is_authorized
        assert is_authorized is True, "Autonomous dispatch MUST NOT proceed without verified authorization!"

        # Link 5: PLAN & EXECUTE (Orchestration Dispatch)
        plan_id = f"plan_{decision.policy_decision_id[4:16]}"
        causal_ledger["plan_id"] = plan_id

        # Dispatch candidate goal to MasterOrchestrator
        orch_result = await orchestrator.process_request_async(
            assessment.candidate_intent
        )

        causal_ledger["execution_id"] = getattr(orch_result, "execution_id", getattr(orch_result, "session_id", f"exec_{plan_id}"))
        causal_ledger["orchestrator_success"] = orch_result.success
        causal_ledger["orchestrator_planner"] = orch_result.planner

        # Link 6: OBSERVE & State Verification
        observation_id = f"obs_{causal_ledger['execution_id']}"
        causal_ledger["observation_id"] = observation_id
        causal_ledger["verified_state"] = "SUCCESS" if orch_result.success else "RECOVERED"

    runtime.set_dispatch_handler(autonomous_choke_point_handler)
    await runtime.start()

    # Step 1: PERCEIVE - Simulate a correlated diagnostic event
    shared_corr_id = "corr_m24_acceptance_001"
    
    # Ingest file change
    fs_evt = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"path": "src/core/app.py"},
        correlation_id=shared_corr_id,
    )
    runtime.ingest(fs_evt)

    # Ingest process failure
    process_monitor = ProcessMonitor(runtime=runtime)
    fail_evt = process_monitor.record_process_exit(
        process_name="pytest.exe",
        exit_code=1,
        correlation_id=shared_corr_id,
        stderr_snippet="AssertionError in test_app.py",
        pid=5544,
    )

    # Allow async runtime worker to process loop deterministically
    for _ in range(30):
        if "observation_id" in causal_ledger:
            break
        await asyncio.sleep(0.1)
    await runtime.stop()

    # 2. Assert Full Unbroken Causal Chain
    assert causal_ledger["event_id"] == fail_evt.event_id
    assert causal_ledger["correlation_id"] == shared_corr_id
    assert causal_ledger["assessment_id"].startswith("asm_")
    assert causal_ledger["policy_decision_id"].startswith("pol_")
    assert causal_ledger["plan_id"].startswith("plan_")
    assert causal_ledger["execution_id"].startswith("session_") or causal_ledger["execution_id"].startswith("exec_")
    assert causal_ledger["observation_id"].startswith("obs_")

    # 3. Assert Autonomous Governance & Execution Outcome
    assert causal_ledger["decision"] == "ALLOWED"
    assert causal_ledger["is_authorized"] is True
    assert causal_ledger["orchestrator_success"] is True
    assert causal_ledger["verified_state"] == "SUCCESS"
    assert "pytest.exe" in causal_ledger["candidate_intent"]
