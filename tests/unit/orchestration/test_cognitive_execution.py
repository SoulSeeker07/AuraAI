"""
Unit tests for TaskWorkingMemory and WorldStateObserver (Continuous Cognitive Execution Engine).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from core.orchestration.task_working_memory import TaskWorkingMemory
from core.orchestration.world_state_observer import WorldStateObserver


def test_task_working_memory_lifecycle():
    mem = TaskWorkingMemory(
        goal="open chrome and search youtube and play top python video"
    )
    assert mem.step_count == 0
    assert not mem.is_complete

    mem.record_step(
        capability="app_open",
        target="Chrome",
        goal="open chrome",
        success=True,
        observations=["✓ Chrome is open."],
    )
    assert mem.step_count == 1
    assert len(mem.completed_actions) == 1
    assert mem.completed_actions[0].capability == "app_open"

    mem.update_world_state(
        {"focused_window": "Google Chrome", "browser_url": "https://www.youtube.com"}
    )
    assert mem.current_world_state.get("browser_url") == "https://www.youtube.com"

    mem.mark_complete(success=True, final_observation="Played YouTube video")
    assert mem.is_complete
    assert mem.success

    summary = mem.get_summary()
    assert summary["steps_completed"] == 1
    assert summary["success"] is True


@pytest.mark.asyncio
async def test_world_state_observer_async():
    observer = WorldStateObserver.get_instance()
    snap = await observer.observe_async(domain="desktop")
    assert "focused_window" in snap
    assert "running_processes_count" in snap
