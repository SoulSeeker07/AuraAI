"""
Unit Tests for M18 Phase 1: Probe Consolidation & World Model Wiring

Verifies:
  1. ActiveWindowMonitor RECT struct & dimension calculation (Bug 1 fix)
  2. RunningAppsMonitor foreground delegation (Bug 2 fix)
  3. GitContext timedelta cache & TTL behavior (Bug 3 fix)
  4. WorldSnapshotProvider thread-safety, timestamp field, and auto diff->timeline recording
  5. WorldStateObserver observe_sync/observe_async safety
  6. WorldModel sync/async update via GitContext
"""

import asyncio
import ctypes
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.brain.world_model import WorldModel, WorldState
from src.core.orchestration.world_diff import WorldDiff
from src.core.orchestration.world_snapshot import DesktopStateSnapshot, WorldSnapshotProvider
from src.core.orchestration.world_state_observer import WorldStateObserver
from src.core.orchestration.world_timeline import TimelineEvent, WorldTimeline
from src.workspace.active_window import RECT, ActiveWindowMonitor
from src.workspace.git_context import GitContext
from src.workspace.models import ActiveWindow, GitRepository, RunningApplication
from src.workspace.running_apps import RunningAppsMonitor


# ── 1. ActiveWindowMonitor Tests ─────────────────────────────────────────────

def test_active_window_rect_struct():
    """Verify RECT structure has 16-byte size and proper long fields."""
    assert ctypes.sizeof(RECT) == 16
    rect = RECT(100, 200, 900, 800)
    assert rect.left == 100
    assert rect.top == 200
    assert rect.right == 900
    assert rect.bottom == 800
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    assert width == 800
    assert height == 600


def test_active_window_monitor_sync_and_async():
    """Test ActiveWindowMonitor returns valid ActiveWindow object."""
    monitor = ActiveWindowMonitor()

    def mock_get_window_text(hwnd, buf, maxlen):
        buf.value = "VS Code - AuraAI"
        return len(buf.value)

    def mock_get_window_rect(hwnd, byref_rect):
        byref_rect._obj.left = 0
        byref_rect._obj.top = 0
        byref_rect._obj.right = 1200
        byref_rect._obj.bottom = 800
        return 1

    with patch.object(monitor, "GetForegroundWindow", return_value=12345), \
         patch.object(monitor, "GetWindowTextW", side_effect=mock_get_window_text), \
         patch.object(monitor, "GetWindowRect", side_effect=mock_get_window_rect), \
         patch.object(monitor, "_get_process_name", return_value="code.exe"):

        win = monitor.get_active_window_sync()
        assert win is not None
        assert win.title == "VS Code - AuraAI"
        assert win.app_name == "VS Code"
        assert win.rect["width"] == 1200
        assert win.rect["height"] == 800

        # Test async path
        async def run_async():
            return await monitor.get_active_window()

        win_async = asyncio.run(run_async())
        assert win_async is not None
        assert win_async.title == "VS Code - AuraAI"


# ── 2. RunningAppsMonitor Tests ──────────────────────────────────────────────

def test_running_apps_foreground_delegation():
    """Verify RunningAppsMonitor delegates foreground detection to ActiveWindowMonitor."""
    mock_window_mon = MagicMock(spec=ActiveWindowMonitor)
    mock_window_mon.get_active_window_sync.return_value = ActiveWindow(
        title="Terminal",
        app_name="Command Prompt",
        process_name="cmd",
        window_id=999,
        rect={"x": 0, "y": 0, "width": 800, "height": 600},
    )

    apps_mon = RunningAppsMonitor(window_monitor=mock_window_mon)
    fg_app = apps_mon.get_foreground_app_sync()

    assert fg_app is not None
    assert fg_app.name == "Command Prompt"
    assert fg_app.window_title == "Terminal"
    assert fg_app.is_foreground is True


# ── 3. GitContext Tests ──────────────────────────────────────────────────────

