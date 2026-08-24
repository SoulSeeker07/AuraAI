"""
Unit Tests for Execution Events & NodeState 6-Member Taxonomy (Core Orchestration)
Location: tests/unit/test_execution_events.py
"""

from dataclasses import FrozenInstanceError
import pytest
from src.core.orchestration.task_decomposer import SubTask, PlannerRole
from src.core.orchestration.execution_events import (
    NodeState,
    GraphInitializedEvent,
    NodeStateChangedEvent,
    ConfirmationRequiredEvent,
    ExecutionStartedEvent,
    ExecutionFinishedEvent,
    ReplanTriggeredEvent,
    SubTaskNodeInfo,
)


def test_nodestate_all_six_members():
    """Verify that NodeState defines all 6 canonical states."""
    expected_members = {
        "PENDING": "pending",
        "RUNNING": "running",
        "COMPLETED": "completed",
        "FAILED": "failed",
        "SKIPPED": "skipped",
        "CANCELLED": "cancelled",
    }
    for name, value in expected_members.items():
        assert hasattr(NodeState, name)
        assert getattr(NodeState, name).value == value
        assert NodeState.from_str(value) == getattr(NodeState, name)


@pytest.mark.parametrize("status_str, expected_state", [
    ("pending", NodeState.PENDING),
    ("running", NodeState.RUNNING),
    ("completed", NodeState.COMPLETED),
    ("success", NodeState.COMPLETED),
    ("failed", NodeState.FAILED),
    ("error", NodeState.FAILED),
    ("skipped", NodeState.SKIPPED),
    ("cancelled", NodeState.CANCELLED),
    ("aborted", NodeState.CANCELLED),
])
def test_nodestate_from_str_normalization(status_str, expected_state):
    """Verify robust parsing from string representations and legacy aliases."""
    assert NodeState.from_str(status_str) == expected_state


@pytest.mark.parametrize("invalid_status", [
    "unknown_status",
    "partially_done",
    "halted",
    "",
    "   ",
    "null",
    "123",
])
def test_nodestate_from_str_rejects_unknown(invalid_status):
    """Verify that unknown status strings raise ValueError explicitly."""
    with pytest.raises(ValueError) as exc_info:
        NodeState.from_str(invalid_status)
    assert f"Unknown NodeState '{invalid_status}'" in str(exc_info.value)


def test_subtask_all_six_states_compatibility():
    """Verify that SubTask instances can be constructed with each of the six statuses."""
    all_statuses = ["pending", "running", "completed", "failed", "skipped", "cancelled"]
    for idx, st_status in enumerate(all_statuses):
        st = SubTask(
            task_id=f"task_{idx}",
            title=f"Task {idx}",
            required_role=PlannerRole.DESKTOP,
            capability="app_open",
            status=st_status,
        )
        assert st.status == st_status
        node_state = NodeState.from_str(st.status)
        assert node_state.value == st_status


def test_nodestate_changed_event_verified_tristate():
    """Verify tri-state verification flag (None, True, False) on NodeStateChangedEvent."""
    # 1. Unverified / In-flight (None)
    ev_unverified = NodeStateChangedEvent(
        task_id="t1",
        new_state=NodeState.RUNNING,
        verified=None,
    )
    assert ev_unverified.verified is None

    # 2. Verified Passed (True)
    ev_passed = NodeStateChangedEvent(
        task_id="t1",
        new_state=NodeState.COMPLETED,
        verified=True,
    )
    assert ev_passed.verified is True

    # 3. Verified Failed (False)
    ev_failed = NodeStateChangedEvent(
        task_id="t1",
        new_state=NodeState.FAILED,
        verified=False,
    )
    assert ev_failed.verified is False


def test_confirmation_required_event_structure():
    """Verify ConfirmationRequiredEvent fields and immutability."""
    ev = ConfirmationRequiredEvent(
        session_id="sess_123",
        task_id="task_1",
        plan_id="plan_abc",
        prompt="Delete 100 files?",
        target="C:/temp",
        capability="file.delete",
        remaining_task_ids=("task_2", "task_3"),
    )
    assert ev.session_id == "sess_123"
    assert ev.task_id == "task_1"
    assert ev.plan_id == "plan_abc"
    assert ev.prompt == "Delete 100 files?"
    assert ev.target == "C:/temp"
    assert ev.capability == "file.delete"
    assert ev.remaining_task_ids == ("task_2", "task_3")

    with pytest.raises(FrozenInstanceError):
        ev.prompt = "Mutated prompt"


def test_execution_events_immutability_and_structure():
    """Verify that execution event dataclasses are frozen and raise FrozenInstanceError."""
    node_info = SubTaskNodeInfo(
        task_id="t1",
        title="Open Notepad",
        required_role="desktop",
        capability="app_open",
        status=NodeState.PENDING,
    )
    assert node_info.task_id == "t1"
    assert node_info.status == NodeState.PENDING

    event = NodeStateChangedEvent(
        task_id="t1",
        new_state=NodeState.RUNNING,
        old_state=NodeState.PENDING,
    )
    assert event.task_id == "t1"
    assert event.new_state == NodeState.RUNNING
    assert event.old_state == NodeState.PENDING

    # Explicitly verify FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        event.new_state = NodeState.COMPLETED
