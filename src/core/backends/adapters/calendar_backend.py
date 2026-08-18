"""
Calendar Backend Adapter
Location: src/core/backends/adapters/calendar_backend.py

Connects MasterOrchestrator to CalendarPlugin for events, tasks, and scheduling.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class CalendarBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for calendar and to-do task management.
    """

    @property
    def name(self) -> str:
        return "Calendar Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "calendar",
            "calendar.list_events",
            "calendar.create_event",
            "calendar.update_event",
            "calendar.delete_event",
            "calendar.check_availability",
            "calendar.set_reminder",
            "tasks.create",
            "tasks.list",
            "tasks.complete",
            "tasks.set_priority",
            "event",
            "meeting",
            "todo",
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
        from plugins.calendar.calendar_plugin import CalendarPlugin

        plugin = CalendarPlugin()
        plugin.load()
        plugin.initialize()

        args = arguments or {}
        res = plugin.execute(capability=capability, **args)

        return ExecutionResult(
            success=True if not isinstance(res, dict) or res.get("status") != "error" else False,
            planner="calendar",
            goal=goal,
            observations=[f"Calendar operation: {capability}"],
            data={"result": res},
        )
