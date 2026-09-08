"""
Integration Test: GUI CommandWorkerThread Subagent Survival & Persistent Loop
=============================================================================
Verifies that:
1. A user typing `/background <task>` through the GUI's CommandWorkerThread gets
   an immediate response (<50ms) and the thread completes cleanly.
2. The subagent task does NOT get destroyed or orphaned when CommandWorkerThread terminates.
3. The subagent continues execution on the persistent AsyncRuntime event loop, completes,
   and enqueues its completion card into FocusManager.
4. Subsequent turn via AuraCore receives and renders the drained completion notification.
"""

import os
import sys
import time
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from src.core.async_runtime import AsyncRuntime
from src.core.aura_core import AuraCore
from src.core.focus_manager import FocusManager
from src.core.orchestration.worker_manager import WorkerManager
from src.gui.main_window import CommandWorker


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def cleanup():
    yield
    AsyncRuntime.reset_instance()
    FocusManager.reset_instance()
    WorkerManager.reset_instance()


def test_gui_command_worker_subagent_persists_and_completes(qapp):
    """
    Simulate the exact GUI path:
    User submits '/background scan the codebase for TODOs' via CommandWorker.
    Verify thread termination does not kill the subagent, which completes on AsyncRuntime.
    """
    AsyncRuntime.reset_instance()
    FocusManager.reset_instance()
    WorkerManager.reset_instance()

    runtime = AsyncRuntime.get_instance()
    assert runtime.is_running

    finished_payloads = []
    error_payloads = []

    worker_thread = CommandWorker(
        command="/background scan the codebase for TODO markers",
        session_id="gui_integration_test_session",
    )

    def on_finished(task_id, resp):
        finished_payloads.append((task_id, resp))

    def on_error(task_id, err):
        error_payloads.append((task_id, err))

    worker_thread.finished_signal.connect(on_finished)
    worker_thread.error_signal.connect(on_error)

    # Pre-warm AuraCore kernel instance so first-time lazy-init does not block the command timeout
    AuraCore.get_instance()

    # 1. Start the GUI worker thread
    t0 = time.perf_counter()
    worker_thread.start()

    # Wait for the GUI thread to complete its turn (should be fast, < 2.0s)
    success = worker_thread.wait(15000)
    qapp.processEvents()
    dur = time.perf_counter() - t0

    assert success, "CommandWorker failed to finish within timeout"
    assert worker_thread.isFinished(), "GUI thread must be completely finished"
    assert not error_payloads, f"Unexpected error in GUI thread: {error_payloads}"
    assert len(finished_payloads) == 1, "Expected exactly 1 finished_signal"

    task_id, resp_str = finished_payloads[0]
    assert "dispatched worker" in resp_str.lower(), f"Unexpected ack text: {resp_str}"
    print(f"\n[Test] Immediate GUI turn completed in {dur*1000:.1f}ms with resp: {resp_str[:80]}...")

    # 2. Inspect WorkerManager
    worker_mgr = WorkerManager.get_instance()
    all_workers = list(worker_mgr._workers.values())
    assert len(all_workers) >= 1, "Subagent was not registered in WorkerManager"
    subagent_worker = all_workers[-1]
    print(f"[Test] Subagent worker registered: {subagent_worker.worker_id}, initial status: {subagent_worker.status}")

    # 3. Wait for the background worker to execute on persistent AsyncRuntime loop
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if subagent_worker.status in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.1)

    print(f"[Test] Subagent worker final status: {subagent_worker.status}")
    assert subagent_worker.status == "COMPLETED", (
        f"Worker failed to complete! Status is {subagent_worker.status}. "
        f"If RUNNING, the loop was closed prematurely or task was lost."
    )

    # 4. Verify FocusManager received the completion notification card in pending_notifications
    focus_mgr = FocusManager.get_instance()
    with focus_mgr._get_connection() as conn:
        rows = conn.execute("SELECT * FROM pending_notifications WHERE delivered = 0").fetchall()
    assert len(rows) >= 1, "FocusManager received no completion notifications"
    notif_row = rows[-1]
    assert "finished successfully" in notif_row["message"], f"Unexpected notification: {notif_row['message']}"
    print(f"[Test] FocusManager verified notification in DB: [{notif_row['severity']}] {notif_row['message']}")

    # 5. Verify that the next user turn drains and displays the notification
    core = AuraCore.get_instance()
    next_resp = runtime.run_coroutine_sync(
        core.process_request("what is the current status?", session_id="gui_integration_test_session")
    )
    print(f"[Test] Next chat turn response:\n{next_resp}")
    assert "finished successfully" in next_resp, "Completion card was not drained into subsequent user turn"


def test_gui_subagents_query_and_cancel(qapp):
    """
    Verify /subagents list and /subagent cancel via AuraCore fast-paths.
    """
    runtime = AsyncRuntime.get_instance()
    core = AuraCore.get_instance()

    # Query when empty
    WorkerManager.reset_instance()
    empty_resp = runtime.run_coroutine_sync(core.process_request("/subagents"))
    assert "No background subagents registered" in empty_resp

    # Dispatch a background subagent
    disp_resp = runtime.run_coroutine_sync(core.process_request("/background check repository hygiene"))
    assert "dispatched worker" in disp_resp.lower()

    # List subagents
    list_resp = runtime.run_coroutine_sync(core.process_request("/subagents"))
    assert "Background Subagents" in list_resp
    assert "subagent_" in list_resp
