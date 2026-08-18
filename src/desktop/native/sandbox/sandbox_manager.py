"""
Sandbox Manager
Location: src/desktop/native/sandbox/sandbox_manager.py

Orchestrates multi-tier process sandboxing providers (Docker -> WSL2 -> Win32JobSandbox).
Auto-negotiates the highest available isolation tier on system startup and enforces workspace jails.
"""

import logging
import os
from pathlib import Path
from typing import Any

from .base_sandbox import BaseSandboxProvider, IsolationLevel
from .docker_sandbox import DockerSandbox
from .restricted_user_sandbox import RestrictedUserSandbox
from .win32_job_sandbox import Win32JobSandbox
from .wsl2_sandbox import WSL2Sandbox

logger = logging.getLogger(__name__)


class SandboxManager:
    """
    Central manager and auto-negotiator for Aura AI process execution sandboxes.
    """

    _instance: "SandboxManager | None" = None

    def __init__(self, workspace_root: str | None = None):
        self._workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self._providers: list[BaseSandboxProvider] = [
            DockerSandbox(workspace_root=str(self._workspace_root)),
            WSL2Sandbox(workspace_root=str(self._workspace_root)),
            RestrictedUserSandbox(workspace_root=str(self._workspace_root)),
            Win32JobSandbox(workspace_root=str(self._workspace_root)),
        ]
        self._active_provider: BaseSandboxProvider = self._negotiate_provider()


    @classmethod
    def get_instance(cls, workspace_root: str | None = None) -> "SandboxManager":
        if cls._instance is None:
            cls._instance = cls(workspace_root)
        return cls._instance

    def _negotiate_provider(self) -> BaseSandboxProvider:
        """Select the highest-tier isolation provider available on the host system."""
        for provider in self._providers:
            if provider.is_available():
                logger.info(
                    f"Selected active sandbox provider: {provider.__class__.__name__} "
                    f"[{provider.isolation_level.value}]"
                )
                return provider

        # Fallback to Win32JobSandbox default
        return self._providers[-1]

    @property
    def active_provider(self) -> BaseSandboxProvider:
        return self._active_provider

    @property
    def isolation_level(self) -> IsolationLevel:
        return self._active_provider.isolation_level

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def set_workspace_root(self, root: str) -> None:
        self._workspace_root = Path(root).resolve()
        # Update providers
        for p in self._providers:
            if hasattr(p, "_workspace_root"):
                p._workspace_root = self._workspace_root
            if hasattr(p, "_workspace_jail"):
                p._workspace_jail.set_workspace_root(str(self._workspace_root))

    def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command through the active sandbox provider."""
        exec_cwd = str(Path(cwd or self._workspace_root).resolve())
        return self._active_provider.execute(
            command=command,
            cwd=exec_cwd,
            timeout=timeout,
            env=env,
        )

    def health_check(self) -> dict[str, Any]:
        return {
            "active_provider": self._active_provider.__class__.__name__,
            "isolation_level": self.isolation_level.value,
            "workspace_root": str(self._workspace_root),
            "provider_details": self._active_provider.health_check(),
        }
