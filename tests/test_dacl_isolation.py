"""
Tests for Dedicated Low-Privilege Service Account (Path B) & DACL Isolation
Location: tests/test_dacl_isolation.py
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.desktop.native.sandbox.account_provisioner import AccountProvisioner, SANDBOX_USER_NAME
from src.desktop.native.sandbox.base_sandbox import IsolationLevel
from src.desktop.native.sandbox.restricted_user_sandbox import RestrictedUserSandbox
from src.desktop.native.sandbox.sandbox_manager import SandboxManager


class TestAccountProvisioner:
    """Tests for AccountProvisioner query and configuration contracts."""

    def test_account_provisioner_initialization(self):
        prov = AccountProvisioner(SANDBOX_USER_NAME)
        assert prov.username == SANDBOX_USER_NAME

    def test_account_provisioner_is_admin_check(self):
        # Checks that is_admin returns a boolean without throwing an exception
        is_adm = AccountProvisioner.is_admin()
        assert isinstance(is_adm, bool)


class TestRestrictedUserSandbox:
    """Tests for RestrictedUserSandbox provider lifecycle and fallback."""

    def test_restricted_user_sandbox_unprovisioned_state(self):
        sandbox = RestrictedUserSandbox(workspace_root=str(REPO_ROOT))
        assert sandbox.isolation_level == IsolationLevel.RESTRICTED_USER

        # If password is not set or account does not exist, is_available is False
        if not sandbox._provisioner.account_exists() or not sandbox._password:
            assert sandbox.is_available() is False

    def test_restricted_user_sandbox_graceful_fallback_execution(self):
        # When unprovisioned, execute() gracefully delegates to Win32JobSandbox
        sandbox = RestrictedUserSandbox(workspace_root=str(REPO_ROOT))
        code, stdout, stderr = sandbox.execute("Write-Output 'RESTRICTED_FALLBACK_OK'", cwd=str(REPO_ROOT))
        assert code == 0
        assert "RESTRICTED_FALLBACK_OK" in stdout

    def test_restricted_user_sandbox_health_check(self):
        sandbox = RestrictedUserSandbox(workspace_root=str(REPO_ROOT))
        hc = sandbox.health_check()
        assert hc["provider"] == "RestrictedUserSandbox"
        assert hc["isolation_level"] == "restricted_user"
        assert hc["username"] == SANDBOX_USER_NAME
        assert isinstance(hc["account_exists"], bool)


class TestSandboxManagerPathBNegotiation:
    """Tests for SandboxManager negotiation chain with Path B."""

    def test_sandbox_manager_contains_all_four_providers(self):
        mgr = SandboxManager(workspace_root=str(REPO_ROOT))
        provider_names = [p.__class__.__name__ for p in mgr._providers]
        assert "DockerSandbox" in provider_names
        assert "WSL2Sandbox" in provider_names
        assert "RestrictedUserSandbox" in provider_names
        assert "Win32JobSandbox" in provider_names

    def test_sandbox_manager_executes_safely_in_workspace(self):
        mgr = SandboxManager(workspace_root=str(REPO_ROOT))
        code, stdout, stderr = mgr.execute("Write-Output 'MGR_EXECUTION_OK'", cwd=str(REPO_ROOT))
        assert code == 0
        assert "MGR_EXECUTION_OK" in stdout


class TestAdversarialDACLKernelEnforcement:
    """
    Direct Adversarial Tests against the provisioned AuraSandboxUser.
    Verifies that the Windows NTFS kernel driver rejects unauthorized reads and tampering.
    """

    @pytest.fixture(autouse=True)
    def check_provisioning_status(self):
        prov = AccountProvisioner(SANDBOX_USER_NAME)
        self.account_ready = prov.account_exists()

    def test_adversarial_direct_credential_read_denied(self):
        """Test 1: Direct directory/file read of host user credentials must return Access is denied."""
        if not self.account_ready:
            pytest.skip("AuraSandboxUser not yet provisioned via scripts/setup_sandbox_account.py")

        sandbox = RestrictedUserSandbox(workspace_root=str(REPO_ROOT))
        user_profile = os.environ.get("USERPROFILE", "C:\\Users\\default")
        target_path = f"{user_profile}\\.ssh"

        code, stdout, stderr = sandbox.execute(f"Get-ChildItem '{target_path}'", cwd=str(REPO_ROOT))
        assert code != 0
        assert "Access is denied" in stderr or "PermissionDenied" in stderr or "ItemExistsUnauthorizedAccessError" in stderr

    def test_adversarial_dotnet_reflection_read_denied(self):
        """Test 2: .NET IO reflection read must trigger UnauthorizedAccessException."""
        if not self.account_ready:
            pytest.skip("AuraSandboxUser not yet provisioned via scripts/setup_sandbox_account.py")

        sandbox = RestrictedUserSandbox(workspace_root=str(REPO_ROOT))
        user_profile = os.environ.get("USERPROFILE", "C:\\Users\\default")
        cmd = f"[System.IO.Directory]::GetFiles('{user_profile}\\.ssh')"

        code, stdout, stderr = sandbox.execute(cmd, cwd=str(REPO_ROOT))
        assert code != 0
        assert "UnauthorizedAccessException" in stderr or "is denied" in stderr

    def test_adversarial_project_secret_read_denied(self):
        """Test 3: Reading .env secret file in workspace must return Access is denied."""
        if not self.account_ready:
            pytest.skip("AuraSandboxUser not yet provisioned via scripts/setup_sandbox_account.py")

        sandbox = RestrictedUserSandbox(workspace_root=str(REPO_ROOT))
        env_file = REPO_ROOT / ".env"

        code, stdout, stderr = sandbox.execute(f"Get-Content '{env_file}'", cwd=str(REPO_ROOT))
        assert code != 0
        assert "is denied" in stderr or "PermissionDenied" in stderr or "UnauthorizedAccessException" in stderr

    def test_adversarial_provisioning_script_tampering_denied(self):
        """Test 4: Modifying provisioning scripts must return Access is denied."""
        if not self.account_ready:
            pytest.skip("AuraSandboxUser not yet provisioned via scripts/setup_sandbox_account.py")

        sandbox = RestrictedUserSandbox(workspace_root=str(REPO_ROOT))
        setup_script = REPO_ROOT / "scripts" / "setup_sandbox_account.py"

        cmd = f"Set-Content -Path '{setup_script}' -Value '# hacked'"
        code, stdout, stderr = sandbox.execute(cmd, cwd=str(REPO_ROOT))
        assert code != 0
        assert "is denied" in stderr or "UnauthorizedAccessException" in stderr

    def test_adversarial_direct_file_read_in_ssh_denied(self):
        """Test 5: Direct file read attempt within .ssh must return Access is denied / ItemExistsUnauthorizedAccessError."""
        if not self.account_ready:
            pytest.skip("AuraSandboxUser not yet provisioned via scripts/setup_sandbox_account.py")

        sandbox = RestrictedUserSandbox(workspace_root=str(REPO_ROOT))
        user_profile = os.environ.get("USERPROFILE", "C:\\Users\\default")
        target_file = f"{user_profile}\\.ssh\\known_hosts"

        code, stdout, stderr = sandbox.execute(f"Get-Content '{target_file}'", cwd=str(REPO_ROOT))
        assert code != 0
        assert "is denied" in stderr or "PermissionDenied" in stderr or "ItemNotFoundException" in stderr or "UnauthorizedAccess" in stderr


