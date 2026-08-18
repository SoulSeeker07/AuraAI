"""
Security Backend Adapter
Location: src/core/backends/adapters/security_backend.py

Connects MasterOrchestrator to SecurityManager.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class SecurityBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for firewall, defender antivirus, and privacy cleanup.
    """

    @property
    def name(self) -> str:
        return "Security Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "security",
            "security.firewall.status",
            "security.firewall.enable",
            "security.firewall.disable",
            "security.firewall.add_rule",
            "security.antivirus.status",
            "security.antivirus.scan",
            "security.vpn.status",
            "security.vpn.connect",
            "security.vpn.disconnect",
            "privacy.clear_temp",
            "firewall",
            "antivirus",
            "vpn",
            "privacy",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 200.0,
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
        mgr = registry.get_manager("security")
        if not mgr:
            registry.discover()
            mgr = registry.get_manager("security")

        if not mgr:
            return ExecutionResult(
                success=False,
                planner="security",
                goal=goal,
                warnings=["SecurityManager not found."],
            )

        res = mgr.execute(capability=capability, goal=goal, arguments=arguments)
        return ExecutionResult(
            success=res.success,
            planner="security",
            goal=goal,
            observations=[f"Security operation: {capability}"],
            warnings=[res.error] if (not res.success and res.error) else [],
            data=res.data,
        )

