"""
Unit Tests for MasterOrchestrator Execution Event Sink & Circuit Breaker Instrumentation
Location: tests/unit/test_orchestrator_sink_instrumentation.py

Verifies the 6 emission sites against real orchestrator plumbing, correct event
payload population, tri-state verification handling, and the 3-strike circuit-breaker
detachment with loud error logging.
"""

import logging
from unittest.mock import MagicMock
import pytest

from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.execution_events import (
    NodeState,
    ExecutionStartedEvent,
    GraphInitializedEvent,
    NodeStateChangedEvent,
    ConfirmationRequiredEvent,
    ExecutionFinishedEvent,
)
from core.planning.execution_result import ExecutionResult
from core.backends.backend_registry import BackendRegistry


def create_mock_backend(
    planner: str = "desktop",
    goal: str = "test",
    success: bool = True,
    policy_action: str = "launch_new",
    verification_passed: bool | None = None,
    observations: list[str] | None = None,
):
    backend = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "describe", "health_check"])
    backend.name = "mock_backend"
    data = {"policy_action": policy_action, "action_target": "notepad", "capability": "app_open", "plan_id": "plan_test123"}
    if verification_passed is not None:
        data["verification_passed"] = verification_passed
    obs = observations if observations is not None else (["Executed successfully"] if success else ["Execution failed"])
    res = ExecutionResult(
        success=success,
        planner=planner,
        goal=goal,
        observations=obs,
        data=data,
    )
    backend.execute.return_value = res
    backend.execute_plan.return_value = res
    return backend


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Ensure clean orchestrator singleton before and after each test."""
    MasterOrchestrator.reset_instance()
    BackendRegistry.reset_instance()
    yield
    MasterOrchestrator.reset_instance()
    BackendRegistry.reset_instance()


@pytest.mark.asyncio
async def test_sink_receives_all_lifecycle_events_in_order():
    """Verify that a registered sink receives all lifecycle events in deterministic order."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    mock_backend = create_mock_backend(goal="Open Notepad", success=True, verification_passed=True)
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    res = await orchestrator.process_request_async("Open Notepad")
    assert res.success is True

    # Check event order
    event_types = [type(e) for e in emitted_events]
    assert event_types == [
        ExecutionStartedEvent,
        GraphInitializedEvent,
        NodeStateChangedEvent,  # RUNNING
        NodeStateChangedEvent,  # COMPLETED
        ExecutionFinishedEvent,
    ]

    # Verify GraphInitializedEvent contents
    graph_ev = emitted_events[1]
    assert isinstance(graph_ev, GraphInitializedEvent)
    assert graph_ev.goal == "Open Notepad"
    assert len(graph_ev.nodes) >= 1
    assert graph_ev.nodes[0].capability == "app_open"
    assert graph_ev.nodes[0].status == NodeState.PENDING

    # Verify NodeStateChangedEvent (RUNNING)
    running_ev = emitted_events[2]
    assert isinstance(running_ev, NodeStateChangedEvent)
    assert running_ev.new_state == NodeState.RUNNING
    assert running_ev.old_state == NodeState.PENDING

    # Verify NodeStateChangedEvent (COMPLETED) with explicit tri-state verified=True
    completed_ev = emitted_events[3]
    assert isinstance(completed_ev, NodeStateChangedEvent)
    assert completed_ev.new_state == NodeState.COMPLETED
    assert completed_ev.old_state == NodeState.RUNNING
    assert completed_ev.verified is True

    # Verify ExecutionFinishedEvent
    finished_ev = emitted_events[4]
    assert isinstance(finished_ev, ExecutionFinishedEvent)
    assert finished_ev.goal == "Open Notepad"
    assert finished_ev.success is True


@pytest.mark.asyncio
async def test_sink_unverified_task_emits_none_tristate():
    """
    CRITICAL REGRESSION TEST:
    Verify that a successful task without an explicit verification check
    emits verified=None (unverified), NEVER silently upgrading to True.
    """
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    # Note: verification_passed is omitted (None)
    mock_backend = create_mock_backend(goal="Open Notepad", success=True, verification_passed=None)
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    res = await orchestrator.process_request_async("Open Notepad")
    assert res.success is True

    completed_events = [
        e for e in emitted_events
        if isinstance(e, NodeStateChangedEvent) and e.new_state == NodeState.COMPLETED
    ]
    assert len(completed_events) == 1
    completed_ev = completed_events[0]

    # Must remain None (honest unverified default)
    assert completed_ev.verified is None


@pytest.mark.asyncio
async def test_sink_failed_task_emits_false_tristate():
    """Verify that a failing task emits verified=False."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    mock_backend = create_mock_backend(goal="Open Notepad", success=False, policy_action="launch_new")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    res = await orchestrator.process_request_async("Open Notepad")
    assert res.success is False

    failed_events = [
        e for e in emitted_events
        if isinstance(e, NodeStateChangedEvent) and e.new_state == NodeState.FAILED
    ]
    assert len(failed_events) >= 1
    failed_ev = failed_events[0]
    assert failed_ev.verified is False


@pytest.mark.asyncio
async def test_sink_receives_confirmation_required_event():
    """Verify that ASK_USER halt emits ConfirmationRequiredEvent with real plan_id and target."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    mock_ask_backend = create_mock_backend(
        goal="Open Notepad",
        success=False,
        policy_action="ask_user",
        observations=["Notepad is already open. Open another instance? (yes / no)"],
    )
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_ask_backend)

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    res = await orchestrator.process_request_async("Open Notepad")
    assert res.success is False

    # Filter for ConfirmationRequiredEvent
    conf_events = [e for e in emitted_events if isinstance(e, ConfirmationRequiredEvent)]
    assert len(conf_events) == 1
    conf_ev = conf_events[0]

    assert conf_ev.target == "notepad"
    assert conf_ev.task_id != ""
    assert conf_ev.capability == "app_open"
    assert conf_ev.plan_id.startswith("plan_")
    assert conf_ev.prompt == "Notepad is already open. Open another instance? (yes / no)"
    assert isinstance(conf_ev.remaining_task_ids, tuple)


@pytest.mark.asyncio
async def test_circuit_breaker_detaches_sink_after_three_strikes(caplog):
    """
    Verify that an unstable/crashing sink:
    1. Does not disrupt core orchestrator execution.
    2. Is detached after 3 consecutive failures.
    3. Logs detachment loudly at ERROR level.
    """
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    mock_backend = create_mock_backend(goal="Open Notepad", success=True)
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    call_count = 0

    def crashing_sink(event):
        nonlocal call_count
        call_count += 1
        raise RuntimeError(f"CrashingSink intentional error #{call_count}")

    orchestrator.set_execution_sink(crashing_sink)
    assert orchestrator._execution_sink is crashing_sink

    with caplog.at_level(logging.ERROR):
        # 1st run: will emit multiple events (ExecutionStarted, GraphInit, Running, Completed, Finished)
        res = await orchestrator.process_request_async("Open Notepad")
        assert res.success is True

    # Assert exactly 3 strikes were attempted before permanent detachment
    assert call_count == 3
    # Sink must now be detached (set to None)
    assert orchestrator._execution_sink is None

    # Assert loud ERROR log message was recorded
    error_logs = [rec.message for rec in caplog.records if rec.levelno == logging.ERROR]
    assert any("Circuit breaker tripped: permanently detaching sink" in msg for msg in error_logs)

    # 2nd run: orchestrator runs normally without crashing or calling the dead sink
    call_count_before = call_count
    res2 = await orchestrator.process_request_async("Open Notepad")
    assert res2.success is True
    assert call_count == call_count_before  # No more calls to detached sink
