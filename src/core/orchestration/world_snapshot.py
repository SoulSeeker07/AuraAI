"""
Desktop State Snapshot
Location: src/core/orchestration/world_snapshot.py

Lightweight desktop state snapshot and provider.
Consolidates OS probes onto canonical ActiveWindowMonitor and RunningAppsMonitor.
Thread-safe snapshotting with automatic WorldTimeline diff recording.
"""

import asyncio
import logging
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_src_root = Path(__file__).resolve().parent.parent.parent
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

try:
    from browser.world_model import BrowserContext, BrowserStateProbe
except (ModuleNotFoundError, ImportError):
    try:
        from browser.world_model import BrowserContext, BrowserStateProbe
    except Exception:
        class BrowserContext:
            running_browsers = []
            def to_dict(self):
                return {}

        class BrowserStateProbe:
            @staticmethod
            def probe_state(engine=None):
                return BrowserContext()

try:
    from workspace.active_window import ActiveWindowMonitor
    from workspace.running_apps import RunningAppsMonitor
except (ModuleNotFoundError, ImportError):
    try:
        from workspace.active_window import ActiveWindowMonitor
        from workspace.running_apps import RunningAppsMonitor
    except Exception:
        class ActiveWindowMonitor:
            def get_active_window(self):
                return {"title": ""}

        class RunningAppsMonitor:
            def __init__(self, *args, **kwargs):
                pass

            def get_running_apps(self):
                return []

logger = logging.getLogger(__name__)


@dataclass
class DesktopStateSnapshot:
    """
    Immutable snapshot of desktop state at a point in time.

    Consumed by TaskDecomposer to make skip/reuse decisions before
    building the TaskGraph — avoiding redundant steps like re-launching
    an already-open browser.
    """

    # Normalized process names (lowercase, no extension)
    running_processes: list[str] = field(default_factory=list)

    # Title of the currently focused window (may be empty)
    focused_window_title: str = ""

    # Real-time browser context representation (open tabs, domains, browsers)
    browser_context: BrowserContext = field(default_factory=BrowserContext)

    # Whether this snapshot was populated from real OS data
    is_live: bool = False

    # Timestamp of the snapshot capture
    timestamp: float = field(default_factory=time.time)

    @property
    def browser_world(self) -> BrowserContext:
        """Backward compatibility alias for browser_context."""
        return self.browser_context

    def is_running(self, app_name: str) -> bool:
        """
        Check if an application is currently running.
        """
        normalized = (
            app_name.lower()
            .replace(".exe", "")
            .replace("google ", "")
            .replace("microsoft ", "")
            .strip()
        )
        return any(normalized in proc for proc in self.running_processes)

    def has_window_with_title(self, fragment: str) -> bool:
        """
        Check if the focused window title contains a string fragment.
        """
        return fragment.lower() in self.focused_window_title.lower()

    def to_context_dict(self) -> dict:
        """Serialize for injection into shared_context."""
        return {
            "running_processes": self.running_processes,
            "focused_window_title": self.focused_window_title,
            "browser_context": self.browser_context.to_dict(),
            "browser_world": self.browser_context.to_dict(),
            "is_live": self.is_live,
            "timestamp": self.timestamp,
        }


class WorldSnapshotProvider:
    """
    Provides a DesktopStateSnapshot by polling the OS via canonical monitors
    and tracks state diffs thread-safely.
    """

    _lock = threading.RLock()
    _last_snapshot: DesktopStateSnapshot | None = None

    def __init__(
        self,
        window_monitor: ActiveWindowMonitor | None = None,
        apps_monitor: RunningAppsMonitor | None = None,
    ):
        self.window_monitor = window_monitor or ActiveWindowMonitor()
        self.apps_monitor = apps_monitor or RunningAppsMonitor(window_monitor=self.window_monitor)

    def snapshot(self, playwright_engine: Any = None) -> DesktopStateSnapshot:
        """
        Synchronously capture a snapshot of the current desktop state.
        Thread-safe against concurrent readers/writers.
        """
        processes = self._get_running_processes()
        focused = self._get_focused_window_title()
        browser_ctx = BrowserStateProbe.probe_state(playwright_engine)
        is_live = bool(processes or browser_ctx.running_browsers)

        snap = DesktopStateSnapshot(
            running_processes=processes,
            focused_window_title=focused,
            browser_context=browser_ctx,
            is_live=is_live,
            timestamp=time.time(),
        )

        with WorldSnapshotProvider._lock:
            WorldSnapshotProvider._last_snapshot = snap

        if is_live:
            logger.debug(
                f"WorldSnapshot: {len(processes)} processes, "
                f"{len(browser_ctx.open_tabs)} browser tabs, "
                f"focused='{focused[:40]}'"
            )
        else:
            logger.debug("WorldSnapshot: running in degraded mode")

        return snap

    async def snapshot_async(self, playwright_engine: Any = None) -> DesktopStateSnapshot:
        """
        Asynchronously capture a snapshot without blocking the event loop.
        """
        return await asyncio.to_thread(self.snapshot, playwright_engine)

    def snapshot_with_diff(
        self, playwright_engine: Any = None
    ) -> tuple[DesktopStateSnapshot, Any]:
        """
        Capture a snapshot, compute WorldDiff against previous snapshot,
        and automatically record the diff events into the WorldTimeline.
        Lock is held only for brief pointer read/write operations; sensing executes unblocked.
        """
        from .world_diff import WorldDiffEngine
        from .world_timeline import WorldTimeline

        with WorldSnapshotProvider._lock:
            prev_snap = WorldSnapshotProvider._last_snapshot

        # Sensing runs outside the lock, updating _last_snapshot under its own brief lock
        current_snap = self.snapshot(playwright_engine=playwright_engine)
        diff = WorldDiffEngine.compute_diff(prev_snap, current_snap)

        # Automatically log diff into the chronological timeline
        WorldTimeline.get_instance().record_diff(diff)

        return current_snap, diff

    def _get_running_processes(self) -> list[str]:
        """Get normalized list of running process names via canonical RunningAppsMonitor."""
        try:
            apps = self.apps_monitor.get_running_apps_sync()
            return [app.process_name for app in apps if app.process_name]
        except Exception as e:
            logger.warning(f"WorldSnapshot: process probe failed: {e}")
            return []

    def _get_focused_window_title(self) -> str:
        """Get the title of the currently focused window via canonical ActiveWindowMonitor."""
        try:
            win = self.window_monitor.get_active_window_sync()
            return win.title if win else ""
        except Exception as e:
            logger.debug(f"WorldSnapshot: focused window probe failed: {e}")
            return ""
