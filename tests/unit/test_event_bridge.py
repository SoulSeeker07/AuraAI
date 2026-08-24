"""
Unit Tests for ExecutionEventBridge Cross-Thread Signal Marshaling
Location: tests/unit/test_event_bridge.py

Verifies:
1. Event dispatch from same thread.
2. Cross-thread signal marshaling via Qt QueuedConnection from a real background worker thread.
3. Strict main-thread execution of ExecutionTraceModel mutations (thread affinity safety).
4. Safe connect/disconnect lifecycle.
"""

import threading
import time
import pytest
from PySide6.QtCore import QCoreApplication

from core.orchestration.execution_events import (
    ExecutionStartedEvent,
    GraphInitializedEvent,
    NodeState,
    NodeStateChangedEvent,
    SubTaskNodeInfo,
)
from gui.event_bridge import ExecutionEventBridge
from gui.models.execution_trace_model import ExecutionTraceModel


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QCoreApplication instance exists for Qt event loop and signal processing."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_bridge_direct_connection_same_thread(qapp):
    """Verify direct event forwarding on the same thread."""
    bridge = ExecutionEventBridge()
    model = ExecutionTraceModel()
    bridge.connect_model(model)

    ev = ExecutionStartedEvent(goal="Direct Goal", session_id="sess_101")
    bridge.sink_callback(ev)

    assert model.goal == "Direct Goal"
    assert model.session_id == "sess_101"
    assert model.is_running is True


def test_bridge_cross_thread_queued_connection_and_thread_affinity(qapp):
    """
    CRITICAL MULTI-THREADING SAFETY TEST:
    Verify that when sink_callback is called from a real background worker thread:
    1. The model mutation executes strictly on the main GUI thread (not worker thread).
    2. Events are queued and delivered during QCoreApplication.processEvents().
    """
    main_thread_id = threading.get_ident()
    execution_thread_ids = []

    bridge = ExecutionEventBridge()
    model = ExecutionTraceModel()
    bridge.connect_model(model)

    # Attach thread-monitoring spy to signal
    def thread_spy(event):
        execution_thread_ids.append(threading.get_ident())

    bridge.execution_event.connect(thread_spy)

    worker_thread_id = None

    def background_worker():
        nonlocal worker_thread_id
        worker_thread_id = threading.get_ident()

        # Emit execution started
        bridge.sink_callback(ExecutionStartedEvent(goal="Thread Goal", session_id="sess_thread_test"))

        # Emit graph initialization
        nodes_info = (
            SubTaskNodeInfo(
                task_id="t1",
                title="Worker Task",
                required_role="desktop",
                capability="app_open",
                status=NodeState.PENDING,
            ),
        )
        bridge.sink_callback(GraphInitializedEvent(
            goal="Thread Goal",
            session_id="sess_thread_test",
            nodes=nodes_info,
        ))

        # Emit node running
        bridge.sink_callback(NodeStateChangedEvent(task_id="t1", new_state=NodeState.RUNNING))

    # Run the worker on a real background OS thread
    thread = threading.Thread(target=background_worker)
    thread.start()
    thread.join(timeout=3.0)

    assert worker_thread_id is not None
    assert worker_thread_id != main_thread_id

    # Process queued events on the main thread event loop
    qapp.processEvents()

    # Verify model state updated correctly
    assert model.session_id == "sess_thread_test"
    assert model.goal == "Thread Goal"
    assert model.rowCount() == 1
    assert model.get_node("t1").status == NodeState.RUNNING

    # Verify that all slot executions occurred strictly on the main GUI thread!
    assert len(execution_thread_ids) == 3
    for tid in execution_thread_ids:
        assert tid == main_thread_id, f"Slot executed on thread {tid}, expected main thread {main_thread_id}"


def test_bridge_disconnect_model(qapp):
    """Verify that disconnected models no longer receive signal updates."""
    bridge = ExecutionEventBridge()
    model = ExecutionTraceModel()
    bridge.connect_model(model)

    bridge.sink_callback(ExecutionStartedEvent(goal="Goal 1", session_id="sess_1"))
    assert model.goal == "Goal 1"

    bridge.disconnect_model(model)
    bridge.sink_callback(ExecutionStartedEvent(goal="Goal 2", session_id="sess_2"))

    # Model remains on Goal 1
    assert model.goal == "Goal 1"
    assert model.session_id == "sess_1"
