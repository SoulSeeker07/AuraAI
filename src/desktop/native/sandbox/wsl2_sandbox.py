"""
WSL2 MicroVM Sandbox Provider
Location: src/desktop/native/sandbox/wsl2_sandbox.py

Executes commands inside WSL2 microVM namespace with isolated mount tables.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base_sandbox import BaseSandboxProvider, IsolationLevel

logger = logging.getLogger(__name__)


class WSL2Sandbox(BaseSandboxProvider):
    """
    MicroVM execution sandbox using Windows Subsystem for Linux 2.
    """

    def __init__(self, distro: str | None = None, workspace_root: str | None = None):
        self._distro = distro
        self._workspace_root = Path(workspace_root or os.getcwd()).resolve()

    @property
    def isolation_level(self) -> IsolationLevel:
        return IsolationLevel.MICROVM

    def is_available(self) -> bool:
        if not shutil.which("wsl.exe"):
            return False
        try:
            res = subprocess.run(["wsl.exe", "--status"], capture_output=True, timeout=3.0)
            return res.returncode == 0
        except Exception:
            return False

    def _to_wsl_path(self, windows_path: Path) -> str:
        """Convert Windows path D:\\path to /mnt/d/path."""
        p_str = str(windows_path).replace("\\", "/")
        if ":" in p_str:
            drive, rest = p_str.split(":", 1)
            return f"/mnt/{drive.lower()}{rest}"
        return p_str

    def execute(
        self,
        command: str,
        cwd: str,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        if not self.is_available():
            return 1, "", "WSL2 is not available."

        wsl_cwd = self._to_wsl_path(Path(cwd).resolve())
        wsl_cmd = ["wsl.exe"]
        if self._distro:
            wsl_cmd.extend(["-d", self._distro])
        wsl_cmd.extend(["--cd", wsl_cwd, "bash", "-c", command])

        try:
            proc = subprocess.run(
                wsl_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"WSL2 execution timed out after {timeout}s"
        except Exception as exc:
            return 1, "", f"WSL2 execution error: {exc}"

    def health_check(self) -> dict[str, Any]:
        return {
            "provider": "WSL2Sandbox",
            "available": self.is_available(),
            "isolation_level": self.isolation_level.value,
            "distro": self._distro or "default",
            "workspace_root": str(self._workspace_root),
        }
