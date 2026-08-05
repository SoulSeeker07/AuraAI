"""
World Diff Engine
Location: src/core/orchestration/world_diff.py

Compares successive DesktopStateSnapshots to compute real-time state changes:
new/closed processes, new/closed browser tabs, focused window changes, etc.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .world_snapshot import DesktopStateSnapshot

logger = logging.getLogger(__name__)


@dataclass
class WorldDiff:
    """Represents differences between two consecutive DesktopStateSnapshots."""
    new_processes: list[str] = field(default_factory=list)
    closed_processes: list[str] = field(default_factory=list)
    new_tabs: list[str] = field(default_factory=list)
    closed_tabs: list[str] = field(default_factory=list)
    focused_window_changed: bool = False
    previous_focused: str = ""
    current_focused: str = ""

    def summary(self) -> str:
        changes: list[str] = []
        if self.new_processes:
            changes.append(f"Started processes: {', '.join(self.new_processes)}")
        if self.closed_processes:
            changes.append(f"Closed processes: {', '.join(self.closed_processes)}")
        if self.new_tabs:
            changes.append(f"Opened tabs: {', '.join(self.new_tabs)}")
        if self.closed_tabs:
            changes.append(f"Closed tabs: {', '.join(self.closed_tabs)}")
        if self.focused_window_changed:
            changes.append(f"Focus changed from '{self.previous_focused}' to '{self.current_focused}'")

        return "; ".join(changes) if changes else "No desktop state changes detected."

    def to_dict(self) -> dict[str, Any]:
        return {
            "new_processes": self.new_processes,
            "closed_processes": self.closed_processes,
            "new_tabs": self.new_tabs,
            "closed_tabs": self.closed_tabs,
            "focused_window_changed": self.focused_window_changed,
            "previous_focused": self.previous_focused,
            "current_focused": self.current_focused,
            "summary": self.summary(),
        }


class WorldDiffEngine:
    """Computes state diffs between DesktopStateSnapshot instances."""

    @staticmethod
    def compute_diff(
        prev_snap: DesktopStateSnapshot | None, current_snap: DesktopStateSnapshot
    ) -> WorldDiff:
        if prev_snap is None:
            return WorldDiff(
                current_focused=current_snap.focused_window_title,
            )

        prev_procs = set(prev_snap.running_processes)
        curr_procs = set(current_snap.running_processes)

        new_procs = sorted(list(curr_procs - prev_procs))
        closed_procs = sorted(list(prev_procs - curr_procs))

        prev_tabs = {t.title for t in prev_snap.browser_context.open_tabs}
        curr_tabs = {t.title for t in current_snap.browser_context.open_tabs}

        new_tabs = sorted(list(curr_tabs - prev_tabs))
        closed_tabs = sorted(list(prev_tabs - curr_tabs))

        focused_changed = (prev_snap.focused_window_title != current_snap.focused_window_title)

        return WorldDiff(
            new_processes=new_procs,
            closed_processes=closed_procs,
            new_tabs=new_tabs,
            closed_tabs=closed_tabs,
            focused_window_changed=focused_changed,
            previous_focused=prev_snap.focused_window_title,
            current_focused=current_snap.focused_window_title,
        )
