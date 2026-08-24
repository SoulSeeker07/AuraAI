"""
Unit Tests for ExecutionTraceModel (Headless QAbstractListModel)
Location: tests/unit/test_execution_trace_model.py

Verifies that ExecutionTraceModel:
1. Operates headlessly as a QAbstractListModel without requiring a running QApplication.
2. Ingests the complete lifecycle in deterministic order.
3. Faithfully reflects tri-state verification (None -> "—", True -> "PASS", False -> "FAIL").
4. Accurately badges exact blocked nodes on ConfirmationRequiredEvent using task_id.
5. Fires loud tripwire warnings upon receiving events for unknown task_ids.
6. Exposes LevelRole for visual DAG indentation.
7. Tracks ReplanTriggeredEvent for telemetry and metrics.
"""

import logging
import pytest
from PySide6.QtCore import QModelIndex, Qt

from core.orchestration.execution_events import (
    ConfirmationRequiredEvent,
    ExecutionFinishedEvent,
    ExecutionStartedEvent,
    GraphInitializedEvent,
    NodeState,
    NodeStateChangedEvent,
    ReplanTriggeredEvent,
    SubTaskNodeInfo,
)
from gui.models.execution_trace_model import ExecutionTraceModel, ExecutionTraceNode


def test_model_initial_state():
    """Verify initial empty state of ExecutionTraceModel."""
    model = ExecutionTraceModel()
    assert model.rowCount() == 0
    assert model.session_id == ""
    assert model.goal == ""
    assert model.is_running is False
    assert model.get_all_nodes() == []
    assert len(model.roleNames()) >= 9


def test_model_full_lifecycle_event_ingestion():
    """Verify model state progression through all lifecycle events."""
    model = ExecutionTraceModel()

    # 1. ExecutionStartedEvent
    model.on_event(ExecutionStartedEvent(goal="Organize Desktop", session_id="sess_abc123"))
    assert model.session_id == "sess_abc123"
    assert model.goal == "Organize Desktop"
    assert model.is_running is True
    assert model.rowCount() == 0

    # 2. GraphInitializedEvent with 2 execution levels
    nodes_info = (
        SubTaskNodeInfo(
            task_id="task_1",
            title="Scan desktop directory",
            required_role="desktop",
            capability="file.scan",
            status=NodeState.PENDING,
        ),
        SubTaskNodeInfo(
            task_id="task_2",
            title="Move files to archive",
            required_role="desktop",
            capability="file.move",
            dependencies=("task_1",),
            status=NodeState.PENDING,
        ),
    )
    model.on_event(GraphInitializedEvent(
        goal="Organize Desktop",
        session_id="sess_abc123",
        nodes=nodes_info,
        execution_order=(("task_1",), ("task_2",)),
    ))
    assert model.rowCount() == 2

    node1 = model.get_node("task_1")
    node2 = model.get_node("task_2")
    assert node1 is not None and node2 is not None
    assert node1.status == NodeState.PENDING
    assert node2.status == NodeState.PENDING
    assert node1.level == 0
    assert node2.level == 1
    assert node1.verified is None

    # Test LevelRole in data()
    idx1 = model.index(0, 0)
    idx2 = model.index(1, 0)
    assert model.data(idx1, ExecutionTraceModel.LevelRole) == 0
    assert model.data(idx2, ExecutionTraceModel.LevelRole) == 1

    # 3. NodeStateChangedEvent -> RUNNING (task_1)
    model.on_event(NodeStateChangedEvent(task_id="task_1", new_state=NodeState.RUNNING))
    assert node1.status == NodeState.RUNNING
    assert node1.start_time is not None

    # 4. NodeStateChangedEvent -> COMPLETED with verified=True (task_1)
    model.on_event(NodeStateChangedEvent(
        task_id="task_1",
        new_state=NodeState.COMPLETED,
        verified=True,
    ))
    assert node1.status == NodeState.COMPLETED
    assert node1.verified is True
    assert node1.duration_ms is not None

    # 5. NodeStateChangedEvent -> RUNNING & COMPLETED with verified=None (task_2, unverified)
    model.on_event(NodeStateChangedEvent(task_id="task_2", new_state=NodeState.RUNNING))
    model.on_event(NodeStateChangedEvent(
        task_id="task_2",
        new_state=NodeState.COMPLETED,
        verified=None,
    ))
    assert node2.status == NodeState.COMPLETED
    assert node2.verified is None

    # 6. ExecutionFinishedEvent
    model.on_event(ExecutionFinishedEvent(
        goal="Organize Desktop",
        session_id="sess_abc123",
        success=True,
        observations=("2 tasks finished",),
    ))
    assert model.is_running is False
    assert model.success is True


