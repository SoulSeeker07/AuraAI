"""
Unit Tests for Personal OS Gate G5 (Restart Persistence & Lifecycle Integration)
Location: tests/test_personal_os_g5.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from personal_os.state_store import PersonalOSStateStore, PersonalOSTrigger
from personal_os.daily_context import DailyContextEngine
from personal_os.workspace_search import WorkspaceSearchEngine
from autonomy.trigger_registry import TriggerRegistry
from autonomy.models import Trigger, TriggerType, TriggerState


def test_personal_os_restart_persistence_lifecycle_ac4():
    """AC4: Personal OS state persists across system restarts and re-arms routines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "personal_os.db"
        triggers_json_path = Path(tmpdir) / "triggers.json"

        # ── Session 1: User configures Personal OS ─────────────────────────
        store_s1 = PersonalOSStateStore(db_path=db_path)
        PersonalOSStateStore._instance = store_s1

        store_s1.set_preference("user_timezone", "Asia/Kolkata")
        store_s1.set_preference(
            "tasks_list",
            [
                {"task_id": "persist_task_1", "title": "Implement M26 Personal OS", "priority": "CRITICAL"},
            ],
        )

        trig1 = PersonalOSTrigger(
            trigger_id="trig_morning_standup",
            name="morning_standup",
            goal_text="Review git commits and summarize yesterday's tasks",
            schedule="0 9 * * *",
            template_vars={"project": "AuraAI"},
        )
        store_s1.save_trigger(trig1)

        # ── Session 2: Full System Restart ─────────────────────────────────
        # Reset in-memory singletons to simulate process termination
        PersonalOSStateStore.reset_instance()
        WorkspaceSearchEngine.reset_instance()

        # Re-open state store from persistent DB path
        store_s2 = PersonalOSStateStore.get_instance(db_path=db_path)

        # 1. Verify preferences restored
        assert store_s2.get_preference("user_timezone") == "Asia/Kolkata"
        tasks = store_s2.get_preference("tasks_list", [])
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Implement M26 Personal OS"

        # 2. Verify stored triggers restored
        stored_triggers = store_s2.list_triggers(enabled_only=True)
        assert len(stored_triggers) == 1
        loaded_trig = stored_triggers[0]
        assert loaded_trig.trigger_id == "trig_morning_standup"
        assert loaded_trig.name == "morning_standup"
        assert loaded_trig.template_vars == {"project": "AuraAI"}

        # 3. Verify real AuraCore._init_personal_os() re-arms triggers into trigger_registry
        from core.aura_core import AuraCore
        import shutil

        core = AuraCore.__new__(AuraCore)
        core.project_root = Path(tmpdir)
        (Path(tmpdir) / "storage").mkdir(parents=True, exist_ok=True)
        shutil.copy(db_path, Path(tmpdir) / "storage" / "personal_os.db")
        
        core.components = {}
        core.trigger_registry = TriggerRegistry(storage_path=triggers_json_path)

        # Call REAL production initialization method
        core._init_personal_os()

        from core.aura_core import AuraCoreStatus
        assert core.components["personal_os"].status == AuraCoreStatus.READY
        armed_triggers = core.trigger_registry.list_triggers(enabled_only=True)
        assert len(armed_triggers) == 1
        assert armed_triggers[0].trigger_id == "trig_morning_standup"
        assert armed_triggers[0].state == TriggerState.ARMED
        assert armed_triggers[0].cron_schedule == "0 9 * * *"

        # 4. Verify Daily Context Engine synthesizes immediately without warm-up
        ctx = core.daily_context_engine.get_daily_context()
        assert any(t.title == "Implement M26 Personal OS" for t in ctx.tasks)
        assert any("morning_standup" in t.title for t in ctx.tasks)


def test_personal_os_state_store_schema_migration_version_bump():
    """Verify PersonalOSStateStore executes migrations cleanly when schema version bumps."""
    import sqlite3
    from src.personal_os import state_store as ss_mod

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "migrated.db"

        # 1. Create a v1 database manually with version=1 recorded
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);")
        conn.execute("INSERT INTO schema_version VALUES (1, '2026-08-01T00:00:00Z');")
        conn.execute("""
            CREATE TABLE personal_os_triggers (
                trigger_id TEXT PRIMARY KEY, name TEXT UNIQUE, goal_text TEXT,
                schedule TEXT, enabled INTEGER, created_at TEXT, last_fired_at TEXT,
                run_count INTEGER, last_result_summary TEXT, template_vars TEXT, metadata TEXT
            );
        """)
        conn.execute("CREATE TABLE personal_os_preferences (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);")
        conn.commit()
        conn.close()

        # 2. Simulate schema version bump to v2 with a registered migrator
        original_ver = ss_mod.CURRENT_SCHEMA_VERSION
        try:
            ss_mod.CURRENT_SCHEMA_VERSION = 2
            PersonalOSStateStore.CURRENT_SCHEMA_VERSION = 2
            
            # Define migration hook for v2: adds extra column to triggers
            def _migrate_to_v2(self, c):
                c.execute("ALTER TABLE personal_os_triggers ADD COLUMN execution_tag TEXT DEFAULT 'default';")
            
            setattr(PersonalOSStateStore, "_migrate_to_v2", _migrate_to_v2)

            # Open state store -> must execute _migrate_to_v2 and update schema_version to 2
            store = PersonalOSStateStore(db_path=db_path)

            with store._get_connection() as c:
                row = c.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;").fetchone()
                assert row["version"] == 2

                # Verify column was added by migration
                c.execute("SELECT execution_tag FROM personal_os_triggers LIMIT 1;")
        finally:
            ss_mod.CURRENT_SCHEMA_VERSION = original_ver
            PersonalOSStateStore.CURRENT_SCHEMA_VERSION = original_ver
            if hasattr(PersonalOSStateStore, "_migrate_to_v2"):
                delattr(PersonalOSStateStore, "_migrate_to_v2")
