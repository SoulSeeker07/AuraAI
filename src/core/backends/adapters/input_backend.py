"""
Input Simulation Backend Adapter
Location: src/core/backends/adapters/input_backend.py

Connects MasterOrchestrator to InputManager for synthetic mouse and keyboard operations.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class InputBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for keyboard & mouse simulation.
    """

    @property
    def name(self) -> str:
        return "Input Simulation Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "input",
            "input.click",
            "input.double_click",
            "input.right_click",
            "input.drag",
            "input.scroll",
            "input.type_text",
            "input.hotkey",
            "input.key_press",
            "input.key_down",
            "input.key_up",
            "input.move_mouse",
            "input.mouse_position",
            "keyboard",
            "mouse",
            "click",
            "type",
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
        # Lazy import to satisfy import contracts
        from desktop.native.managers.native_manager_registry import NativeManagerRegistry

        registry = NativeManagerRegistry.get_instance()
        input_mgr = registry.get_manager("input")

        if not input_mgr:
            registry.discover()
            input_mgr = registry.get_manager("input")

        if not input_mgr:
            return ExecutionResult(
                success=False,
                planner="input",
                goal=goal,
                warnings=["InputManager could not be loaded from native layer."],
            )

        res = input_mgr.execute(capability=capability, goal=goal, arguments=arguments)

        return ExecutionResult(
            success=res.success,
            planner="input",
            goal=goal,
            observations=[
                f"Input executed: {capability}"
                if res.success
                else f"Input error: {res.error}"
            ],
            warnings=[res.error] if (not res.success and res.error) else [],
            data=res.data,
        )

