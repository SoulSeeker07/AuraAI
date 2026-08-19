"""
Desktop World Model Provider
Location: src/brain/providers/desktop_provider.py

Provides real-time desktop perception: focused window, foreground application,
running non-system processes, and active editor/browser detection.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import Executor
from typing import Any

try:
    from workspace.active_window import ActiveWindowMonitor
    from workspace.running_apps import RunningAppsMonitor
except (ImportError, ModuleNotFoundError):
    try:
        from src.workspace.active_window import ActiveWindowMonitor
        from src.workspace.running_apps import RunningAppsMonitor
    except Exception:
        ActiveWindowMonitor = None  # type: ignore
        RunningAppsMonitor = None  # type: ignore
from .base import IWorldProvider, ProviderFact


class DesktopProvider(IWorldProvider):
    """
    World model provider for native OS desktop and process perception.
    """

    def __init__(
        self,
        window_monitor: ActiveWindowMonitor | None = None,
        apps_monitor: RunningAppsMonitor | None = None,
        executor: Executor | None = None,
    ):
        self.window_monitor = window_monitor or ActiveWindowMonitor()
        self.apps_monitor = apps_monitor or RunningAppsMonitor(window_monitor=self.window_monitor)
        self._executor = executor

    @property
    def domain(self) -> str:
        return "desktop"

    async def get_state(self) -> dict[str, Any]:
        """Fetch full desktop perception dictionary."""
        loop = asyncio.get_running_loop()
        if self._executor:
            win = await loop.run_in_executor(self._executor, self.window_monitor.get_active_window_sync)
            apps = await loop.run_in_executor(self._executor, self.apps_monitor.get_running_apps_sync)
        else:
            win = self.window_monitor.get_active_window_sync()
            apps = self.apps_monitor.get_running_apps_sync()

        return {
            "focused_window": win.title if win else "",
            "focused_app": win.app_name if win else "",
            "running_apps": [a.name for a in apps],
            "running_editors": [a.name for a in apps if a.is_editor],
            "running_browsers": [a.name for a in apps if a.is_browser],
        }

    async def query(self, entity: str) -> list[ProviderFact]:
        """
        Query desktop domain for specific entities.
        
        Supported entity queries:
          - "active_window" / "focused_window"
          - "focused_app" / "current_app"
          - "running_apps" / "apps"
          - "is_running:<app_name>"
          - "editor_open" / "running_editors"
          - "browser_open" / "running_browsers"
        """
        facts: list[ProviderFact] = []
        entity_norm = entity.strip().lower()

        # Check for is_running:<app_name> query
        if entity_norm.startswith("is_running:"):
            target_app = entity_norm.split(":", 1)[1].strip()
            state = await self.get_state()
            running = any(target_app in app.lower() for app in state["running_apps"])
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity=f"is_running:{target_app}",
                    value=running,
                )
            )
            return facts

        state = await self.get_state()

        if entity_norm in ("active_window", "focused_window", "window", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="focused_window",
                    value=state["focused_window"],
                )
            )

        if entity_norm in ("focused_app", "current_app", "active_app", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="focused_app",
                    value=state["focused_app"],
                )
            )

        if entity_norm in ("running_apps", "apps", "processes", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="running_apps",
                    value=state["running_apps"],
                )
            )

        if entity_norm in ("editor_open", "running_editors", "editor", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="running_editors",
                    value=state["running_editors"],
                )
            )

        if entity_norm in ("browser_open", "running_browsers", "browser", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="running_browsers",
                    value=state["running_browsers"],
                )
            )

        return facts
