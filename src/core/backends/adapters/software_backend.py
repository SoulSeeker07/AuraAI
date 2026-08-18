"""
Software Backend Adapter
Location: src/core/backends/adapters/software_backend.py

Connects MasterOrchestrator to SoftwareManager.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class SoftwareBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for software and package installations (winget, pip, npm).
    """

    @property
    def name(self) -> str:
        return "Software Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "software",
            "software.list_installed",
            "software.search",
            "software.install",
            "software.uninstall",
            "software.update",
            "software.update_all",
            "pip.install",
            "npm.install",
            "install",
            "package",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 500.0,
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
        mgr = registry.get_manager("software")
        if not mgr:
            registry.discover()
            mgr = registry.get_manager("software")

        if not mgr:
            return ExecutionResult(
                success=False,
                planner="software",
                goal=goal,
                warnings=["SoftwareManager not found."],
            )

        res = mgr.execute(capability=capability, goal=goal, arguments=arguments)
        return ExecutionResult(
            success=res.success,
            planner="software",
            goal=goal,
            observations=[f"Software operation: {capability}"],
            warnings=[res.error] if (not res.success and res.error) else [],
            data=res.data,
        )

