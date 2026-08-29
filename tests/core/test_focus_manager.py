"""
Unit tests for FocusManager (M32)
Location: tests/core/test_focus_manager.py

Tests run against a temp SQLite DB — no network, no LLM calls.
Covers: create, switch, pause, resume, fuzzy-match dedup, update_state,
        archive_stale, pending notification queue + dedupe.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Fixture: isolated FocusManager per test ───────────────────────────────────

@pytest.fixture
def fm(tmp_path):
    """Return a fresh FocusManager backed by a temp DB for each test."""
    from core.focus_manager import FocusManager

    db = tmp_path / "focus_test.db"
    FocusManager.reset_instance()
    manager = FocusManager.get_instance(db_path=db)
    yield manager
    FocusManager.reset_instance()


# ── Tests: basic CRUD ─────────────────────────────────────────────────────────

class TestCreateAndSwitch:
    def test_create_sets_current_focus(self, fm):
        thread = fm.create("api_refactor", {"step": 1})
        assert thread.task_id == "api_refactor"
        assert thread.status == "active"
        assert fm.get_current().task_id == "api_refactor"

    def test_create_two_then_switch(self, fm):
        fm.create("api_refactor", {})
        fm.create("documentation", {})  # creates second WITHOUT fuzzy match (different names)
        # Currently documentation is active, api_refactor was paused by create
        fm.switch_to("api_refactor")
        current = fm.get_current()
        assert current.task_id == "api_refactor"
        assert current.status == "active"

    def test_switch_pauses_previous(self, fm):
        fm.create("api_refactor_work", {})
        fm.create("documentation_writing", {})
        fm.switch_to("api_refactor_work")

        all_threads = {t.task_id: t for t in fm.list_active()}
        assert all_threads["api_refactor_work"].status == "active"
        assert all_threads["documentation_writing"].status == "paused"


    def test_switch_to_nonexistent_creates_it(self, fm):
        thread = fm.switch_to("brand_new_task")
        assert thread.task_id == "brand_new_task"
        assert fm.get_current().task_id == "brand_new_task"


class TestPauseResume:
    def test_pause_changes_status(self, fm):
        fm.create("work", {})
        fm.pause("work")
        threads = {t.task_id: t for t in fm.list_active()}
        assert threads["work"].status == "paused"

    def test_resume_restores_active(self, fm):
        fm.create("work", {})
        fm.pause("work")
        resumed = fm.resume("work")
        assert resumed.status == "active"
        assert fm.get_current().task_id == "work"

    def test_resume_updates_last_touched(self, fm):
        fm.create("ts_task", {})
        fm.pause("ts_task")
        before = datetime.now(timezone.utc)
        time.sleep(0.01)
        fm.resume("ts_task")
        current = fm.get_current()
        touched = datetime.fromisoformat(current.last_touched)
        assert touched >= before


class TestUpdateState:
    def test_state_merges_correctly(self, fm):
        fm.create("coding", {"files": ["main.py"]})
        fm.update_state("coding", {"last_summary": "Added tests", "vars": {"x": 1}})
        thread = fm._load_thread("coding")
        assert thread.state["files"] == ["main.py"]        # original key preserved
        assert thread.state["last_summary"] == "Added tests"  # new key added
        assert thread.state["vars"] == {"x": 1}

    def test_update_nonexistent_does_not_raise(self, fm):
        # Should log a warning but not raise
        fm.update_state("ghost_task", {"foo": "bar"})


class TestGetCurrentStateSnippet:
    def test_snippet_is_empty_without_focus(self, fm):
        assert fm.get_current_state_snippet() == ""

    def test_snippet_contains_task_id(self, fm):
        fm.create("my_project", {"last_summary": "wrote tests"})
        snippet = fm.get_current_state_snippet()
        assert "my_project" in snippet
        assert "### Current Focus Thread" in snippet


# ── Tests: fuzzy task-ID dedup ────────────────────────────────────────────────

class TestFuzzyMatch:
    def test_exact_duplicate_resolves_to_existing(self, fm):
        """Exact same slug always merges regardless of length."""
        original = fm.create("python_project_refactor", {})
        resolved = fm.create("python_project_refactor", {})
        assert resolved.task_id == original.task_id
        assert len(fm.list_active()) == 1

    def test_near_duplicate_long_slug_resolves(self, fm):
        """Long slugs (≥16 chars) use the 0.75 threshold — near-duplicates merge."""
        fm.create("python_project_refactor", {})
        # "python project refactor" → slug "python_project_refactor" after replace
        resolved = fm.create("python_project_refactoring", {})
        # ratio("python_project_refactor","python_project_refactoring") ≈ 0.98 → merges
        assert resolved.task_id == "python_project_refactor"
        assert len(fm.list_active()) == 1

    def test_short_distinct_slugs_do_not_merge(self, fm):
        """
        Regression: short slugs ('fix_bug' vs 'fix_build') must NOT merge even
        though their SequenceMatcher ratio is ~0.82 (above the old flat 0.75 threshold).
        With the length-weighted threshold (0.90 for len<8), they must stay separate.
        """
        fm.create("fix_bug", {})
        fm.create("fix_bld", {})  # ratio ≈ 0.86, below 0.90 short threshold → new thread
        assert len(fm.list_active()) == 2

    def test_clearly_different_creates_new(self, fm):
        """Unrelated slugs always create separate threads."""
        fm.create("api_refactor_backend", {})
        fm.create("devops_pipeline_deploy", {})
        assert len(fm.list_active()) == 2

    def test_fuzzy_threshold_boundary_long(self, fm):
        """Completely dissimilar slugs create new threads (long)."""
        fm.create("authentication_service", {})
        fm.create("data_pipeline_etl_v2", {})  # ratio near 0 → new thread
        assert len(fm.list_active()) == 2

    def test_short_exact_match_still_merges(self, fm):
        """Exact short slug match (ratio=1.0) still merges — threshold only guards grey zone."""
        fm.create("bug", {})
        resolved = fm.create("bug", {})
        assert resolved.task_id == "bug"
        assert len(fm.list_active()) == 1


# ── Tests: pending notification queue ────────────────────────────────────────

class TestPendingNotifications:
    def test_enqueue_and_drain(self, fm):
        fm.create("task_x", {})
        fm.enqueue_notification("task_x", "Memory usage at 90%", "medium")
        notifs = fm.drain_pending_notifications()
        assert len(notifs) == 1
        assert notifs[0].message == "Memory usage at 90%"
        assert notifs[0].delivered is True

    def test_dedupe_same_state_hash_not_re_delivered(self, fm):
        fm.create("task_x", {})
        fm.enqueue_notification("task_x", "Same message", "low")
        fm.drain_pending_notifications()  # first drain → delivered=1

        # Enqueue identical message again — must be skipped (same state_hash)
        fm.enqueue_notification("task_x", "Same message", "low")
        notifs = fm.drain_pending_notifications()
        assert len(notifs) == 0  # dedupe: not re-surfaced

    def test_changed_message_is_re_surfaced(self, fm):
        fm.create("task_x", {})
        fm.enqueue_notification("task_x", "Old message", "low")
        fm.drain_pending_notifications()

        fm.enqueue_notification("task_x", "Updated message", "low")  # different hash
        notifs = fm.drain_pending_notifications()
        assert len(notifs) == 1
        assert notifs[0].message == "Updated message"

    def test_drain_respects_cap_of_3(self, fm):
        fm.create("task_x", {})
        for i in range(6):
            fm.enqueue_notification("task_x", f"Alert {i}", "low")
        drained = fm.drain_pending_notifications()
        assert len(drained) <= 3

    def test_low_severity_does_not_touch_current_focus(self, fm):
        fm.create("task_a", {})
        fm.enqueue_notification("task_b", "Minor: disk 80%", "low")
        # Current focus must still be task_a
        assert fm.get_current().task_id == "task_a"


# ── Tests: stale archival ────────────────────────────────────────────────────

class TestArchiveStale:
    def test_archive_removes_old_threads(self, fm, tmp_path):
        fm.create("stale_task", {})
        # Manually backdate last_touched to simulate staleness
        with fm._db_lock, fm._get_connection() as conn:
            old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
            conn.execute("UPDATE focus_threads SET last_touched=? WHERE task_id=?", (old_ts, "stale_task"))
            conn.commit()

        with patch.object(fm, "_persist_to_long_term_memory") as mock_persist:
            archived = fm.archive_stale(max_age_hours=24)
            assert archived == 1
            mock_persist.assert_called_once()

        assert fm._load_thread("stale_task") is None

    def test_fresh_threads_not_archived(self, fm):
        fm.create("fresh_task", {})
        archived = fm.archive_stale(max_age_hours=24)
        assert archived == 0
        assert fm._load_thread("fresh_task") is not None

    def test_archive_clears_current_focus_if_stale(self, fm):
        fm.create("old_focus", {})
        assert fm._current_focus == "old_focus"
        with fm._db_lock, fm._get_connection() as conn:
            old_ts = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
            conn.execute("UPDATE focus_threads SET last_touched=? WHERE task_id=?", (old_ts, "old_focus"))
            conn.commit()

        with patch.object(fm, "_persist_to_long_term_memory"):
            fm.archive_stale(max_age_hours=1)

        assert fm._current_focus is None
