"""
AppContextRouter — Per-App Contextual Verb & Action Routing
Location: src/routing/app_context_router.py

Dispatches voice/text action verbs to the appropriate subsystem based on
the active foreground application context (Explorer, Chrome, VS Code, etc.).
Identifies targetless navigation verbs for zero-vision-cost fast-path execution.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Represents the active foreground application state."""

    app_name: str  # e.g. "explorer.exe", "chrome.exe", "code.exe"
    window_handle: int = 0
    window_title: str = ""
    pid: int = 0
    bounds: tuple[int, int, int, int] | None = None
    is_browser: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "window_handle": self.window_handle,
            "window_title": self.window_title,
            "pid": self.pid,
            "bounds": self.bounds,
            "is_browser": self.is_browser,
        }


# Per-app capability mappings: {app_name: {verb: (subsystem_capability, risk_level)}}
APP_CAPABILITY_MAPS: dict[str, dict[str, tuple[str, str]]] = {
    "explorer.exe": {
        "open": ("file.open", "LOW"),
        "open_file": ("file.open", "LOW"),
        "open_folder": ("file.open", "LOW"),
        "rename": ("file.rename", "LOW"),
        "delete": ("file.delete", "HIGH"),
        "navigate_up": ("window.nav_up", "LOW"),
        "search": ("file.search", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "chrome.exe": {
        "click": ("browser.click", "LOW"),
        "type": ("browser.type", "LOW"),
        "type_in_field": ("browser.type", "LOW"),
        "scroll": ("browser.scroll", "LOW"),
        "scroll_down": ("browser.scroll_down", "LOW"),
        "scroll_up": ("browser.scroll_up", "LOW"),
        "back": ("browser.back", "LOW"),
        "forward": ("browser.forward", "LOW"),
        "new_tab": ("browser.new_tab", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "msedge.exe": {
        "click": ("browser.click", "LOW"),
        "type": ("browser.type", "LOW"),
        "type_in_field": ("browser.type", "LOW"),
        "scroll": ("browser.scroll", "LOW"),
        "scroll_down": ("browser.scroll_down", "LOW"),
        "scroll_up": ("browser.scroll_up", "LOW"),
        "back": ("browser.back", "LOW"),
        "forward": ("browser.forward", "LOW"),
        "new_tab": ("browser.new_tab", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "code.exe": {
        "open": ("editor.open", "LOW"),
        "open_file": ("editor.open", "LOW"),
        "search_file": ("editor.find", "LOW"),
        "run": ("terminal.run", "HIGH"),
        "fix": ("coding.synthesize_fix", "HIGH"),
        "edit": ("editor.edit", "LOW"),
        "save": ("editor.save", "LOW"),
        "terminal": ("terminal.open", "LOW"),
        "delete": ("file.delete", "HIGH"),
    },
    "windowsterminal.exe": {
        "run": ("terminal.run", "HIGH"),
        "execute": ("terminal.run", "HIGH"),
        "clear": ("terminal.clear", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
        "interrupt": ("terminal.interrupt", "LOW"),
        "new_tab": ("terminal.new_tab", "LOW"),
    },
    "powershell.exe": {
        "run": ("terminal.run", "HIGH"),
        "execute": ("terminal.run", "HIGH"),
        "clear": ("terminal.clear", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "cmd.exe": {
        "run": ("terminal.run", "HIGH"),
        "execute": ("terminal.run", "HIGH"),
        "clear": ("terminal.clear", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "notepad.exe": {
        "open": ("file.open", "LOW"),
        "save": ("input.hotkey_save", "LOW"),
        "type": ("input.type", "LOW"),
        "clear": ("editor.clear", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
        "find": ("editor.find", "LOW"),
    },
    "notepad++.exe": {
        "open": ("file.open", "LOW"),
        "save": ("file.save", "LOW"),
        "type": ("input.type", "LOW"),
        "find": ("editor.find", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "slack.exe": {
        "send": ("slack.send_message", "LOW"),
        "search": ("slack.search", "LOW"),
        "channel": ("slack.switch_channel", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "discord.exe": {
        "send": ("discord.send_message", "LOW"),
        "search": ("discord.search", "LOW"),
        "channel": ("discord.switch_channel", "LOW"),
        "mute": ("discord.toggle_mute", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "teams.exe": {
        "send": ("teams.send_message", "LOW"),
        "search": ("teams.search", "LOW"),
        "join": ("teams.join_meeting", "LOW"),
        "mute": ("teams.toggle_mute", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
        "paste": ("clipboard.paste", "LOW"),
    },
    "spotify.exe": {
        "play": ("audio.play", "LOW"),
        "pause": ("audio.pause", "LOW"),
        "next": ("audio.next", "LOW"),
        "previous": ("audio.previous", "LOW"),
        "search": ("spotify.search", "LOW"),
        "volume_up": ("audio.volume_up", "LOW"),
        "volume_down": ("audio.volume_down", "LOW"),
    },
    "systemsettings.exe": {
        "open": ("settings.open", "LOW"),
        "search": ("settings.search", "LOW"),
        "toggle": ("settings.toggle", "LOW"),
    },
    "taskmgr.exe": {
        "end_task": ("system.kill_process", "HIGH"),
        "search": ("process.search", "LOW"),
        "performance": ("system.performance", "LOW"),
    },
    "acrobat.exe": {
        "find": ("input.hotkey_find", "LOW"),
        "search": ("input.hotkey_find", "LOW"),
        "scroll_down": ("input.scroll_down", "LOW"),
        "scroll_up": ("input.scroll_up", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
    },
    "acrord32.exe": {
        "find": ("input.hotkey_find", "LOW"),
        "search": ("input.hotkey_find", "LOW"),
        "scroll_down": ("input.scroll_down", "LOW"),
        "scroll_up": ("input.scroll_up", "LOW"),
        "copy": ("clipboard.copy", "LOW"),
    },
}

# Generic fallback mapping for desktop applications
DEFAULT_APP_CAPABILITIES: dict[str, tuple[str, str]] = {
    "open": ("app.open", "LOW"),
    "click": ("input.click", "LOW"),
    "type": ("input.type", "LOW"),
    "scroll": ("input.scroll", "LOW"),
    "copy": ("clipboard.copy", "LOW"),
    "paste": ("clipboard.paste", "LOW"),
    "save": ("input.hotkey_save", "LOW"),
    "delete": ("file.delete", "HIGH"),
    "run": ("terminal.run", "HIGH"),
    "fix": ("coding.synthesize_fix", "HIGH"),
    "switch_to": ("window.switch_to", "LOW"),
    "focus": ("window.focus", "LOW"),
    "bring_to_front": ("window.bring_to_front", "LOW"),
    "snap_left": ("window.snap_left", "LOW"),
    "snap_right": ("window.snap_right", "LOW"),
    "tile": ("window.arrange_tiled", "LOW"),
    "show_desktop": ("window.show_desktop", "LOW"),
    "transfer_to": ("clipboard.paste", "LOW"),
}

# Pure-navigation verbs that do not require target grounding
TARGETLESS_VERBS = {
    "scroll",
    "scroll_up",
    "scroll_down",
    "back",
    "go_back",
    "previous_page",
    "forward",
    "navigate_up",
    "new_tab",
    "refresh",
    "save",
    "terminal",
    "snap_left",
    "snap_right",
    "show_desktop",
    "tile",
}


class AppContextRouter:
    """
    Routes contextual verbs to specific subsystem capabilities based on
    the active foreground application.
    """

    _instance: Optional["AppContextRouter"] = None

    def __init__(self) -> None:
        self._last_detected_context: Optional[AppContext] = None

    @classmethod
    def get_instance(cls) -> "AppContextRouter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def detect_current_app(self) -> AppContext:
        """
        Detect currently active foreground application on Windows without
        spawning secondary polling loops.
        """
        try:
            from workspace.active_window import ActiveWindowMonitor
            mgr = ActiveWindowMonitor()
            win = mgr.get_active_window_sync()
            if win:
                app_name = (win.process_name or "").lower()
                is_browser = app_name in ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe")
                bounds = (win.x, win.y, win.x + win.width, win.y + win.height) if win.width > 0 else None
                ctx = AppContext(
                    app_name=app_name,
                    window_handle=win.hwnd,
                    window_title=win.title,
                    pid=win.pid,
                    bounds=bounds,
                    is_browser=is_browser,
                )
                self._last_detected_context = ctx
                return ctx
        except Exception as e:
            logger.debug(f"[AppContextRouter] Active window detection note: {e}")

        # Fallback empty context
        ctx = AppContext(app_name="unknown", window_handle=0, window_title="")
        self._last_detected_context = ctx
        return ctx

    def is_targetless_verb(self, verb: str) -> bool:
        """Check if verb is a pure navigation/control command needing no grounding."""
        v = verb.lower().strip().replace(" ", "_")
        return v in TARGETLESS_VERBS

    def resolve_verb(
        self, verb: str, app_context: AppContext | None = None
    ) -> tuple[str, str]:
        """
        Map a spoken/typed verb to the concrete (capability_name, risk_level) pair.

        Returns:
          tuple[capability_name, risk_level]  e.g. ("file.open", "LOW")
        """
        v = verb.lower().strip().replace(" ", "_")
        app_name = (app_context.app_name if app_context else "").lower()

        # Check app-specific map first
        app_map = APP_CAPABILITY_MAPS.get(app_name)
        if app_map and v in app_map:
            cap, risk = app_map[v]
            logger.debug(
                f"[AppContextRouter] Resolved verb '{verb}' for app '{app_name}' -> "
                f"({cap}, {risk})"
            )
            return cap, risk

        # Fallback to default desktop map
        if v in DEFAULT_APP_CAPABILITIES:
            cap, risk = DEFAULT_APP_CAPABILITIES[v]
            logger.debug(
                f"[AppContextRouter] Resolved verb '{verb}' via default map -> ({cap}, {risk})"
            )
            return cap, risk

        # Generic passthrough
        return f"generic.{v}", "LOW"

    @staticmethod
    def normalize_app_name(name: str) -> str:
        """Normalize colloquial app names to executable names (e.g. 'chrome' -> 'chrome.exe')."""
        n = name.lower().strip()
        aliases = {
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "vs code": "code.exe",
            "vscode": "code.exe",
            "code": "code.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "terminal": "windowsterminal.exe",
            "windows terminal": "windowsterminal.exe",
            "powershell": "powershell.exe",
            "cmd": "cmd.exe",
            "notepad": "notepad.exe",
            "notepad++": "notepad++.exe",
            "slack": "slack.exe",
            "discord": "discord.exe",
            "teams": "teams.exe",
            "spotify": "spotify.exe",
            "settings": "systemsettings.exe",
            "task manager": "taskmgr.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "acrobat": "acrobat.exe",
            "adobe acrobat": "acrobat.exe",
            "pdf reader": "acrobat.exe",
            "pdf": "acrobat.exe",
        }
        return aliases.get(n, n if n.endswith(".exe") else f"{n}.exe")

    def detect_cross_app_intent(
        self, text: str, current_app: str = ""
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Detect if an instruction requires cross-application coordination.
        Returns:
            tuple[is_cross_app, source_app, target_app]
        """
        txt = text.lower().strip()
        curr = current_app.lower().strip()

        # Known app aliases checked longest first
        known_aliases = sorted(
            [
                "google chrome",
                "microsoft edge",
                "adobe acrobat",
                "pdf reader",
                "vs code",
                "vscode",
                "windows terminal",
                "file explorer",
                "task manager",
                "notepad++",
                "notepad",
                "chrome",
                "edge",
                "code",
                "explorer",
                "terminal",
                "powershell",
                "cmd",
                "slack",
                "discord",
                "teams",
                "spotify",
                "settings",
                "acrobat",
                "word",
                "excel",
                "pdf",
            ],
            key=len,
            reverse=True,
        )

        for alias in known_aliases:
            # Pattern 1: switch / focus / activate
            if re.search(
                rf"\b(?:switch to|focus|bring up|activate|go to)\s+{re.escape(alias)}\b",
                txt,
            ):
                norm = self.normalize_app_name(alias)
                return True, curr or None, norm

            # Pattern 2: "in <app>, <action>" or "in <app> <action>"
            if re.search(rf"\bin\s+{re.escape(alias)}\b", txt):
                norm = self.normalize_app_name(alias)
                if curr and curr != norm:
                    return True, curr, norm
                return True, None, norm

            # Pattern 3: "paste to <app>", "transfer to <app>", "upload to <app>"
            if re.search(
                rf"\b(?:transfer|paste|send|upload)\s+(?:to|in)\s+{re.escape(alias)}\b",
                txt,
            ):
                norm = self.normalize_app_name(alias)
                return True, curr or None, norm

        return False, None, None
