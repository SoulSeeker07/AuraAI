"""
Phase 1 Native Desktop Manager Security Hardening & Adversarial Test Suite
Location: tests/test_phase1_manager_hardening.py

Validates:
1. Unified CryptographicApprovalAuthority process singleton, HMAC-SHA256 signing, replay attack protection.
2. SoftwareManager HMAC-gated installations, package argument sanitization, winreg enumeration.
3. SettingsManager HMAC-gated startup app persistence, wallpaper extension validation, timezone sanitization.
4. SecurityManager unconditional hard-block on firewall/antivirus disablement, gated firewall rules.
5. FileManager WorkspaceJail path confinement, ZipSlip traversal prevention, and executable execution blocks.
"""

import io
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
src_path = REPO_ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.desktop.native.managers.file_manager import FileManager
from src.desktop.native.managers.security_manager import SecurityManager
from src.desktop.native.managers.settings_manager import SettingsManager
from src.desktop.native.managers.software_manager import SoftwareManager
from src.desktop.native.managers.terminal_manager import TerminalManager
from src.desktop.native.security.approval_authority import (
    ApprovalTicket,
    CryptographicApprovalAuthority,
)


class TestSharedApprovalAuthority:
    """Tests for the centralized CryptographicApprovalAuthority service."""

    @pytest.fixture(autouse=True)
    def reset_authority(self):
        CryptographicApprovalAuthority.reset_instance()
        yield
        CryptographicApprovalAuthority.reset_instance()

    def test_singleton_shared_across_managers(self):
        auth1 = CryptographicApprovalAuthority.get_instance()
        auth2 = CryptographicApprovalAuthority.get_instance()
        assert auth1 is auth2

        term_mgr = TerminalManager()
        soft_mgr = SoftwareManager()
        sett_mgr = SettingsManager()
        sec_mgr = SecurityManager()
        file_mgr = FileManager()

        assert term_mgr.auth is auth1
        assert soft_mgr.auth is auth1
        assert sett_mgr.auth is auth1
        assert sec_mgr.auth is auth1
        assert file_mgr.auth is auth1

    def test_hmac_action_hash_canonicalization(self):
        auth = CryptographicApprovalAuthority.get_instance()
        # Different parameter dictionary ordering produces the exact same hash
        hash1 = auth.compute_action_hash("software.install", "git", {"version": "2.40", "source": "winget"})
        hash2 = auth.compute_action_hash("software.install", "git", {"source": "winget", "version": "2.40"})
        assert hash1 == hash2

        # Different parameter values produce different hashes
        hash3 = auth.compute_action_hash("software.install", "git", {"source": "winget", "version": "2.41"})
        assert hash1 != hash3

    def test_human_signing_and_single_use_redemption(self):
        auth = CryptographicApprovalAuthority.get_instance()
        ticket_id = auth.create_ticket("software.install", "ripgrep", {"source": "winget"})
        assert ticket_id.startswith("tkt_")

        ticket = auth.get_ticket(ticket_id)
        assert ticket is not None
        assert ticket.is_redeemed is False

        # Human UI signs the ticket
        sig = auth.generate_human_signature(ticket_id)
        assert sig is not None
        assert len(sig) == 64  # SHA-256 hex length

        # 1st Redemption: Must succeed
        valid, msg = auth.verify_and_redeem(ticket_id, sig, "software.install", "ripgrep", {"source": "winget"})
        assert valid is True
        assert ticket.is_redeemed is True

        # 2nd Redemption (Replay Attack): Must fail
        valid2, msg2 = auth.verify_and_redeem(ticket_id, sig, "software.install", "ripgrep", {"source": "winget"})
        assert valid2 is False
        assert "already been redeemed" in msg2

    def test_forged_and_tampered_signature_rejection(self):
        auth = CryptographicApprovalAuthority.get_instance()
        ticket_id = auth.create_ticket("pip.install", "numpy")
        forged_sig = "0" * 64

        valid, msg = auth.verify_and_redeem(ticket_id, forged_sig, "pip.install", "numpy")
        assert valid is False
        assert "signature verification failed" in msg

    def test_parameter_tampering_rejection(self):
        auth = CryptographicApprovalAuthority.get_instance()
        ticket_id = auth.create_ticket("software.install", "ripgrep", {"version": "1.0"})
        sig = auth.generate_human_signature(ticket_id)

        # Attacker modifies parameters during execution
        valid, msg = auth.verify_and_redeem(ticket_id, sig, "software.install", "ripgrep", {"version": "2.0"})
        assert valid is False
        assert "does not match" in msg

    def test_expired_ticket_rejection(self):
        auth = CryptographicApprovalAuthority.get_instance()
        ticket_id = auth.create_ticket("software.install", "curl", ttl_seconds=0.01)
        time.sleep(0.03)

        sig = auth.generate_human_signature(ticket_id)
        assert sig is None  # Cannot sign expired ticket


