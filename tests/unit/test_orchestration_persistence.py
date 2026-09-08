"""
Unit tests for OrchestrationStore and MasterOrchestrator Crash-Resume Idempotency.
Location: tests/unit/test_orchestration_persistence.py

Verifies:
1. High-risk task interrupted during 'executing' fails closed on fresh-process resume:
   - Does NOT re-dispatch.
   - Transitions to 'interrupted' in SQLite.
   - Session transitions to 'suspended' in SQLite.
   - Invokes existing ActionPlanConfirmation / ConfirmationRequiredEvent mechanism.
2. Medium-risk task interrupted during 'executing' also fails closed (no silent fallback).
3. Low-risk task interrupted during 'executing' safely re-queues to 'pending' and completes.
4. Completed tasks in SQLite are pruned from re-execution on resume (idempotency).
"""

import pytest
import sqlite3
from pathlib import Path

from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.orchestration_store import OrchestrationStore
from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole
from core.orchestration.confirmation import ActionPlanConfirmation
from core.orchestration.execution_events import ConfirmationRequiredEvent
from core.orchestration.agent_session import AgentSession
from core.orchestration.request_source import RequestSource
from core.planning.execution_result import ExecutionResult


@pytest.mark.asyncio
async def test_crash_resume_high_risk_interrupted_fails_closed(tmp_path):
    """
    Simulate a process crash while a HIGH-risk task is in state 'executing'.
    Assert that resuming from a fresh orchestrator instance reading directly
    from SQLite:
    (a) Discards prior in-memory instances and starts from a fresh process/orchestrator.
    (b) Does NOT silently re-dispatch the task (verified via execution backend spy).
    (c) Sets task status to 'interrupted' in SQLite.
    (d) Sets session status to 'suspended' in SQLite.
    (e) Invokes the existing ActionPlanConfirmation and fires ConfirmationRequiredEvent.
    """
    db_file = tmp_path / "Memory.db"

    # --- PROCESS 1: Pre-Crash Initialization & Dispatch ---
    store = OrchestrationStore(db_path=db_file)
    session_id = "sess_crash_high_01"
    goal = "Perform high-risk credential audit and file wipe"
    store.register_session(session_id, goal=goal)

    st_high = SubTask(
        task_id="task_delete_01",
        title="Delete Sensitive File",
        required_role=PlannerRole.CODEACT,
        capability="file.delete",
        description="Delete file",
        parameters={"path": "sensitive.txt"},
        risk_tier="HIGH",
    )
    store.register_initial_tasks(session_id, [st_high])

    # Simulate execution start right before crash:
    store.update_task_status(session_id, "task_delete_01", status="executing", increment_attempt=True)

    # Verify disk state before crash:
    with sqlite3.connect(str(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, attempt_count FROM orchestration_tasks WHERE session_id = ? AND task_id = ?;",
            (session_id, "task_delete_01"),
        ).fetchone()
        assert row["status"] == "executing"
        assert row["attempt_count"] == 1

    # --- SIMULATE CRASH: Destroy all in-memory references from Process 1 ---
    del store

    # --- PROCESS 2: Fresh-Process Restart ---
    fresh_orchestrator = MasterOrchestrator(memory_db_path=db_file)

    # Register sink to verify typed execution lifecycle events
    emitted_events = []
    fresh_orchestrator.set_execution_sink(emitted_events.append)

    # Attach backend spy to detect any unexpected dispatch attempts
    dispatched_backend_calls = []
    async def spy_execute(task_id, subtask, decision, context):
        dispatched_backend_calls.append(task_id)
        return ExecutionResult(success=True, planner="mock", goal=subtask.title)

    fresh_orchestrator._execute_level_task = spy_execute

    # Resume the crashed session from fresh database
    result = await fresh_orchestrator.resume_session(session_id)

    # Requirement 1 & 2: Execution backend must NOT have been called (no silent re-dispatch)
    assert len(dispatched_backend_calls) == 0, f"Backend dispatch was unexpectedly called: {dispatched_backend_calls}"
    assert result.success is False
    assert result.data.get("is_suspended") is True

    # Database verification on disk:
    with sqlite3.connect(str(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        task_row = conn.execute(
            "SELECT status, risk_tier, attempt_count FROM orchestration_tasks WHERE session_id = ? AND task_id = ?;",
            (session_id, "task_delete_01"),
        ).fetchone()
        assert task_row["status"] == "interrupted"
        assert task_row["risk_tier"] == "HIGH"
        # Attempt count must NOT have increased
        assert task_row["attempt_count"] == 1

        session_row = conn.execute(
            "SELECT status FROM orchestration_sessions WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        assert session_row["status"] == "suspended"

    # Requirement 3: Existing ActionPlanConfirmation mechanism fired
    pending_conf = fresh_orchestrator._last_session.pending_confirmation
    assert isinstance(pending_conf, ActionPlanConfirmation)
    assert pending_conf.session_id == session_id
    assert pending_conf.action_plan.plan_id == "plan_resume_task_delete_01"
    assert "interrupted mid-flight" in pending_conf.prompt
    assert "Delete Sensitive File" in pending_conf.prompt
    assert pending_conf.resolved is False

    # Typed event fired for UI / observers via execution sink
    conf_events = [e for e in emitted_events if isinstance(e, ConfirmationRequiredEvent)]
    assert len(conf_events) == 1
    assert conf_events[0].session_id == session_id
    assert conf_events[0].task_id == "task_delete_01"
    assert conf_events[0].plan_id == "plan_resume_task_delete_01"


@pytest.mark.asyncio
async def test_crash_resume_medium_risk_interrupted_fails_closed(tmp_path):
    """
    Verify that MEDIUM-risk tasks also fail closed on crash-resume
    rather than silently falling through to automatic re-dispatch.
    """
    db_file = tmp_path / "Memory.db"

    # Process 1 setup:
    store = OrchestrationStore(db_path=db_file)
    session_id = "sess_crash_med_01"
    goal = "Execute medium-risk environment modification"
    store.register_session(session_id, goal=goal)

    st_med = SubTask(
        task_id="task_proc_kill_01",
        title="Terminate Application Process",
        required_role=PlannerRole.DESKTOP,
        capability="app_close",
        description="Close window",
        parameters={"app_name": "notepad"},
        risk_tier="MEDIUM",
    )
    store.register_initial_tasks(session_id, [st_med])
    store.update_task_status(session_id, "task_proc_kill_01", status="executing", increment_attempt=True)

    # Crash & discard:
    del store

    # Process 2 fresh restart:
    fresh_orchestrator = MasterOrchestrator(memory_db_path=db_file)
    emitted_events = []
    fresh_orchestrator.set_execution_sink(emitted_events.append)

    dispatched_backend_calls = []
    async def spy_execute(task_id, subtask, decision, context):
        dispatched_backend_calls.append(task_id)
        return ExecutionResult(success=True, planner="mock", goal=subtask.title)

    fresh_orchestrator._execute_level_task = spy_execute

    result = await fresh_orchestrator.resume_session(session_id)

    # Backend was not invoked
    assert len(dispatched_backend_calls) == 0
    assert result.success is False
    assert result.data.get("is_suspended") is True

    with sqlite3.connect(str(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, risk_tier FROM orchestration_tasks WHERE session_id = ? AND task_id = ?;",
            (session_id, "task_proc_kill_01"),
        ).fetchone()
        assert row["status"] == "interrupted"
        assert row["risk_tier"] == "MEDIUM"

        session_row = conn.execute(
            "SELECT status FROM orchestration_sessions WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        assert session_row["status"] == "suspended"

    assert isinstance(fresh_orchestrator._last_session.pending_confirmation, ActionPlanConfirmation)
    conf_events = [e for e in emitted_events if isinstance(e, ConfirmationRequiredEvent)]
    assert len(conf_events) == 1
    assert conf_events[0].task_id == "task_proc_kill_01"


@pytest.mark.asyncio
async def test_crash_resume_low_risk_interrupted_safely_requeues(tmp_path):
    """
    Verify that a LOW-risk (read-only / idempotent) task interrupted during
    'executing' safely re-queues to 'pending' on resume and executes without prompting.
    """
    db_file = tmp_path / "Memory.db"

    # Process 1 setup:
    store = OrchestrationStore(db_path=db_file)
    session_id = "sess_crash_low_01"
    goal = "Read user preference baseline"
    store.register_session(session_id, goal=goal)

    st_low = SubTask(
        task_id="task_read_01",
        title="Read Memory Preference",
        required_role=PlannerRole.MEMORY,
        capability="memory.read",
        description="Recall baseline",
        parameters={"key": "theme"},
        risk_tier="LOW",
    )
    store.register_initial_tasks(session_id, [st_low])
    store.update_task_status(session_id, "task_read_01", status="executing", increment_attempt=1)

    # Before resume, verify it is 'executing':
    with sqlite3.connect(str(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status FROM orchestration_tasks WHERE session_id = ? AND task_id = ?;",
            (session_id, "task_read_01"),
        ).fetchone()
        assert row["status"] == "executing"

    # Crash & discard:
    del store

    # Process 2 fresh restart:
    fresh_orchestrator = MasterOrchestrator(memory_db_path=db_file)
    emitted_events = []
    fresh_orchestrator.set_execution_sink(emitted_events.append)

    # Backend spy / mock:
    dispatched_backend_calls = []
    async def mock_execute(task_id, subtask, decision, context):
        dispatched_backend_calls.append(task_id)
        return ExecutionResult(
            success=True,
            planner="mock",
            goal=subtask.title,
            observations=["Read successful"],
            data={"theme": "dark"},
        )

    fresh_orchestrator._execute_level_task = mock_execute

    result = await fresh_orchestrator.resume_session(session_id)

    assert result.success is True
    # Confirm LOW-risk task WAS re-dispatched to backend
    assert dispatched_backend_calls == ["task_read_01"]

    # Confirm no prompt / confirmation was triggered
    assert fresh_orchestrator._last_session.pending_confirmation is None
    conf_events = [e for e in emitted_events if isinstance(e, ConfirmationRequiredEvent)]
    assert len(conf_events) == 0

    # Confirm disk state is now completed:
    with sqlite3.connect(str(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        task_row = conn.execute(
            "SELECT status FROM orchestration_tasks WHERE session_id = ? AND task_id = ?;",
            (session_id, "task_read_01"),
        ).fetchone()
        assert task_row["status"] == "completed"

        session_row = conn.execute(
            "SELECT status FROM orchestration_sessions WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        assert session_row["status"] == "completed"


@pytest.mark.asyncio
async def test_crash_resume_prunes_already_completed_tasks(tmp_path):
    """
    Verify that in a multi-task DAG, tasks that already completed prior to a crash
    are recorded in completed_ids and NOT re-dispatched upon resume.
    """
    db_file = tmp_path / "Memory.db"
    store = OrchestrationStore(db_path=db_file)

    session_id = "sess_prune_01"
    goal = "Two-stage pipeline"
    store.register_session(session_id, goal=goal)

    st1 = SubTask(
        task_id="st_1",
        title="Step 1 Completed",
        required_role=PlannerRole.MEMORY,
        capability="memory.read",
        risk_tier="LOW",
        status="completed",
    )
    st2 = SubTask(
        task_id="st_2",
        title="Step 2 Pending",
        required_role=PlannerRole.DESKTOP,
        capability="browser.search",
        risk_tier="LOW",
        dependencies=["st_1"],
        status="pending",
    )
    store.register_initial_tasks(session_id, [st1, st2])
    store.update_task_status(session_id, "st_1", status="completed", result={"done": True})

    fresh_orchestrator = MasterOrchestrator(memory_db_path=db_file)

    dispatched_tasks = []
    async def mock_execute(task_id, subtask, decision, context):
        dispatched_tasks.append(task_id)
        return ExecutionResult(success=True, planner="mock", goal=subtask.title, observations=["Done"], data={})

    fresh_orchestrator._execute_level_task = mock_execute

    result = await fresh_orchestrator.resume_session(session_id)

    assert result.success is True
    # Invariant: st_1 was already completed on disk, so it MUST NOT be in dispatched_tasks!
    assert "st_1" not in dispatched_tasks
    assert "st_2" in dispatched_tasks
    assert dispatched_tasks == ["st_2"]
