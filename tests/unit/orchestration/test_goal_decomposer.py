"""
Unit Tests — Goal-Oriented Task Decomposer & World Snapshot
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.orchestration.task_decomposer import PlannerRole, TaskDecomposer
from core.orchestration.world_snapshot import (
    DesktopStateSnapshot,
    WorldSnapshotProvider,
)


class TestGoalDecomposer:
    def test_decompose_browser_multi_step_dag(self):
        decomposer = TaskDecomposer()
        decision = MagicMock()
        decision.intent_type.value = "browser"
        decision.world_state = {"running_processes": []}

        graph = decomposer.decompose("Open my Instagram profile", decision=decision)

        assert len(graph.subtasks) == 4
        subtask_roles = [t.required_role for t in graph.subtasks.values()]
        assert all(role == PlannerRole.BROWSER for role in subtask_roles)

        caps = [t.capability for t in graph.subtasks.values()]
        assert "browser.ensure_open" in caps
        assert "browser.navigate" in caps
        assert "browser.check_auth" in caps
        assert "browser.navigate_goal" in caps

    def test_browser_ensure_open_skipped_if_chrome_running(self):
        decomposer = TaskDecomposer()
        decision = MagicMock()
        decision.intent_type.value = "browser"
        decision.world_state = {"running_processes": ["chrome", "code"]}

        graph = decomposer.decompose("Open Instagram profile", decision=decision)

        ensure_task = [
            t for t in graph.subtasks.values() if t.capability == "browser.ensure_open"
        ][0]
        assert ensure_task.status == "skipped"

    def test_world_snapshot_provider_smoke(self):
        provider = WorldSnapshotProvider()
        snap = provider.snapshot()
        assert isinstance(snap, DesktopStateSnapshot)
        assert isinstance(snap.running_processes, list)
