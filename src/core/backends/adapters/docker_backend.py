"""
Docker Backend Adapter
Location: src/core/backends/adapters/docker_backend.py

Connects MasterOrchestrator to DockerPlugin for container management.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class DockerBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for Docker containers and images.
    """

    @property
    def name(self) -> str:
        return "Docker Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "docker",
            "docker.list_containers",
            "docker.start",
            "docker.stop",
            "docker.logs",
            "docker.exec",
            "docker.build",
            "docker.pull",
            "docker.compose_up",
            "docker.compose_down",
            "docker.images",
            "docker.remove",
            "container",
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
        from plugins.docker.docker_plugin import DockerPlugin

        plugin = DockerPlugin()
        plugin.load()
        plugin.initialize()

        args = arguments or {}
        res = plugin.execute(capability=capability, **args)

        return ExecutionResult(
            success=True if not isinstance(res, dict) or res.get("status") != "error" else False,
            planner="docker",
            goal=goal,
            observations=[f"Docker operation completed: {capability}"],
            data={"result": res},
        )