def test_git_context_cache_and_timedelta():
    """Verify GitContext caching works with timedelta without TypeError."""
    git_ctx = GitContext(cache_ttl_seconds=30)
    fake_repo = GitRepository(path=str(Path.cwd()), branch="feature/world-model")

    # Manually populate cache with datetime
    git_ctx._cache[str(Path.cwd().resolve())] = (fake_repo, datetime.now())

    # Second call must hit cache without raising timedelta < int error
    cached_repo = git_ctx.get_git_repo_sync()
    assert cached_repo is not None
    assert cached_repo.branch == "feature/world-model"

    # Test async
    async def run_async():
        return await git_ctx.get_git_repo()

    cached_async = asyncio.run(run_async())
    assert cached_async is not None
    assert cached_async.branch == "feature/world-model"


# ── 4. WorldSnapshotProvider & Timeline Wiring Tests ─────────────────────────

def test_world_snapshot_timestamp_and_thread_safety():
    """Verify DesktopStateSnapshot timestamp and thread-safe snapshotting."""
    snap_provider = WorldSnapshotProvider()
    snap = snap_provider.snapshot()

    assert isinstance(snap.timestamp, float)
    assert snap.timestamp > 0

    # Test multi-threaded hammering
    results = []

    def worker():
        for _ in range(20):
            s = snap_provider.snapshot()
            results.append(s.timestamp)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 100


def test_snapshot_with_diff_auto_records_to_timeline():
    """Verify snapshot_with_diff computes diff and automatically populates WorldTimeline."""
    timeline = WorldTimeline.get_instance()
    timeline.clear()

    snap_provider = WorldSnapshotProvider()

    # Create synthetic previous and current snapshots
    snap1 = DesktopStateSnapshot(
        running_processes=["code", "chrome"],
        focused_window_title="VS Code",
    )
    snap2 = DesktopStateSnapshot(
        running_processes=["code", "chrome", "spotify"],
        focused_window_title="Spotify Free",
    )

    with WorldSnapshotProvider._lock:
        WorldSnapshotProvider._last_snapshot = snap1

    with patch.object(snap_provider, "snapshot", return_value=snap2):
        current_snap, diff = snap_provider.snapshot_with_diff()

        assert diff.focused_window_changed is True
        assert "spotify" in diff.new_processes

        events = timeline.get_recent_events(minutes=5)
        event_types = [e.event_type for e in events]
        assert "process_start" in event_types
        assert "window_focus" in event_types


# ── 5. WorldStateObserver Tests ──────────────────────────────────────────────

def test_world_state_observer_sync_and_async():
    """Verify WorldStateObserver observe_sync does not crash on timestamp."""
    observer = WorldStateObserver.get_instance()
    
    obs_sync = observer.observe_sync()
    assert "timestamp" in obs_sync
    assert isinstance(obs_sync["timestamp"], float)

    async def run_obs_async():
        return await observer.observe_async()

    obs_async = asyncio.run(run_obs_async())
    assert "timestamp" in obs_async


# ── 6. WorldModel Tests ──────────────────────────────────────────────────────

def test_world_model_sync_and_async_update():
    """Verify WorldModel update integrates GitContext safely."""
    from unittest.mock import AsyncMock

    mock_git = MagicMock(spec=GitContext)
    fake_repo = GitRepository(
        path="C:/AuraAI",
        branch="main",
        uncommitted_changes=3,
        is_dirty=True,
    )
    mock_git.get_git_repo_sync.return_value = fake_repo
    mock_git.get_git_repo = AsyncMock(return_value=fake_repo)

    wm = WorldModel(git_context=mock_git)
    state = wm.update()

    assert state.workspace.get("git_branch") == "main"
    assert state.workspace.get("uncommitted_changes") == 3

    # Async update test
    async def run_wm_async():
        return await wm.update_async()

    state_async = asyncio.run(run_wm_async())
    assert state_async.workspace.get("git_branch") == "main"
