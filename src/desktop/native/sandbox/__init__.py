"""
OS Process Sandboxing & Workspace Isolation Subsystem
Location: src/desktop/native/sandbox/__init__.py
"""

from .account_provisioner import AccountProvisioner, SANDBOX_USER_NAME
from .base_sandbox import BaseSandboxProvider, IsolationLevel
from .docker_sandbox import DockerSandbox
from .restricted_user_sandbox import RestrictedUserSandbox
from .sandbox_manager import SandboxManager
from .win32_job_sandbox import Win32JobSandbox
from .workspace_jail import WorkspaceJail
from .wsl2_sandbox import WSL2Sandbox

__all__ = [
    "BaseSandboxProvider",
    "IsolationLevel",
    "AccountProvisioner",
    "SANDBOX_USER_NAME",
    "DockerSandbox",
    "WSL2Sandbox",
    "RestrictedUserSandbox",
    "Win32JobSandbox",
    "WorkspaceJail",
    "SandboxManager",
]
