"""
Unit Tests for Personal OS Gate G2 (Daily Context Engine)
Location: tests/test_personal_os_g2.py
"""

from __future__ import annotations

import time
import pytest
from pathlib import Path
import tempfile

from src.personal_os.models import DailyContext, TaskItem, CalendarMeeting, DeadlineItem
from src.personal_os.state_store import PersonalOSStateStore
from src.personal_os.daily_context import DailyContextEngine
from src.core.backends.adapters.personal_os_backend import PersonalOSBackendAdapter
from src.core.orchestration.master_orchestrator import MasterOrchestrator


def test_daily_context_model_formatting():
    """Verify DailyContext dataclass formatting and priority sorting."""
    ctx = DailyContext(
        date="2026-08-21",
        meetings=[
            CalendarMeeting(
                title="Sprint Standup",
                start_time="09:30",
                end_time="10:00",
                location="Google Meet",
            )
        ],
        tasks=[
            TaskItem(
                task_id="t1",
                title="Normal task",
                priority="NORMAL",
            ),
            TaskItem(
                task_id="t2",
                title="Urgent critical fix",
                priority="CRITICAL",
            ),
            TaskItem(
                task_id="t3",
                title="High priority review",
                priority="HIGH",
            ),
        ],
        deadlines=[
            DeadlineItem(
                title="M26 Release",
                due_date="2026-08-21",
                is_overdue=False,
            )
        ],
    )

    summary = ctx.format_summary()
    assert "Sprint Standup" in summary
    assert "Urgent critical fix" in summary
    # CRITICAL should precede NORMAL in rendered output
    pos_critical = summary.find("Urgent critical fix")
    pos_normal = summary.find("Normal task")
    assert pos_critical < pos_normal


def test_daily_context_engine_synthesis():
    """Verify DailyContextEngine synthesizes context with state store items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        store = PersonalOSStateStore(db_path=db_path)

        # Store test tasks and calendar items
        store.set_preference(
            "tasks_list",
            [
                {"task_id": "test_t1", "title": "Implement G3 workspace search", "priority": "HIGH"},
                {"task_id": "test_t2", "title": "Completed task", "status": "COMPLETED"},
            ],
        )

        store.set_preference(
            "calendar_events_2026-08-21",
            [{"title": "Architecture Review", "start_time": "14:00", "end_time": "15:00"}],
        )

        # Add stored triggers (one weekday 1-5, one Friday-only 5)
        from src.personal_os.state_store import PersonalOSTrigger
        store.save_trigger(
            PersonalOSTrigger(
                trigger_id="trig_weekday",
                name="weekday_standup",
                goal_text="Standup",
                schedule="0 9 * * 1-5",
            )
        )
        store.save_trigger(
            PersonalOSTrigger(
                trigger_id="trig_friday_only",
                name="friday_retro",
                goal_text="Retro",
                schedule="0 17 * * 5",
            )
        )

        store.save_trigger(
            PersonalOSTrigger(
                trigger_id="trig_monthly_15th",
                name="monthly_payroll_audit",
                goal_text="Audit payroll",
                schedule="0 9 15 * *",
            )
        )

        store.save_trigger(
            PersonalOSTrigger(
                trigger_id="trig_15th_or_monday",
                name="monday_or_15th_sync",
                goal_text="Sync team",
                schedule="0 9 15 * 1",
            )
        )

        engine = DailyContextEngine(state_store=store)
        
        # 2026-08-21 is Friday the 21st (DOW=5, DOM=21)
        ctx_fri = engine.get_daily_context(target_date="2026-08-21")
        assert any("weekday_standup" in t.title for t in ctx_fri.tasks)
        assert any("friday_retro" in t.title for t in ctx_fri.tasks)
        assert not any("monthly_payroll_audit" in t.title for t in ctx_fri.tasks)
        assert not any("monday_or_15th_sync" in t.title for t in ctx_fri.tasks)

        # 2026-08-15 is Saturday the 15th (DOM=15, DOW=6) -> monthly 15th is due, and 15th_or_monday is due (DOM matches)
        ctx_15th = engine.get_daily_context(target_date="2026-08-15")
        assert any("monthly_payroll_audit" in t.title for t in ctx_15th.tasks)
        assert any("monday_or_15th_sync" in t.title for t in ctx_15th.tasks)
        assert not any("weekday_standup" in t.title for t in ctx_15th.tasks)
        assert not any("friday_retro" in t.title for t in ctx_15th.tasks)

        # 2026-08-17 is Monday the 17th (DOM=17, DOW=1) -> monday_or_15th_sync is due (DOW matches), weekday_standup is due
        ctx_mon = engine.get_daily_context(target_date="2026-08-17")
        assert any("weekday_standup" in t.title for t in ctx_mon.tasks)
        assert any("monday_or_15th_sync" in t.title for t in ctx_mon.tasks)
        assert not any("friday_retro" in t.title for t in ctx_mon.tasks)
        assert not any("monthly_payroll_audit" in t.title for t in ctx_mon.tasks)

        # 2026-08-18 is Tuesday the 18th (DOW=2, DOM=18) -> neither DOM nor DOW matches for 15th_or_monday
        ctx_tue = engine.get_daily_context(target_date="2026-08-18")
        assert any("weekday_standup" in t.title for t in ctx_tue.tasks)
        assert not any("friday_retro" in t.title for t in ctx_tue.tasks)
        assert not any("monthly_payroll_audit" in t.title for t in ctx_tue.tasks)
        assert not any("monday_or_15th_sync" in t.title for t in ctx_tue.tasks)


def test_personal_os_backend_adapter():
    """Verify PersonalOSBackendAdapter executes capabilities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        store = PersonalOSStateStore(db_path=db_path)
        adapter = PersonalOSBackendAdapter(state_store=store)

        # 1. Add Task
        res_add = adapter.execute(
            capability="personal_os.task.add",
            goal="Add new feature task",
            arguments={"title": "Write G2 docs", "priority": "HIGH"},
        )
        assert res_add.success is True
        assert "Write G2 docs" in res_add.observations[0]

        # 2. List Tasks
        res_list = adapter.execute(
            capability="personal_os.task.list",
            goal="List tasks",
        )
        assert res_list.success is True
        assert len(res_list.data["tasks"]) == 1

        # 3. Daily Context
        res_ctx = adapter.execute(
            capability="personal_os.daily_context",
            goal="What do I need to do today?",
        )
        assert res_ctx.success is True
        assert res_ctx.planner == "personal_os"
        assert "daily_context" in res_ctx.data
        assert "Write G2 docs" in res_ctx.observations[0]


@pytest.mark.asyncio
async def test_master_orchestrator_e2e_daily_context_ac1():
    """AC1: 'What do I need to do today?' returns structured daily agenda in <2s."""
    orch = MasterOrchestrator()

    start_time = time.perf_counter()
    result = await orch.process_request_async("What do I need to do today?")
    elapsed = time.perf_counter() - start_time

    assert result.success is True
    assert result.planner == "personal_os" or "daily_context" in result.data or len(result.observations) > 0
    assert elapsed < 2.0  # Must be fast under 2 seconds
