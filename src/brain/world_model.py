"""
Layer 0.5: World Model
======================

Context is conversation.
World Model is the computer.

The World Model tracks:
    * Applications (running, focused, PID)
    * Browser (tabs, URLs)
    * Workspace (project, git branch)
    * Voice (mic status)
    * Clipboard (current text)
    * Focused window

The World Model updates continuously — not only when the user asks.
This is how Aura understands "Open it" → "it" → Chrome without asking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WorldState:
    """A snapshot of the external computer state."""

    applications: list[dict[str, Any]] = field(default_factory=list)
    focused_window: str = ""
    focused_pid: int | None = None
    browser_tabs: list[dict[str, Any]] = field(default_factory=list)
    workspace: dict[str, Any] = field(default_factory=dict)
    voice: dict[str, Any] = field(default_factory=dict)
    clipboard: str = ""
    is_live: bool = False
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "applications": self.applications,
            "focused_window": self.focused_window,
            "focused_pid": self.focused_pid,
            "browser_tabs": self.browser_tabs,
            "workspace": self.workspace,
            "voice": self.voice,
            "clipboard": self.clipboard,
            "is_live": self.is_live,
            "timestamp": self.timestamp,
        }

    def summarize(self) -> str:
        """Build a compact text summary for the LLM."""
        parts: list[str] = []

        if self.focused_window:
            parts.append(f"Focused Window: {self.focused_window}")
        if self.applications:
            running = [
                a.get("name", "unknown")
                for a in self.applications
                if a.get("running", False)
            ]
            if running:
                parts.append(f"Running Apps: {', '.join(running[:5])}")
        if self.browser_tabs:
            tabs = [t.get("title", t.get("url", "tab")) for t in self.browser_tabs[:5]]
            parts.append(f"Browser Tabs: {', '.join(tabs)}")
        if self.workspace:
            project = self.workspace.get("project", "")
            branch = self.workspace.get("git_branch", "")
            if project:
                parts.append(f"Project: {project}")
            if branch:
                parts.append(f"Git Branch: {branch}")
        if self.clipboard:
            parts.append(f"Clipboard: {self.clipboard[:50]}")
        if self.voice:
            mic = self.voice.get("mic_active", False)
            parts.append(f"Mic: {'Active' if mic else 'Inactive'}")

        return "\n".join(parts) if parts else "No world state available."


class WorldModel:
    """
    Tracks the external computer state continuously.

    This is Aura's perception of the computer.
    It updates even when the user isn't asking.
    """

    def __init__(self, snapshot_provider: Any | None = None):
        """
        Initialize the World Model.

        Args:
            snapshot_provider: Optional WorldSnapshotProvider for live OS state.
        """
        self.snapshot_provider = snapshot_provider
        self._state = WorldState()

    def update(self) -> WorldState:
        """
        Update the world state from live system probes.

        Returns:
            The updated WorldState.
        """
        from datetime import datetime

        # ── Live OS probe ───────────────────────────────────────────────────
        if self.snapshot_provider is not None:
            try:
                snap = self.snapshot_provider.snapshot()
                self._state.focused_window = snap.focused_window_title or ""
                self._state.focused_pid = getattr(snap, "focused_pid", None)
                self._state.applications = [
                    {"name": p, "running": True}
                    for p in getattr(snap, "running_processes", [])[:20]
                ]
                self._state.is_live = getattr(snap, "is_live", False)
            except Exception as e:
                logger.debug(f"World snapshot unavailable: {e}")

        # ── Workspace state ─────────────────────────────────────────────────
        try:
            import subprocess

            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                self._state.workspace["git_branch"] = result.stdout.strip()
        except Exception:
            pass

        self._state.timestamp = datetime.now().isoformat()

        logger.info(
            f"WorldModel updated: focused={self._state.focused_window}, "
            f"apps={len(self._state.applications)}, "
            f"live={self._state.is_live}"
        )

        return self._state

    def get_state(self) -> WorldState:
        """Get the current world state."""
        return self._state

    def set_browser_tabs(self, tabs: list[dict[str, Any]]) -> None:
        """Set the current browser tabs."""
        self._state.browser_tabs = tabs

    def set_clipboard(self, text: str) -> None:
        """Set the current clipboard content."""
        self._state.clipboard = text

    def set_voice_state(self, mic_active: bool) -> None:
        """Set the voice/mic state."""
        self._state.voice = {"mic_active": mic_active}

    def set_workspace(self, workspace: dict[str, Any]) -> None:
        """Set the workspace state."""
        self._state.workspace = workspace


__all__ = ["WorldModel", "WorldState"]