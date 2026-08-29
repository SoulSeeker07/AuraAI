"""
Unit tests covering single, current, and bulk thread closure in FocusManager and AuraCore.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.focus_manager import FocusManager, FocusThread
from core.aura_core import AuraCore


def test_focus_manager_close_single_thread(tmp_path):
    db_path = tmp_path / "focus_threads.db"
    fm = FocusManager(db_path=db_path)
    fm.create("weather_widget", {}, severity_origin="user")
    fm.create("db_refactor", {}, severity_origin="user")

    assert len(fm.list_active()) == 2
    closed = fm.close_thread("weather_widget")
    assert closed is True

    active = fm.list_active()
    assert len(active) == 1
    assert active[0].task_id == "db_refactor"


def test_focus_manager_close_all_threads(tmp_path):
    db_path = tmp_path / "focus_threads.db"
    fm = FocusManager(db_path=db_path)
    fm.create("task_1", {}, severity_origin="user")
    fm.create("task_2", {}, severity_origin="user")
    fm.create("task_3", {}, severity_origin="user")

    assert len(fm.list_active()) == 3
    count = fm.close_all_threads()
    assert count == 3
    assert len(fm.list_active()) == 0
    assert fm.get_current() is None


def test_aura_core_focus_intent_closing():
    core = MagicMock(spec=AuraCore)
    core.llm_enabled = False
    core.groq_client = None

    intent1 = AuraCore._resolve_focus_intent(core, "close task weather_widget")
    assert intent1["action"] == "close"
    assert intent1["task_id"] == "weather_widget"

    intent2 = AuraCore._resolve_focus_intent(core, "close current task")
    assert intent2["action"] == "close_current"

    intent3 = AuraCore._resolve_focus_intent(core, "close all focus threads")
    assert intent3["action"] == "close_all"
