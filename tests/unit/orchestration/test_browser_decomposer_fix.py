"""
Unit Tests for Browser Task Decomposition & Target URL Resolution Fixes.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.orchestration.task_decomposer import PlannerRole, TaskDecomposer


def test_resolve_browser_target_youtube():
    decomposer = TaskDecomposer()
    site, url, query = decomposer._resolve_browser_target("open chrome and search youtube")
    assert site == "youtube"
    assert url == "https://www.youtube.com"


def test_resolve_browser_target_youtube_with_query():
    decomposer = TaskDecomposer()
    site, url, query = decomposer._resolve_browser_target("search python tutorials on youtube")
    assert site == "youtube"
    assert "youtube.com/results?search_query=" in url
    assert query == "python tutorials"


def test_decompose_open_chrome_and_search_youtube():
    decomposer = TaskDecomposer()
    graph = decomposer.decompose("open chrome and search youtube")
    
    # Clause 1: open chrome (desktop app_open)
    # Clause 2: search youtube (browser subtasks)
    subtask_caps = [t.capability for t in graph.subtasks.values()]
    assert "app_open" in subtask_caps
    assert "browser.navigate" in subtask_caps

    # Verify target_url parameter is passed correctly
    nav_task = [t for t in graph.subtasks.values() if t.capability == "browser.navigate"][0]
    assert nav_task.parameters.get("url") == "https://www.youtube.com"
    assert nav_task.parameters.get("site") == "youtube"


def test_decompose_open_chrome_and_type_and_press_enter():
    decomposer = TaskDecomposer()
    graph = decomposer.decompose("open chrome and type youtube and press enter")
    
    subtask_caps = [t.capability for t in graph.subtasks.values()]
    assert "app_open" in subtask_caps
    assert "keyboard.type" in subtask_caps
    assert "keyboard.press" in subtask_caps

    type_task = [t for t in graph.subtasks.values() if t.capability == "keyboard.type"][0]
    assert type_task.parameters.get("text") == "youtube"

    press_task = [t for t in graph.subtasks.values() if t.capability == "keyboard.press"][0]
    assert press_task.parameters.get("key") == "enter"