def test_model_tristate_verification_role_formatting():
    """Verify that Qt data() returns honest '—', 'PASS', and 'FAIL' strings."""
    model = ExecutionTraceModel()

    nodes_info = (
        SubTaskNodeInfo(task_id="t1", title="Task 1", required_role="desktop", capability="c1"),
        SubTaskNodeInfo(task_id="t2", title="Task 2", required_role="desktop", capability="c2"),
        SubTaskNodeInfo(task_id="t3", title="Task 3", required_role="desktop", capability="c3"),
    )
    model.on_event(GraphInitializedEvent(goal="Test", session_id="s1", nodes=nodes_info))

    # t1: completed with verified=None (honest unverified)
    model.on_event(NodeStateChangedEvent(task_id="t1", new_state=NodeState.COMPLETED, verified=None))
    # t2: completed with verified=True
    model.on_event(NodeStateChangedEvent(task_id="t2", new_state=NodeState.COMPLETED, verified=True))
    # t3: failed with verified=False
    model.on_event(NodeStateChangedEvent(task_id="t3", new_state=NodeState.FAILED, verified=False))

    idx_t1 = model.index(0, 0)
    idx_t2 = model.index(1, 0)
    idx_t3 = model.index(2, 0)

    assert model.data(idx_t1, ExecutionTraceModel.VerifiedRole) == "—"
    assert model.data(idx_t2, ExecutionTraceModel.VerifiedRole) == "PASS"
    assert model.data(idx_t3, ExecutionTraceModel.VerifiedRole) == "FAIL"


def test_model_confirmation_required_exact_node_badging():
    """Verify that ConfirmationRequiredEvent badges the exact task_id without touching others."""
    model = ExecutionTraceModel()

    nodes_info = (
        SubTaskNodeInfo(task_id="task_delete_1", title="Delete temp folder", required_role="desktop", capability="file.delete"),
        SubTaskNodeInfo(task_id="task_delete_2", title="Delete system log", required_role="desktop", capability="file.delete"),
    )
    model.on_event(GraphInitializedEvent(goal="Clean disk", session_id="s1", nodes=nodes_info))

    # Emit ConfirmationRequiredEvent targeting only task_delete_2
    model.on_event(ConfirmationRequiredEvent(
        session_id="s1",
        task_id="task_delete_2",
        plan_id="plan_98765",
        prompt="Confirm deleting system log?",
        target="system.log",
        capability="file.delete",
    ))

    node1 = model.get_node("task_delete_1")
    node2 = model.get_node("task_delete_2")

    assert node1.awaiting_confirmation is False
    assert node2.awaiting_confirmation is True
    assert node2.confirmation_prompt == "Confirm deleting system log?"
    assert node2.confirmation_plan_id == "plan_98765"

    idx_node2 = model.index(1, 0)
    assert model.data(idx_node2, ExecutionTraceModel.StatusRole) == "Awaiting Approval"
    assert model.data(idx_node2, ExecutionTraceModel.AwaitingApprovalRole) is True

    # When user confirms and node transitions to RUNNING, badging clears
    model.on_event(NodeStateChangedEvent(task_id="task_delete_2", new_state=NodeState.RUNNING))
    assert node2.awaiting_confirmation is False
    assert model.data(idx_node2, ExecutionTraceModel.StatusRole) == "RUNNING"
    assert model.data(idx_node2, ExecutionTraceModel.AwaitingApprovalRole) is False


