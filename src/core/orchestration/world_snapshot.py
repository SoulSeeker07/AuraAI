"""
Desktop State Snapshot
Location: src/core/orchestration/world_snapshot.py

Lightweight pre-decomposition desktop state probe.

Used by TaskDecomposer to skip tasks whose preconditions are already satisfied.
For example: if Chrome is already running, skip the "Launch Chrome" subtask.

Design:
- Queries running Windows processes via psutil (if available)
- Queries the focused window title via win32gui (if available)
- Gracefully degrades if neither is available (returns an empty snapshot)

This is a pre-M18 placeholder.
Milestone 18 (World Model) will extend this into a full persistent world
representation (tabs, files, project state, desktop layout, etc.).
The interface is intentionally minimal so M18 can replace the implementation
without changing how the decomposer consumes it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


from src.browser.world_model import BrowserContext, BrowserStateProbe, BrowserWorldModel


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
        }


class WorldSnapshotProvider:
    """
    Provides a DesktopStateSnapshot by polling the OS and tracks state diffs.
    """

    _last_snapshot: DesktopStateSnapshot | None = None

    def snapshot(self, playwright_engine: Any = None) -> DesktopStateSnapshot:
        """
        Capture a snapshot of the current desktop state.
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
        )

        WorldSnapshotProvider._last_snapshot = snap

        if is_live:
            logger.debug(
                f"WorldSnapshot: {len(processes)} processes, "
                f"{len(browser_ctx.open_tabs)} browser tabs, "
                f"focused='{focused[:40]}'"
            )
        else:
            logger.debug("WorldSnapshot: running in degraded mode (no psutil/win32gui)")

        return snap

    def snapshot_with_diff(self, playwright_engine: Any = None) -> tuple[DesktopStateSnapshot, Any]:
        """
        Capture a snapshot and compute the WorldDiff against the previous snapshot.
        """
        from src.core.orchestration.world_diff import WorldDiffEngine

        prev_snap = WorldSnapshotProvider._last_snapshot
        current_snap = self.snapshot(playwright_engine=playwright_engine)
        diff = WorldDiffEngine.compute_diff(prev_snap, current_snap)
        return current_snap, diff

    # ── Private OS probes ───────────────────────────────────────────────

    def _get_running_processes(self) -> list[str]:
        """Get normalized list of running process names via psutil."""
        try:
            import psutil  # type: ignore[import]
            names: list[str] = []
            for proc in psutil.process_iter(["name"]):
                try:
                    name = (proc.info.get("name") or "").lower().replace(".exe", "").strip()
                    if name:
                        names.append(name)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return names
        except ImportError:
            logger.debug("WorldSnapshot: psutil not available — process list empty")
            return []
        except Exception as e:
            logger.warning(f"WorldSnapshot: process probe failed: {e}")
            return []

    def _get_focused_window_title(self) -> str:
        """Get the title of the currently focused window via win32gui."""
        try:
            import win32gui  # type: ignore[import]
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd) or ""
        except ImportError:
            return ""
        except Exception as e:
            logger.debug(f"WorldSnapshot: focused window probe failed: {e}")
            return ""
