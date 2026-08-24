"""
Comprehensive Test Suite for M23 OS-Level Process Sandboxing & Workspace Isolation
Location: tests/test_sandbox_isolation.py
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
src_path = REPO_ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from desktop.native.sandbox.base_sandbox import IsolationLevel
from desktop.native.sandbox.sandbox_manager import SandboxManager
from desktop.native.sandbox.win32_job_sandbox import Win32JobSandbox
from desktop.native.sandbox.workspace_jail import WorkspaceJail


class TestWorkspaceJail:
    """Tests for workspace path confinement and adversarial out-of-bounds rejection."""

    def test_workspace_jail_allows_in_workspace_paths(self):
        jail = WorkspaceJail(workspace_root=str(REPO_ROOT))
        test_file = REPO_ROOT / "src" / "aura.py"
        assert jail.is_path_inside_workspace(test_file) is True

        valid, msg = jail.validate_command_paths(f"Get-Content '{test_file}'", cwd=str(REPO_ROOT))
        assert valid is True

    def test_workspace_jail_rejects_relative_traversal(self):
        jail = WorkspaceJail(workspace_root=str(REPO_ROOT))
        outside_rel = REPO_ROOT / ".." / "outside_secret.txt"
        assert jail.is_path_inside_workspace(outside_rel) is False

    def test_workspace_jail_adversarial_out_of_workspace_read(self):
        jail = WorkspaceJail(workspace_root=str(REPO_ROOT))
        # An existing host file outside workspace (e.g. Windows hosts file or system file)
        system_file = "C:\\Windows\\System32\\drivers\\etc\\hosts"
        if Path(system_file).exists():
            valid, msg = jail.validate_command_paths(f"Get-Content {system_file}", cwd=str(REPO_ROOT))
            assert valid is False
            assert "outside workspace root is blocked" in msg

    def test_workspace_jail_rejects_out_of_workspace_cwd(self):
        jail = WorkspaceJail(workspace_root=str(REPO_ROOT))
        valid, msg = jail.validate_command_paths("git status", cwd="C:\\Windows")
        assert valid is False
        assert "outside allowed workspace root" in msg


class TestWin32JobSandbox:
    """Tests for Windows Kernel Job Object limits and execution."""

    def test_win32_job_sandbox_roundtrip(self):
        sandbox = Win32JobSandbox(workspace_root=str(REPO_ROOT))
        assert sandbox.is_available() is True
        assert sandbox.isolation_level == IsolationLevel.JOB_OBJECT

        code, stdout, stderr = sandbox.execute("Write-Output 'JOB_SANDBOX_SUCCESS'", cwd=str(REPO_ROOT))
        assert code == 0
        assert "JOB_SANDBOX_SUCCESS" in stdout

    def test_win32_job_sandbox_enforces_workspace_jail(self):
        sandbox = Win32JobSandbox(workspace_root=str(REPO_ROOT))
        system_file = "C:\\Windows\\System32\\drivers\\etc\\hosts"
        if Path(system_file).exists():
            code, stdout, stderr = sandbox.execute(f"Get-Content {system_file}", cwd=str(REPO_ROOT))
            assert code != 0
            assert "Sandbox Workspace Jail Error" in stderr

    def test_win32_job_sandbox_health_check(self):
        sandbox = Win32JobSandbox(workspace_root=str(REPO_ROOT))
        hc = sandbox.health_check()
        assert hc["available"] is True
        assert hc["job_handle_active"] is True
        assert hc["max_memory_mb"] == 2048
        assert hc["max_active_processes"] == 16


class TestSandboxManagerAndCallerAwareness:
    """Tests for auto-negotiation and caller tier-awareness."""

    def test_sandbox_manager_auto_negotiation(self):
        mgr = SandboxManager.get_instance(workspace_root=str(REPO_ROOT))
        hc = mgr.health_check()
        assert hc["active_provider"] in ("RestrictedUserSandbox", "Win32JobSandbox", "DockerSandbox", "WSL2Sandbox")
        assert hc["isolation_level"] in ("restricted_user", "job_object", "container", "microvm")


    def test_terminal_manager_caller_tier_awareness_enforces_gauntlet(self):
        from desktop.native.managers.terminal_manager import TerminalManager

        term_mgr = TerminalManager()
        term_mgr.initialize()

        # When running on host-level JobObject tier, adversarial out-of-workspace commands are hard blocked
        system_file = "C:\\Windows\\System32\\drivers\\etc\\hosts"
        if Path(system_file).exists():
            res = term_mgr.execute("terminal.execute", arguments={"command": f"Get-Content {system_file}"})
            assert res.success is False
            assert "Workspace Jail security violation" in res.error
