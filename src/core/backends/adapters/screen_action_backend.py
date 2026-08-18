"""
Screen Action Backend Adapter
Location: src/core/backends/adapters/screen_action_backend.py

Connects MasterOrchestrator to ScreenActionManager for closed-loop computer-use automation.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class ScreenActionBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for screenshot-to-action computer use loop.
    """

    @property
    def name(self) -> str:
        return "Screen Action Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "screen_action",
            "computer_use",
            "screen.capture",
            "screen.capture_region",
            "screen.capture_window",
            "screen.compare",
            "screen.find_element",
            "screen.find_text",
            "screen.wait_for_change",
            "screen.act_step",
            "screen",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 300.0,
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
        screen_mgr = registry.get_manager("screen_action")

        if not screen_mgr:
            registry.discover()
            screen_mgr = registry.get_manager("screen_action")

        if not screen_mgr:
            return ExecutionResult(
                success=False,
                planner="screen_action",
                goal=goal,
                warnings=["ScreenActionManager could not be loaded from native layer."],
            )

        res = screen_mgr.execute(capability=capability, goal=goal, arguments=arguments)

        return ExecutionResult(
            success=res.success,
            planner="screen_action",
            goal=goal,
            observations=[
                f"Screen action: {capability}"
                if res.success
                else f"Screen action error: {res.error}"
            ],
            warnings=[res.error] if (not res.success and res.error) else [],
            data=res.data,
        )

