"""
Notification Backend Adapter
Location: src/core/backends/adapters/notification_backend.py

Connects MasterOrchestrator to NotificationManager for desktop popups and alerts.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class NotificationBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for system notifications and alerts.
    """

    @property
    def name(self) -> str:
        return "Notification Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "notification",
            "notification.toast",
            "notification.alert",
            "notification.schedule",
            "notification.clear",
            "notification.list",
            "notification.sound",
            "notify",
            "notify.toast",
            "notify.alert",
            "notify.schedule",
            "notify.clear",
            "notify.list",
            "notify.sound",
            "alert",
            "reminder",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 30.0,
            "cost": 0.0,
            "is_local": True,
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        # Lazy import
        from desktop.native.managers.native_manager_registry import NativeManagerRegistry

        registry = NativeManagerRegistry.get_instance()
        notif_mgr = registry.get_manager("notification")

        if not notif_mgr:
            registry.discover()
            notif_mgr = registry.get_manager("notification")

        if not notif_mgr:
            return ExecutionResult(
                success=False,
                planner="notification",
                goal=goal,
                warnings=["NotificationManager could not be loaded from native layer."],
            )

        res = notif_mgr.execute(capability=capability, goal=goal, arguments=arguments)

        return ExecutionResult(
            success=res.success,
            planner="notification",
            goal=goal,
            observations=[
                f"Notification displayed: {capability}"
                if res.success
                else f"Notification error: {res.error}"
            ],
            warnings=[res.error] if (not res.success and res.error) else [],
            data=res.data,
        )

