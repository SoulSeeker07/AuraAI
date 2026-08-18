"""
Docker Container Sandbox Provider
Location: src/desktop/native/sandbox/docker_sandbox.py

Executes commands inside a disposable or ephemeral Docker container
with ONLY the active project workspace bind-mounted.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base_sandbox import BaseSandboxProvider, IsolationLevel

logger = logging.getLogger(__name__)


class DockerSandbox(BaseSandboxProvider):
    """
    Containerized execution sandbox providing full host filesystem & credential detachment.
    """

    def __init__(self, image: str = "python:3.11-slim", workspace_root: str | None = None):
        self._image = image
        self._workspace_root = Path(workspace_root or os.getcwd()).resolve()

    @property
    def isolation_level(self) -> IsolationLevel:
        return IsolationLevel.CONTAINER

    def is_available(self) -> bool:
        if not shutil.which("docker"):
            return False
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=3.0)
            return res.returncode == 0
        except Exception:
            return False

    def execute(
        self,
        command: str,
        cwd: str,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        if not self.is_available():
            return 1, "", "Docker daemon is not available."

        # Bind mount workspace directory to /workspace inside container
        ws_str = str(self._workspace_root).replace("\\", "/")
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{ws_str}:/workspace:rw",
            "-w", "/workspace",
            "--memory=2g",
            "--cpus=2.0",
            self._image,
            "sh", "-c", command,
        ]

        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Docker execution timed out after {timeout}s"
        except Exception as exc:
            return 1, "", f"Docker execution error: {exc}"

    def health_check(self) -> dict[str, Any]:
        return {
            "provider": "DockerSandbox",
            "available": self.is_available(),
            "isolation_level": self.isolation_level.value,
            "image": self._image,
            "workspace_root": str(self._workspace_root),
        }
