"""
Aura Docker & Container Plugin
==============================
Plugin for container management (list, start, stop, logs, build, compose).
"""

import logging
import subprocess
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest

logger = logging.getLogger(__name__)


class DockerPlugin(Plugin):
    """
    Docker Container Automation Plugin for Aura.
    """

    def __init__(self, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = PluginManifest(
                name="docker",
                version="1.0.0",
                author="Aura AI",
                description="Docker container and image lifecycle automation plugin.",
                category=PluginCategory.DOCKER,
                capabilities=[
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
                ],
            )
        super().__init__(manifest)

    def load(self) -> bool:
        self.state = "initialized"
        return True

    def initialize(self) -> bool:
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        return capability.startswith("docker.") or capability in self.manifest.capabilities

    def _run_docker_cli(self, args: list[str]) -> dict[str, Any]:
        try:
            cmd = ["docker"] + args
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60.0)
            return {
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "success": proc.returncode == 0,
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Docker CLI execution failed: {e}",
                "success": False,
            }

    def execute(self, capability: str, **kwargs: Any) -> Any:
        cap = capability.lower()
        if cap == "docker.list_containers":
            all_flag = ["-a"] if kwargs.get("all") else []
            return self._run_docker_cli(["ps"] + all_flag)
        elif cap == "docker.images":
            return self._run_docker_cli(["images"])
        elif cap == "docker.start":
            cid = kwargs.get("container") or kwargs.get("name", "")
            return self._run_docker_cli(["start", cid])
        elif cap == "docker.stop":
            cid = kwargs.get("container") or kwargs.get("name", "")
            return self._run_docker_cli(["stop", cid])
        elif cap == "docker.logs":
            cid = kwargs.get("container") or kwargs.get("name", "")
            lines = str(kwargs.get("lines", 50))
            return self._run_docker_cli(["logs", "--tail", lines, cid])
        elif cap == "docker.compose_up":
            path = kwargs.get("path") or "."
            return self._run_docker_cli(["compose", "-f", f"{path}/docker-compose.yml", "up", "-d"])
        elif cap == "docker.compose_down":
            path = kwargs.get("path") or "."
            return self._run_docker_cli(["compose", "-f", f"{path}/docker-compose.yml", "down"])
        else:
            return {"status": "success", "capability": capability, "params": kwargs}
