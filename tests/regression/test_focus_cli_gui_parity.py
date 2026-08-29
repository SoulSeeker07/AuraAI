"""
CLI/GUI parity regression test for FocusManager (M32)
Location: tests/regression/test_focus_cli_gui_parity.py

Validates that the single AuraCore.process_request() dispatch path produces
identical focus state regardless of which client entrypoint (CLI or GUI) calls it.
Matches the invariant proven in M30.

All LLM calls are mocked — no network required.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_groq_response(text: str):
    """Build a minimal Groq response mock that passes AuraCore's response parsing."""
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    res = MagicMock()
    res.choices = [choice]
    return res


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def isolated_aura(tmp_path):
    """
    Create an isolated AuraCore instance with:
    - Mocked Groq LLM (no network)
    - Temp SQLite DB for FocusManager
    - Singleton reset before/after each test to guarantee isolation
    """
    from src.core.aura_core import AuraCore
    from src.core.focus_manager import FocusManager

    # Reset singletons
    AuraCore.reset_instance()
    FocusManager.reset_instance()

    # Patch LLM to avoid real Groq calls
    with (
        patch("groq.Groq") as MockGroq,
        patch.dict("os.environ", {"GROQ_API_KEY": "gsk_testdummykey1234567890"}),
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_groq_response(
            "Acknowledged."
        )
        MockGroq.return_value = mock_client

        core = AuraCore(config={
            "project_root": str(tmp_path),
            "memory_db_path": str(tmp_path / "Memory.db"),
        })
        # Point FocusManager at tmp DB
        fm_db = tmp_path / "storage" / "focus_threads.db"
        fm_db.parent.mkdir(parents=True, exist_ok=True)
        FocusManager.reset_instance()
        core.focus_manager = FocusManager.get_instance(db_path=fm_db)

        yield core, core.focus_manager

    # Teardown
    AuraCore.reset_instance()
    FocusManager.reset_instance()


# ── Parity tests ──────────────────────────────────────────────────────────────

class TestCLIGUIParity:
    """
    Each test simulates the exact same request coming from CLI then GUI.
    Both code-paths converge on AuraCore.process_request() — assert that
    focus state is identical after each.
    """

    def test_create_task_via_process_request(self, isolated_aura):
        core, fm = isolated_aura

        # Simulate CLI entrypoint call
        asyncio.get_event_loop().run_until_complete(
            core.process_request("start new task api_refactor")
        )
        cli_focus = fm.get_current()

        # Reset current focus pointer but keep DB state
        fm._current_focus = None

        # Simulate GUI entrypoint call with the same message
        asyncio.get_event_loop().run_until_complete(
            core.process_request("start new task api_refactor")
        )
        gui_focus = fm.get_current()

        # Both must resolve to the same thread (fuzzy dedup prevents duplicate creation)
        assert cli_focus is not None
        assert gui_focus is not None
        assert cli_focus.task_id == gui_focus.task_id
        assert len(fm.list_active()) == 1  # only ONE thread, not two

    def test_switch_focus_via_process_request(self, isolated_aura):
        core, fm = isolated_aura

        # Pre-populate two tasks
        fm.create("task_a", {})
        fm.create("task_b", {})

        # CLI: switch back to task_a
        asyncio.get_event_loop().run_until_complete(
            core.process_request("back to task_a")
        )
        cli_focus = fm.get_current()

        # GUI: same switch — focus must already be task_a (idempotent)
        asyncio.get_event_loop().run_until_complete(
            core.process_request("back to task_a")
        )
        gui_focus = fm.get_current()

        assert cli_focus.task_id == "task_a"
        assert gui_focus.task_id == "task_a"

    def test_state_persists_across_entrypoints(self, isolated_aura, tmp_path):
        """
        After CLI writes a focus state update, a GUI call on the same process
        reads the same state from the shared SQLite DB (WAL isolation invariant).
        """
        core, fm = isolated_aura

        fm.create("shared_task", {"step": 0})

        # CLI turn updates state
        asyncio.get_event_loop().run_until_complete(
            core.process_request("continue working on shared_task")
        )

        # State must be updated in DB — readable from any path
        loaded = fm._load_thread("shared_task")
        assert loaded is not None
        # The postamble should have updated last_summary
        assert "last_summary" in loaded.state or "last_user_msg" in loaded.state


class TestInterruptSeverityRouting:
    """Verify that TriggerScheduler routes interrupts correctly via severity gate."""

    def test_high_severity_switches_focus(self, isolated_aura):
        core, fm = isolated_aura
        fm.create("current_work", {})

        from src.autonomy.trigger_scheduler import TriggerScheduler
        from src.autonomy.models import Trigger, TriggerType, TriggerState

        scheduler = TriggerScheduler()

        trigger = Trigger(
            trigger_id="test_high",
            trigger_type=TriggerType.CONDITION,
            action_goal="Critical security alert detected",
            execution_map={"risk_level": "high"},
            state=TriggerState.ARMED,
        )

        asyncio.get_event_loop().run_until_complete(
            scheduler.fire_background_interrupt(
                trigger=trigger,
                new_task_id="security_incident",
                message="Security breach detected — switching focus.",
                aura_core=core,
            )
        )

        current = fm.get_current()
        assert current is not None
        assert current.task_id == "security_incident"

    def test_low_severity_does_not_switch_focus(self, isolated_aura):
        core, fm = isolated_aura
        fm.create("current_work", {})

        from src.autonomy.trigger_scheduler import TriggerScheduler
        from src.autonomy.models import Trigger, TriggerType, TriggerState

        scheduler = TriggerScheduler()

        trigger = Trigger(
            trigger_id="test_low",
            trigger_type=TriggerType.SCHEDULED,
            action_goal="Weekly backup reminder",
            execution_map={"risk_level": "low"},
            state=TriggerState.ARMED,
        )

        asyncio.get_event_loop().run_until_complete(
            scheduler.fire_background_interrupt(
                trigger=trigger,
                new_task_id="backup_task",
                message="Reminder: backup due",
                aura_core=core,
            )
        )

        # Focus must NOT have changed — still current_work
        current = fm.get_current()
        assert current.task_id == "current_work"

        # But a notification must be queued
        notifs = fm.drain_pending_notifications()
        assert len(notifs) == 1
        assert "backup" in notifs[0].message.lower()

    def test_severity_classification_uses_risk_level_enum(self, isolated_aura):
        _, fm = isolated_aura

        from src.autonomy.trigger_scheduler import TriggerScheduler
        from src.autonomy.models import Trigger, TriggerType, TriggerState

        scheduler = TriggerScheduler()

        # CRITICAL via explicit execution_map key
        critical_trigger = Trigger(
            trigger_id="t1", trigger_type=TriggerType.SCHEDULED,
            action_goal="Weekly report", execution_map={"risk_level": "critical"},
            state=TriggerState.ARMED,
        )
        assert scheduler._classify_interrupt_severity(critical_trigger) == "critical"

        # HIGH via keyword scan
        high_trigger = Trigger(
            trigger_id="t2", trigger_type=TriggerType.SCHEDULED,
            action_goal="disk failure detected", execution_map={},
            state=TriggerState.ARMED,
        )
        assert scheduler._classify_interrupt_severity(high_trigger) == "high"

        # LOW via trigger type fallback (no keywords, SCHEDULED)
        low_trigger = Trigger(
            trigger_id="t3", trigger_type=TriggerType.SCHEDULED,
            action_goal="Check weather", execution_map={},
            state=TriggerState.ARMED,
        )
        assert scheduler._classify_interrupt_severity(low_trigger) == "low"
