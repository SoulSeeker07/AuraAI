"""
Base Sandbox Provider Interface
Location: src/desktop/native/sandbox/base_sandbox.py

Defines the contract for OS-level execution sandboxes across container,
microVM, Windows Job Object, and workspace-jailed environments.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class IsolationLevel(Enum):
    """Hierarchy of isolation levels supported by Aura AI."""
    CONTAINER = "container"              # Docker / Podman container (Filesystem detached)
    MICROVM = "microvm"                  # WSL2 / Hyper-V microVM (Separate kernel & mount table)
    RESTRICTED_USER = "restricted_user"  # Dedicated service account + NTFS DACL DENY isolation
    JOB_OBJECT = "job_object"            # Windows Kernel Job Object + Workspace Jail (Host-hardened)
    UNISOLATED = "unisolated"            # Unrestricted process (Development fallback only)



class BaseSandboxProvider(ABC):
    """Abstract base class for all process sandboxing providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this sandbox provider can run in the current environment."""
        pass

    @property
    @abstractmethod
    def isolation_level(self) -> IsolationLevel:
        """Return the isolation level guaranteed by this provider."""
        pass

    @abstractmethod
    def execute(
        self,
        command: str,
        cwd: str,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """
        Execute command inside the sandbox.
        
        Returns:
            (returncode, stdout, stderr)
        """
        pass

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return health and status diagnostic metrics."""
        pass