def test_model_unknown_task_id_tripwire_warning(caplog):
    """
    CRITICAL TRIPWIRE TEST:
    Verify that receiving an event for an unknown/unspliced task_id
    emits a loud WARNING log instead of silently dropping it.
    """
    model = ExecutionTraceModel()

    nodes_info = (
        SubTaskNodeInfo(task_id="task_known", title="Known task", required_role="desktop", capability="c1"),
    )
    model.on_event(GraphInitializedEvent(goal="Tripwire Test", session_id="s_trip", nodes=nodes_info))

    with caplog.at_level(logging.WARNING):
        # 1. State change for unknown task_id
        model.on_event(NodeStateChangedEvent(task_id="task_unknown_99", new_state=NodeState.RUNNING))
        # 2. Confirmation required for unknown task_id
        model.on_event(ConfirmationRequiredEvent(session_id="s_trip", task_id="task_ghost_404", plan_id="p_ghost"))

    # Assert warning logs were produced
    warning_logs = [rec.message for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any("task_unknown_99" in msg for msg in warning_logs)
    assert any("task_ghost_404" in msg for msg in warning_logs)


def test_model_replan_triggered_event_handling():
    """Verify that ReplanTriggeredEvent increments replan_count and is recorded in summary."""
    model = ExecutionTraceModel()

    model.on_event(ExecutionStartedEvent(goal="Initial Goal", session_id="s_replan"))
    assert model.replan_count == 0

    model.on_event(ReplanTriggeredEvent(
        reason="Blocked by missing artifact",
        old_goal="Initial Goal",
        new_goal="Alternative Goal",
    ))
    assert model.replan_count == 1

    summary = model.get_summary()
    assert summary["replan_count"] == 1


def test_model_on_event_error_containment(caplog, monkeypatch):
    """
    CRITICAL ERROR CONTAINMENT TEST:
    Verify that an exception raised inside an event handler is caught,
    logged at ERROR level, does not crash the Qt event loop caller,
    and leaves the model state uncorrupted for subsequent events.
    """
    model = ExecutionTraceModel()

    nodes_info = (
        SubTaskNodeInfo(task_id="t1", title="Task 1", required_role="desktop", capability="c1"),
    )
    model.on_event(GraphInitializedEvent(goal="Containment Test", session_id="s_err", nodes=nodes_info))
    assert model.rowCount() == 1
    assert model.get_node("t1").status == NodeState.PENDING

    # Monkeypatch handler to simulate a crash
    def exploding_handler(event):
        raise RuntimeError("Simulated GUI slot explosion!")

    monkeypatch.setattr(model, "_handle_node_state_changed", exploding_handler)

    with caplog.at_level(logging.ERROR):
        # Must not raise or propagate
        model.on_event(NodeStateChangedEvent(task_id="t1", new_state=NodeState.RUNNING))

    # Assert loud ERROR log with exception info was recorded
    error_logs = [rec.message for rec in caplog.records if rec.levelno == logging.ERROR]
    assert any("Simulated GUI slot explosion!" in msg for msg in error_logs)
    assert any("NodeStateChangedEvent" in msg for msg in error_logs)

    # Undo monkeypatch and verify model recovers cleanly
    monkeypatch.undo()
    model.on_event(NodeStateChangedEvent(task_id="t1", new_state=NodeState.RUNNING))
    assert model.get_node("t1").status == NodeState.RUNNING
    model.on_event(ExecutionFinishedEvent(goal="Containment Test", session_id="s_err", success=True))
    assert model.is_running is False