class TestSoftwareManagerHardening:
    """Tests for SoftwareManager HMAC authorization and sandbox execution."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        CryptographicApprovalAuthority.reset_instance()
        self.auth = CryptographicApprovalAuthority.get_instance()
        self.manager = SoftwareManager(auth=self.auth)
        self.manager.initialize()

    def test_software_install_without_ticket_fails_and_issues_ticket(self):
        res = self.manager.execute("software.install", arguments={"package": "Git.Git"})
        assert res.success is False
        assert "requires cryptographic human approval" in res.error
        assert res.data["requires_confirmation"] is True
        assert res.data["approval_ticket_id"].startswith("tkt_")
        assert res.data["action_type"] == "software.install"

    def test_software_install_with_forged_ticket_rejected(self):
        ticket_id = self.auth.create_ticket("software.install", "Git.Git", {"capability": "software.install", "target": "Git.Git"})
        res = self.manager.execute(
            "software.install",
            arguments={
                "package": "Git.Git",
                "approval_ticket_id": ticket_id,
                "approval_signature": "bad_signature_deadbeef" * 4,
            },
        )
        assert res.success is False
        assert "Human authorization failed" in res.error
        assert res.data.get("security_alert") == "unauthorized_or_forged_approval"

    def test_software_install_with_valid_signed_ticket_executes_host_installer(self):
        # Issue ticket through manager
        res_prompt = self.manager.execute("software.install", arguments={"package": "Git.Git"})
        ticket_id = res_prompt.data["approval_ticket_id"]

        # Human signs ticket out-of-band
        sig = self.auth.generate_human_signature(ticket_id)
        assert sig is not None

        # Execute and verify it invokes the approved host installer path
        with patch.object(
            self.manager, "_run_approved_installer", return_value=(0, "Successfully installed Git", "")
        ) as mock_host_installer:
            res_exec = self.manager.execute(
                "software.install",
                arguments={
                    "package": "Git.Git",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            assert res_exec.success is True
            assert res_exec.data["package"] == "Git.Git"
            assert "software_installed" in res_exec.events
            mock_host_installer.assert_called_once_with(
                ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget", "--accept-source-agreements", "--accept-package-agreements"]
            )

    def test_pip_install_with_valid_signed_ticket_executes_host_venv_pip(self):
        res_prompt = self.manager.execute("pip.install", arguments={"package": "pytest"})
        ticket_id = res_prompt.data["approval_ticket_id"]

        sig = self.auth.generate_human_signature(ticket_id)
        assert sig is not None

        with patch.object(
            self.manager, "_run_approved_installer", return_value=(0, "Successfully installed pytest", "")
        ) as mock_host_installer:
            res_exec = self.manager.execute(
                "pip.install",
                arguments={
                    "package": "pytest",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            assert res_exec.success is True
            assert res_exec.data["package"] == "pytest"
            assert "pip_installed" in res_exec.events
            mock_host_installer.assert_called_once_with([sys.executable, "-m", "pip", "install", "--index-url", "https://pypi.org/simple", "pytest"])

    def test_pip_install_package_substitution_adversarial_rejection(self):
        """
        Adversarial Test: Ticket signed for 'requests' cannot be redeemed to install a different package.
        Verifies cryptographic binding to the exact package target.
        """
        # 1. Request approval for legitimate package
        res_prompt = self.manager.execute("pip.install", arguments={"package": "requests"})
        ticket_id = res_prompt.data["approval_ticket_id"]

        # 2. Human signs ticket for 'requests'
        sig = self.auth.generate_human_signature(ticket_id)
        assert sig is not None

        # 3. Attacker attempts to redeem ticket against malicious substitute package
        with patch.object(self.manager, "_run_approved_installer") as mock_host_installer:
            res_tampered = self.manager.execute(
                "pip.install",
                arguments={
                    "package": "malicious-backdoor-pkg",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            assert res_tampered.success is False
            assert "Human authorization failed" in res_tampered.error
            assert res_tampered.data.get("security_alert") == "unauthorized_or_forged_approval"
            # Host installer must NEVER have been invoked
            mock_host_installer.assert_not_called()

    def test_software_install_package_substitution_adversarial_rejection(self):
        """
        Adversarial Test: Winget ticket signed for 'Git.Git' cannot be redeemed to install 'Mimikatz'.
        """
        res_prompt = self.manager.execute("software.install", arguments={"package": "Git.Git"})
        ticket_id = res_prompt.data["approval_ticket_id"]
        sig = self.auth.generate_human_signature(ticket_id)
        assert sig is not None

        with patch.object(self.manager, "_run_approved_installer") as mock_host_installer:
            res_tampered = self.manager.execute(
                "software.install",
                arguments={
                    "package": "Mimikatz.Mimikatz",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            assert res_tampered.success is False
            assert "Human authorization failed" in res_tampered.error
            mock_host_installer.assert_not_called()

    def test_pip_and_npm_installs_are_gated(self):
        # pip install without ticket
        pip_res = self.manager.execute("pip.install", arguments={"package": "requests"})
        assert pip_res.success is False
        assert pip_res.data["requires_confirmation"] is True

        # npm install without ticket
        npm_res = self.manager.execute("npm.install", arguments={"package": "typescript"})
        assert npm_res.success is False
        assert npm_res.data["requires_confirmation"] is True

    def test_package_name_argument_injection_rejected(self):
        # Flag injection
        res1 = self.manager.execute("software.install", arguments={"package": "--override -e evil"})
        assert res1.success is False
        assert "cannot start with flag" in res1.error

        # Shell metacharacter injection
        res2 = self.manager.execute("software.install", arguments={"package": "git; del C:\\*"})
        assert res2.success is False
        assert "illegal characters" in res2.error

    def test_software_list_installed_uses_winreg_safely(self):
        res = self.manager.execute("software.list_installed")
        assert res.success is True
        assert "installed" in res.data
        assert isinstance(res.data["installed"], list)


class TestSettingsManagerHardening:
    """Tests for SettingsManager persistence guardrails and input sanitization."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        CryptographicApprovalAuthority.reset_instance()
        self.auth = CryptographicApprovalAuthority.get_instance()
        self.manager = SettingsManager(auth=self.auth)
        self.manager.initialize()

    def test_startup_apps_add_requires_hmac_ticket(self):
        res = self.manager.execute("settings.startup_apps.add", arguments={"name": "BackdoorApp", "command": "calc.exe"})
        assert res.success is False
        assert "requires human approval" in res.error
        assert res.data["requires_confirmation"] is True
        ticket_id = res.data["approval_ticket_id"]

        # Sign ticket and execute
        sig = self.auth.generate_human_signature(ticket_id)
        with patch.object(self.manager, "_add_startup_app", return_value=None) as mock_add:
            res_exec = self.manager.execute(
                "settings.startup_apps.add",
                arguments={
                    "name": "BackdoorApp",
                    "command": "calc.exe",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            assert res_exec.success is True
            mock_add.assert_called_once_with("BackdoorApp", "calc.exe")

    def test_wallpaper_extension_validation(self, tmp_path):
        # Executable masquerading as wallpaper
        exe_file = tmp_path / "payload.exe"
        exe_file.write_text("MZ dummy binary")
        res = self.manager.execute("settings.wallpaper", arguments={"path": str(exe_file)})
        assert res.success is False
        assert "Invalid wallpaper image extension" in res.error

        # Non-existent wallpaper
        res_missing = self.manager.execute("settings.wallpaper", arguments={"path": str(tmp_path / "missing.png")})
        assert res_missing.success is False
        assert "not found" in res_missing.error

    def test_timezone_sanitization(self):
        # Shell injection attempt in timezone
        res_bad = self.manager.execute("settings.time_zone", arguments={"timezone": "UTC; rm -rf /"})
        assert res_bad.success is False
        assert "Invalid timezone format" in res_bad.error

        # Valid timezone
        with patch.object(self.manager._sandbox, "execute", return_value=(0, "OK", "")):
            res_good = self.manager.execute("settings.time_zone", arguments={"timezone": "UTC"})
            assert res_good.success is True


class TestSecurityManagerHardening:
    """Tests for SecurityManager unconditional hard-blocks on security degradation."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        CryptographicApprovalAuthority.reset_instance()
        self.auth = CryptographicApprovalAuthority.get_instance()
        self.manager = SecurityManager(auth=self.auth)
        self.manager.initialize()

    def test_disabling_firewall_is_unconditionally_hard_blocked(self):
        """Disabling host firewall must be rejected unconditionally with no ticket path."""
        res = self.manager.execute("security.firewall.disable")
        assert res.success is False
        assert "CRITICAL SECURITY POLICY VIOLATION" in res.error
        assert "hard-blocked without exception" in res.error
        assert "requires_confirmation" not in res.data
        assert "approval_ticket_id" not in res.data

        # Even if someone attempts to supply a signature or ticket
        res_with_fake = self.manager.execute(
            "security.firewall.disable",
            arguments={"approval_ticket_id": "tkt_123", "approval_signature": "sig_123"},
        )
        assert res_with_fake.success is False
        assert "CRITICAL SECURITY POLICY VIOLATION" in res_with_fake.error

    def test_firewall_add_rule_requires_hmac_ticket(self):
        res = self.manager.execute(
            "security.firewall.add_rule",
            arguments={"name": "InboundPort", "direction": "in", "action": "allow", "port": "8080"},
        )
        assert res.success is False
        assert res.data["requires_confirmation"] is True
        ticket_id = res.data["approval_ticket_id"]

        sig = self.auth.generate_human_signature(ticket_id)
        with patch.object(self.manager._sandbox, "execute", return_value=(0, "Rule added successfully", "")):
            res_exec = self.manager.execute(
                "security.firewall.add_rule",
                arguments={
                    "name": "InboundPort",
                    "direction": "in",
                    "action": "allow",
                    "port": "8080",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            assert res_exec.success is True
            assert res_exec.data["rule_name"] == "InboundPort"

    def test_privacy_clear_temp_canonical_confinement(self, tmp_path):
        fake_temp = tmp_path / "fake_temp"
        fake_temp.mkdir()
        (fake_temp / "temp_file.txt").write_text("temp data")
        (fake_temp / "temp_subdir").mkdir()
        (fake_temp / "temp_subdir" / "nested.txt").write_text("nested data")

        with patch.dict(os.environ, {"TEMP": str(fake_temp), "TMP": str(fake_temp)}):
            res = self.manager.execute("privacy.clear_temp")
            assert res.success is True
            assert res.data["cleared_files"] >= 2
            assert not (fake_temp / "temp_file.txt").exists()
            assert not (fake_temp / "temp_subdir").exists()


class TestFileManagerHardening:
    """Tests for FileManager WorkspaceJail path confinement, ZipSlip protection, and guardrails."""

    @pytest.fixture(autouse=True)
    def setup_workspace(self, tmp_path):
        self.workspace = tmp_path / "workspace"
        self.workspace.mkdir()
        CryptographicApprovalAuthority.reset_instance()
        self.auth = CryptographicApprovalAuthority.get_instance()
        self.manager = FileManager(workspace_root=str(self.workspace), auth=self.auth)
        self.manager.initialize()

    def test_out_of_workspace_write_hard_blocked(self, tmp_path):
        outside_file = tmp_path / "outside_secret.txt"
        res = self.manager.execute("file.write", arguments={"path": str(outside_file), "content": "pwned"})
        assert res.success is False
        assert "Workspace Jail security violation" in res.error
        assert not outside_file.exists()

    def test_out_of_workspace_deletion_hard_blocked(self, tmp_path):
        outside_file = tmp_path / "system_important.txt"
        outside_file.write_text("critical data")

        # Literal path
        res1 = self.manager.execute("file.delete", arguments={"path": str(outside_file)})
        assert res1.success is False
        assert "Workspace Jail security violation" in res1.error
        assert outside_file.exists()

        # Relative traversal path (.. / ..)
        rel_traversal = self.workspace / ".." / "system_important.txt"
        res2 = self.manager.execute("file.delete", arguments={"path": str(rel_traversal)})
        assert res2.success is False
        assert "Workspace Jail security violation" in res2.error
        assert outside_file.exists()

    def test_workspace_root_deletion_permanently_blocked(self):
        res = self.manager.execute("file.delete", arguments={"path": str(self.workspace)})
        assert res.success is False
        assert "Deleting the workspace root directory is permanently prohibited" in res.error
        assert self.workspace.exists()

    def test_critical_project_dir_deletion_requires_hmac_ticket(self):
        git_dir = self.workspace / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main")

        # Without ticket -> Gated
        res_gated = self.manager.execute("file.delete", arguments={"path": str(git_dir)})
        assert res_gated.success is False
        assert res_gated.data["requires_confirmation"] is True
        ticket_id = res_gated.data["approval_ticket_id"]

        # Sign ticket and delete
        sig = self.auth.generate_human_signature(ticket_id)
        res_exec = self.manager.execute(
            "file.delete",
            arguments={"path": str(git_dir), "approval_ticket_id": ticket_id, "approval_signature": sig},
        )
        assert res_exec.success is True
        assert not git_dir.exists()

    def test_zipslip_path_traversal_extraction_blocked(self, tmp_path):
        """Zip archive containing a path traversal member (e.g. ../../../evil.txt) must be blocked."""
        malicious_zip = self.workspace / "malicious.zip"
        with zipfile.ZipFile(malicious_zip, "w") as zf:
            zf.writestr("../evil.txt", "malicious payload outside extract dir")

        extract_target = self.workspace / "extracted"
        res = self.manager.execute(
            "file.decompress",
            arguments={"path": str(malicious_zip), "extract_to": str(extract_target)},
        )
        assert res.success is False
        assert "ZipSlip security violation" in res.error
        assert not (self.workspace / "evil.txt").exists()

    def test_executable_extension_open_with_blocked(self):
        malicious_exe = self.workspace / "script.ps1"
        malicious_exe.write_text("Write-Host 'malicious'")

        res = self.manager.execute("file.open_with", arguments={"path": str(malicious_exe)})
        assert res.success is False
        assert "Direct execution of executable extension" in res.error

    def test_safe_in_workspace_file_lifecycle(self):
        # 1. Create file
        res_write = self.manager.execute("file.write", arguments={"path": "hello.txt", "content": "Hello World!"})
        assert res_write.success is True
        file_path = self.workspace / "hello.txt"
        assert file_path.exists()

        # 2. Read file
        res_read = self.manager.execute("file.read", arguments={"path": "hello.txt"})
        assert res_read.success is True
        assert res_read.data["content"] == "Hello World!"

        # 3. File Info
        res_info = self.manager.execute("file.info", arguments={"path": "hello.txt"})
        assert res_info.success is True
        assert res_info.data["size_bytes"] == 12

        # 4. Delete file
        res_del = self.manager.execute("file.delete", arguments={"path": "hello.txt"})
        assert res_del.success is True
        assert not file_path.exists()
