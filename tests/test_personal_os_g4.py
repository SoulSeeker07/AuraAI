"""
Unit Tests for Personal OS Gate G4 (One-Command Trigger Automation)
Location: tests/test_personal_os_g4.py
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
import pytest

from personal_os.trigger_templates import TriggerTemplateRegistry, TriggerTemplate
from personal_os.state_store import PersonalOSStateStore, PersonalOSTrigger
from autonomy.trigger_scheduler import TriggerScheduler
from autonomy.trigger_registry import TriggerRegistry
from autonomy.models import Trigger, TriggerType, TriggerState
from desktop.native.security.audit_logger import SecurityAuditLogger
from core.orchestration.request_source import RequestSource


def test_trigger_template_registry_and_interpolation():
    """Verify built-in trigger templates and dynamic variable substitution."""
    reg = TriggerTemplateRegistry()
    templates = reg.list_templates()
    assert len(templates) >= 4

    standup = reg.get("standup_prep")
    assert standup is not None

    goal = standup.build_goal({"current_project": "AuraAI", "today_date": "2026-08-21"})
    assert "AuraAI" in goal
    assert "2026-08-21" in goal
    assert "standup" in goal.lower()

    # Instantiation
    trigger = reg.instantiate("standup_prep", name="my_standup", schedule="0 9 * * 1-5")
    assert trigger.name == "my_standup"
    assert trigger.schedule == "0 9 * * 1-5"
    assert "AuraAI" in trigger.goal_text


@pytest.mark.asyncio
async def test_trigger_scheduler_autonomous_goal_dispatch_ac3():
    """AC3: TriggerScheduler fires a goal string through MasterOrchestrator with audit logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        audit_log_path = Path(tmpdir) / "audit_ledger.jsonl"

        state_store = PersonalOSStateStore(db_path=db_path)
        PersonalOSStateStore._instance = state_store

        audit_logger = SecurityAuditLogger.get_instance(log_path=audit_log_path)
        SecurityAuditLogger._instance = audit_logger

        t_registry = TriggerRegistry(storage_path=Path(tmpdir) / "triggers.json")
        scheduler = TriggerScheduler(
            registry=t_registry,
            state_store=state_store,
            audit_logger=audit_logger,
        )

        # Create trigger with action_goal and empty steps execution_map
        test_trigger = Trigger(
            trigger_id="trig_auto_standup",
            trigger_type=TriggerType.SCHEDULED,
            action_goal="Synthesize daily context and prioritize today's agenda",
            execution_map={},
            state=TriggerState.ARMED,
            dedup_key="test_auto_standup",
        )
        t_registry.register_trigger(test_trigger)

        # Save to PersonalOSStateStore
        p_trig = PersonalOSTrigger(
            trigger_id="trig_auto_standup",
            name="auto_standup",
            goal_text="Synthesize daily context and prioritize today's agenda",
            schedule="0 9 * * *",
        )
        state_store.save_trigger(p_trig)

        # Fire trigger
        fired = await scheduler.fire_trigger(test_trigger)
        assert fired is True

        # Wait for all background tasks to complete
        if scheduler._running_tasks:
            await asyncio.gather(*list(scheduler._running_tasks))

        # Verify state store run update
        updated_trig = state_store.get_trigger("trig_auto_standup")
        assert updated_trig is not None
        assert updated_trig.run_count >= 1
        assert updated_trig.last_fired_at is not None

        # Verify Audit Ledger record
        assert audit_log_path.exists()
        content = audit_log_path.read_text(encoding="utf-8")
        assert "AUTONOMOUS_GOAL_DISPATCH" in content
        assert "trigger_autonomous" in content


@pytest.mark.asyncio
async def test_trigger_scheduler_fail_closed_on_audit_logger_failure():
    """Verify that if the audit logger fails to record, dispatch is immediately BLOCKED (fail-closed)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        t_registry = TriggerRegistry(storage_path=Path(tmpdir) / "triggers.json")

        class BrokenAuditLogger:
            def log_event(self, *args, **kwargs):
                raise IOError("Simulated disk write failure on audit sink")

        scheduler = TriggerScheduler(
            registry=t_registry,
            audit_logger=BrokenAuditLogger(),
        )

        trigger = Trigger(
            trigger_id="trig_fail_closed",
            trigger_type=TriggerType.SCHEDULED,
            action_goal="Synthesize daily context and prioritize today's agenda",
            execution_map={},
            state=TriggerState.ARMED,
            dedup_key="test_fail_closed",
        )
        t_registry.register_trigger(trigger)

        fired = await scheduler.fire_trigger(trigger)
        assert fired is True

        if scheduler._running_tasks:
            await asyncio.gather(*list(scheduler._running_tasks))

        # Must have been BLOCKED, never RUNNING or VERIFIED
        updated_trig = t_registry.get_trigger("trig_fail_closed")
        assert updated_trig is not None
        assert updated_trig.state == TriggerState.BLOCKED
