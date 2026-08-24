"""
Unit Tests for ExecutionTraceModel (Headless)
Location: tests/unit/test_execution_trace_model.py

Verifies that ExecutionTraceModel:
1. Operates headlessly without requiring a running QApplication.
2. Ingests the 6-event lifecycle in deterministic order.
3. Faithfully reflects tri-state verification (None -> "—", True -> "PASS", False -> "FAIL").
4. Accurately badges exact blocked nodes on ConfirmationRequiredEvent using task_id.
5. Documents and handles graph lifecycle transitions cleanly.
"""

import pytest

from core.orchestration.execution_events import (
    ConfirmationRequiredEvent,
    ExecutionFinishedEvent,
    ExecutionStartedEvent,
    GraphInitializedEvent,
    NodeState,
    NodeStateChangedEvent,
    SubTaskNodeInfo,
)
from gui.models.execution_trace_model import ExecutionTraceModel, ExecutionTraceNode


def test_model_initial_state():
    """Verify initial empty state of ExecutionTraceModel."""
    model = ExecutionTraceModel()
    assert model.rowCount() == 0
    assert model.columnCount() == 6
    assert model.session_id == ""
    assert model.goal == ""
    assert model.is_running is False
    assert model.get_all_nodes() == []


def test_model_full_lifecycle_event_ingestion():
    """Verify model state progression through all lifecycle events."""
    model = ExecutionTraceModel()

    # 1. ExecutionStartedEvent
    model.on_event(ExecutionStartedEvent(goal="Organize Desktop", session_id="sess_abc123"))
    assert model.session_id == "sess_abc123"
    assert model.goal == "Organize Desktop"
    assert model.is_running is True
    assert model.rowCount() == 0

    # 2. GraphInitializedEvent
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
    assert node1.verified is None

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


def test_model_tristate_verification_column_formatting():
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

    # Inspect data() for Verified column (col index 4)
    # Qt.DisplayRole = 0
    from PySide6.QtCore import Qt

    idx_t1 = model.index(0, 4)
    idx_t2 = model.index(1, 4)
    idx_t3 = model.index(2, 4)

    assert model.data(idx_t1, Qt.DisplayRole) == "—"
    assert model.data(idx_t2, Qt.DisplayRole) == "PASS"
    assert model.data(idx_t3, Qt.DisplayRole) == "FAIL"


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

    from PySide6.QtCore import Qt
    idx_node2_status = model.index(1, 3)
    assert model.data(idx_node2_status, Qt.DisplayRole) == "Awaiting Approval"

    # When user confirms and node transitions to RUNNING, badging clears
    model.on_event(NodeStateChangedEvent(task_id="task_delete_2", new_state=NodeState.RUNNING))
    assert node2.awaiting_confirmation is False
    assert model.data(idx_node2_status, Qt.DisplayRole) == "RUNNING"


def test_model_summary_statistics():
    """Verify get_summary() aggregation dictionary."""
    model = ExecutionTraceModel()

    nodes_info = (
        SubTaskNodeInfo(task_id="t1", title="Task 1", required_role="desktop", capability="c1"),
        SubTaskNodeInfo(task_id="t2", title="Task 2", required_role="desktop", capability="c2"),
        SubTaskNodeInfo(task_id="t3", title="Task 3", required_role="desktop", capability="c3"),
    )
    model.on_event(GraphInitializedEvent(goal="Summary Test", session_id="s_sum", nodes=nodes_info))
    model.on_event(NodeStateChangedEvent(task_id="t1", new_state=NodeState.COMPLETED, verified=True))
    model.on_event(NodeStateChangedEvent(task_id="t2", new_state=NodeState.COMPLETED, verified=None))
    model.on_event(ConfirmationRequiredEvent(session_id="s_sum", task_id="t3", plan_id="p1"))

    summary = model.get_summary()
    assert summary["session_id"] == "s_sum"
    assert summary["total_nodes"] == 3
    assert summary["completed"] == 2
    assert summary["verified_passed"] == 1
    assert summary["unverified"] == 2  # t2 and t3 (unverified)
    assert summary["awaiting_confirmation"] is True
