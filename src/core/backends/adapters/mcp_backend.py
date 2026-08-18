"""
MCP Backend Adapter
Location: src/core/backends/adapters/mcp_backend.py

Connects MasterOrchestrator to Model Context Protocol external tool servers.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class MCPBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for Model Context Protocol (MCP) server tools.
    """

    @property
    def name(self) -> str:
        return "MCP Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "mcp",
            "mcp.list_servers",
            "mcp.connect",
            "mcp.list_tools",
            "mcp.call_tool",
            "mcp.list_resources",
            "mcp.read_resource",
            "mcp.register_server",
            "tool_server",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 150.0,
            "cost": 0.0,
            "is_local": True,
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        from plugins.mcp.mcp_plugin import MCPPlugin

        plugin = MCPPlugin()
        plugin.load()
        plugin.initialize()

        args = arguments or {}
        res = plugin.execute(capability=capability, **args)

        return ExecutionResult(
            success=True if not isinstance(res, dict) or res.get("status") != "error" else False,
            planner="mcp",
            goal=goal,
            observations=[f"MCP operation completed: {capability}"],
            data={"result": res},
        )
