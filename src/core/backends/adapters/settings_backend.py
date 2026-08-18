"""
Settings Backend Adapter
Location: src/core/backends/adapters/settings_backend.py

Connects MasterOrchestrator to SettingsManager.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class SettingsBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for system configuration, dark mode, wallpaper, and startup.
    """

    @property
    def name(self) -> str:
        return "Settings Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "settings",
            "settings.dark_mode",
            "settings.night_light",
            "settings.wallpaper",
            "settings.default_browser",
            "settings.default_app",
            "settings.startup_apps.list",
            "settings.startup_apps.add",
            "settings.startup_apps.remove",
            "settings.taskbar.hide",
            "settings.taskbar.show",
            "settings.time_zone",
            "dark_mode",
            "wallpaper",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 50.0,
            "cost": 0.0,
            "is_local": True,
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        from desktop.native.managers.native_manager_registry import NativeManagerRegistry

        registry = NativeManagerRegistry.get_instance()
        mgr = registry.get_manager("settings")
        if not mgr:
            registry.discover()
            mgr = registry.get_manager("settings")

        if not mgr:
            return ExecutionResult(
                success=False,
                planner="settings",
                goal=goal,
                warnings=["SettingsManager not found."],
            )

        res = mgr.execute(capability=capability, goal=goal, arguments=arguments)
        return ExecutionResult(
            success=res.success,
            planner="settings",
            goal=goal,
            observations=[f"Settings operation: {capability}"],
            warnings=[res.error] if (not res.success and res.error) else [],
            data=res.data,
        )

