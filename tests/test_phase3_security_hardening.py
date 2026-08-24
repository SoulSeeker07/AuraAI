"""
Phase 3 Security Hardening & Cryptographic Audit Ledger Test Suite
Location: tests/test_phase3_security_hardening.py

Validates:
1. Host package manager registry pinning (pip --index-url, npm --registry/--ignore-scripts, winget --source).
2. Subprocess environment variable sanitization (stripping PIP_INDEX_URL, PYTHONPATH, etc.).
3. npm lifecycle script gating via dedicated npm.install_with_scripts capability.
4. BrowserEngine URL security validation & Playwright route interception for XHR/fetch SSRF protection.
5. Cryptographic hash-chained and HMAC-signed SecurityAuditLogger integrity and tamper-evidence.
"""

import json
import os
import sys
import tempfile
import unittest.mock
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
src_path = REPO_ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from browser.engine import BrowserEngine, validate_url_security
from desktop.native.managers.software_manager import SoftwareManager
from desktop.native.security.approval_authority import CryptographicApprovalAuthority
from desktop.native.security.audit_logger import SecurityAuditLogger
from desktop.native.security.governance import (
    HOST_CONTEXT_MUTATION_EXCEPTIONS,
    is_host_context_exception,
)
from desktop.native.security.network_policy import NetworkPolicyEngine


class TestHostInstallerRegistryPinning:
    """Validates SoftwareManager registry pinning and environment variable sanitization."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        CryptographicApprovalAuthority.reset_instance()
        self.auth = CryptographicApprovalAuthority.get_instance()
        self.manager = SoftwareManager(auth=self.auth)
        self.manager.initialize()

    def test_governance_includes_npm_install_with_scripts(self):
        assert "npm.install_with_scripts" in HOST_CONTEXT_MUTATION_EXCEPTIONS
        assert is_host_context_exception("npm.install_with_scripts") is True

    def test_pip_rejects_extra_index_url_injection(self):
        res = self.manager.execute("pip.install", arguments={"package": "requests --extra-index-url https://evil.com"})
        assert res.success is False
        assert "Forbidden installer flag injection" in res.error

    def test_pip_rejects_find_links_and_trusted_host_injection(self):
        res1 = self.manager.execute("pip.install", arguments={"package": "requests --find-links /tmp/wheels"})
        assert res1.success is False
        assert "Forbidden installer flag injection" in res1.error

        res2 = self.manager.execute("pip.install", arguments={"package": "requests --trusted-host evil.com"})
        assert res2.success is False
        assert "Forbidden installer flag injection" in res2.error

    def test_pip_install_enforces_pinned_pypi_index(self):
        res_prompt = self.manager.execute("pip.install", arguments={"package": "requests"})
        ticket_id = res_prompt.data["approval_ticket_id"]
        sig = self.auth.generate_human_signature(ticket_id)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Successfully installed", stderr="")
            res_exec = self.manager.execute(
                "pip.install",
                arguments={"package": "requests", "approval_ticket_id": ticket_id, "approval_signature": sig},
            )
            assert res_exec.success is True
            mock_run.assert_called_once()
            called_cmd = mock_run.call_args[0][0]
            assert "--index-url" in called_cmd
            assert "https://pypi.org/simple" in called_cmd
            assert "requests" in called_cmd

    def test_npm_install_enforces_ignore_scripts_by_default(self):
        res_prompt = self.manager.execute("npm.install", arguments={"package": "lodash"})
        ticket_id = res_prompt.data["approval_ticket_id"]
        sig = self.auth.generate_human_signature(ticket_id)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="added 1 package", stderr="")
            res_exec = self.manager.execute(
                "npm.install",
                arguments={"package": "lodash", "approval_ticket_id": ticket_id, "approval_signature": sig},
            )
            assert res_exec.success is True
            called_cmd = mock_run.call_args[0][0]
            assert "--ignore-scripts" in called_cmd
            assert "--registry=https://registry.npmjs.org" in called_cmd

    def test_npm_install_with_scripts_requires_dedicated_capability(self):
        res_prompt = self.manager.execute("npm.install_with_scripts", arguments={"package": "native-addon"})
        assert res_prompt.success is False
        assert res_prompt.data["action_type"] == "npm.install_with_scripts"
        ticket_id = res_prompt.data["approval_ticket_id"]
        sig = self.auth.generate_human_signature(ticket_id)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="built native module", stderr="")
            res_exec = self.manager.execute(
                "npm.install_with_scripts",
                arguments={"package": "native-addon", "approval_ticket_id": ticket_id, "approval_signature": sig},
            )
            assert res_exec.success is True
            called_cmd = mock_run.call_args[0][0]
            assert "--ignore-scripts" not in called_cmd
            assert "--registry=https://registry.npmjs.org" in called_cmd

    def test_winget_install_enforces_source_winget(self):
        res_prompt = self.manager.execute("software.install", arguments={"package": "Git.Git"})
        ticket_id = res_prompt.data["approval_ticket_id"]
        sig = self.auth.generate_human_signature(ticket_id)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Successfully installed", stderr="")
            res_exec = self.manager.execute(
                "software.install",
                arguments={"package": "Git.Git", "approval_ticket_id": ticket_id, "approval_signature": sig},
            )
            assert res_exec.success is True
            called_cmd = mock_run.call_args[0][0]
            assert "--source" in called_cmd
            assert "winget" in called_cmd

    def test_environment_variables_sanitization(self):
        """Verify that PIP_INDEX_URL and hook env vars are stripped before spawning subprocess."""
        os.environ["PIP_INDEX_URL"] = "https://malicious-mirror.org/simple"
        os.environ["PIP_EXTRA_INDEX_URL"] = "https://another-mirror.org"
        os.environ["NODE_OPTIONS"] = "--require /tmp/malicious.js"

        try:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                self.manager._run_approved_installer(["echo", "test"])
                mock_run.assert_called_once()
                spawned_env = mock_run.call_args[1].get("env", {})
                assert "PIP_INDEX_URL" not in spawned_env
                assert "PIP_EXTRA_INDEX_URL" not in spawned_env
                assert "NODE_OPTIONS" not in spawned_env
        finally:
            os.environ.pop("PIP_INDEX_URL", None)
            os.environ.pop("PIP_EXTRA_INDEX_URL", None)
            os.environ.pop("NODE_OPTIONS", None)


class TestBrowserEngineSSRFProtection:
    """Validates BrowserEngine URL security and Playwright route interception."""

    def test_browser_validate_url_blocks_metadata_and_private_ips(self):
        v1, err1 = validate_url_security("http://169.254.169.254/latest/meta-data")
        assert v1 is False
        assert "Navigation blocked by security policy" in err1

        v2, err2 = validate_url_security("http://metadata.google.internal/computeMetadata/v1")
        assert v2 is False
        assert "Navigation blocked by security policy" in err2

        v3, err3 = validate_url_security("http://192.168.1.1:8080/router")
        assert v3 is False
        assert "Navigation blocked by security policy" in err3

        v4, err4 = validate_url_security("http://[fd00:ec2::254]/latest/meta-data")
        assert v4 is False
        assert "Navigation blocked by security policy" in err4

    @pytest.mark.asyncio
    async def test_browser_route_interceptor_aborts_xhr_fetch_to_metadata(self):
        engine = BrowserEngine()
        mock_route = AsyncMock()
        mock_request = MagicMock()
        mock_request.url = "http://169.254.169.254/latest/meta-data"
        mock_request.method = "GET"

        await engine._route_network_policy_interceptor(mock_route, mock_request)
        mock_route.abort.assert_called_once_with("blockedbyclient")
        mock_route.continue_.assert_not_called()

    @pytest.mark.asyncio
    async def test_browser_route_interceptor_aborts_xhr_fetch_to_private_lan(self):
        engine = BrowserEngine()
        mock_route = AsyncMock()
        mock_request = MagicMock()
        mock_request.url = "http://10.0.0.1:8080/api/keys"
        mock_request.method = "POST"

        await engine._route_network_policy_interceptor(mock_route, mock_request)
        mock_route.abort.assert_called_once_with("blockedbyclient")
        mock_route.continue_.assert_not_called()

    @pytest.mark.asyncio
    async def test_browser_route_interceptor_allows_safe_urls(self):
        engine = BrowserEngine()
        mock_route = AsyncMock()
        mock_request = MagicMock()
        mock_request.url = "https://github.com/torvalds/linux"
        mock_request.method = "GET"

        with patch.object(NetworkPolicyEngine.get_instance(), "resolve_destination", return_value=["140.82.121.4"]):
            await engine._route_network_policy_interceptor(mock_route, mock_request)
            mock_route.continue_.assert_called_once()
            mock_route.abort.assert_not_called()


class TestAuditLedgerCryptographicIntegrity:
    """Validates SecurityAuditLogger hash chain continuity, signatures, and tamper detection."""

    @pytest.fixture
    def temp_audit_logger(self):
        temp_dir = tempfile.mkdtemp()
        log_file = Path(temp_dir) / "audit_ledger.jsonl"
        secret = b"test_secret_audit_key_123456789012"
        SecurityAuditLogger.reset_instance()
        logger_instance = SecurityAuditLogger(log_path=log_file, secret_key=secret, enable_registry_anchor=False)
        yield logger_instance
        SecurityAuditLogger.reset_instance()

    def test_audit_ledger_lifecycle_events_and_verification(self, temp_audit_logger):
        # 1. Log sequential lifecycle events
        temp_audit_logger.log_event(
            event_type="TICKET_ISSUED",
            action_type="pip.install",
            target="requests",
            ticket_id="tkt_123456",
            status="PENDING",
            details={"package": "requests"},
        )
        temp_audit_logger.log_event(
            event_type="TICKET_SIGNED",
            action_type="pip.install",
            target="requests",
            ticket_id="tkt_123456",
            status="SIGNED",
            details={"operator": "human_admin"},
        )
        temp_audit_logger.log_event(
            event_type="TICKET_REDEEMED",
            action_type="pip.install",
            target="requests",
            ticket_id="tkt_123456",
            status="REDEEMED",
            details={"package": "requests"},
        )

        valid, msg, stats = temp_audit_logger.verify_chain_integrity()
        assert valid is True
        assert stats["verified_records"] == 3
        assert "verified successfully" in msg

    def test_audit_ledger_detects_record_tampering(self, temp_audit_logger):
        temp_audit_logger.log_event("TICKET_ISSUED", "pip.install", "requests", "PENDING")
        temp_audit_logger.log_event("TICKET_SIGNED", "pip.install", "requests", "SIGNED")
        temp_audit_logger.log_event("TICKET_REDEEMED", "pip.install", "requests", "REDEEMED")

        # Adversarially modify record #1 (change target to malicious package)
        with open(temp_audit_logger.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        record_1 = json.loads(lines[1])
        record_1["target"] = "malicious_backdoor"
        lines[1] = json.dumps(record_1) + "\n"

        with open(temp_audit_logger.log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        valid, err_msg, stats = temp_audit_logger.verify_chain_integrity()
        assert valid is False
        assert "Entry hash mismatch" in err_msg or "Invalid HMAC signature" in err_msg

    def test_audit_ledger_detects_chain_link_break(self, temp_audit_logger):
        temp_audit_logger.log_event("TICKET_ISSUED", "pip.install", "requests", "PENDING")
        temp_audit_logger.log_event("TICKET_SIGNED", "pip.install", "requests", "SIGNED")

        with open(temp_audit_logger.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        record_1 = json.loads(lines[1])
        record_1["prev_hash"] = "f" * 64
        lines[1] = json.dumps(record_1) + "\n"

        with open(temp_audit_logger.log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        valid, err_msg, stats = temp_audit_logger.verify_chain_integrity()
        assert valid is False
        assert "Broken hash chain link" in err_msg

    def test_audit_ledger_detects_record_deletion(self, temp_audit_logger):
        temp_audit_logger.log_event("EVENT_0", "action", "target0")
        temp_audit_logger.log_event("EVENT_1", "action", "target1")
        temp_audit_logger.log_event("EVENT_2", "action", "target2")

        with open(temp_audit_logger.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Delete middle record (index 1)
        del lines[1]

        with open(temp_audit_logger.log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        valid, err_msg, stats = temp_audit_logger.verify_chain_integrity()
        assert valid is False
        assert "Index sequence violation" in err_msg or "Broken hash chain link" in err_msg

    def test_audit_ledger_detects_wholesale_file_deletion_or_emptying(self, temp_audit_logger):
        """Adversarial Test: Deleting or zeroing the log file after events were recorded is detected."""
        temp_audit_logger.log_event("TICKET_ISSUED", "pip.install", "requests")
        temp_audit_logger.log_event("TICKET_SIGNED", "pip.install", "requests")
        temp_audit_logger.log_event("TICKET_REDEEMED", "pip.install", "requests")

        # Zero out the log file wholesale
        with open(temp_audit_logger.log_path, "w", encoding="utf-8") as f:
            f.write("")

        valid, err_msg, stats = temp_audit_logger.verify_chain_integrity()
        assert valid is False
        assert "Rollback / Deletion attack detected" in err_msg

    def test_audit_ledger_detects_rollback_and_replacement_from_zero(self, temp_audit_logger):
        """Adversarial Test: Replacing historical chain with a short fresh chain starting from 0 is detected."""
        for i in range(5):
            temp_audit_logger.log_event(f"EVENT_{i}", "action", f"target_{i}")

        # Attacker truncates and writes a single valid-looking record at index 0
        SecurityAuditLogger.reset_instance()
        # Create a fresh single record logger pointing to same path but separate secret
        fresh_logger = SecurityAuditLogger(log_path=temp_audit_logger.log_path, secret_key=temp_audit_logger._secret_key)
        # Note: fresh_logger recovered high-water mark = 5 from the signed checkpoint on disk!
        with open(temp_audit_logger.log_path, "w", encoding="utf-8") as f:
            f.write("")

        fresh_logger.log_event("CLEAN_LOOKING_EVENT_0", "action", "clean_target")

        valid, err_msg, stats = fresh_logger.verify_chain_integrity()
        assert valid is False
        assert (
            "Broken hash chain link" in err_msg
            or "Truncation attack detected" in err_msg
            or "Rollback" in err_msg
        )

    def test_audit_ledger_recovers_high_water_mark_from_checkpoint_across_restarts(self, temp_audit_logger):
        """Verify signed checkpoint persistence enables post-restart truncation detection."""
        temp_audit_logger.log_event("EVT_0", "act", "tgt0")
        temp_audit_logger.log_event("EVT_1", "act", "tgt1")
        temp_audit_logger.log_event("EVT_2", "act", "tgt2")

        # Restart logger instance
        SecurityAuditLogger.reset_instance()
        restarted_logger = SecurityAuditLogger(
            log_path=temp_audit_logger.log_path, secret_key=temp_audit_logger._secret_key
        )
        assert restarted_logger.high_water_mark == 3

        # Simulate attacker deleting last record
        with open(temp_audit_logger.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(temp_audit_logger.log_path, "w", encoding="utf-8") as f:
            f.writelines(lines[:2])  # only write 2 records

        valid, err_msg, stats = restarted_logger.verify_chain_integrity()
        assert valid is False
        assert "Truncation attack detected" in err_msg

    def test_audit_ledger_registry_anchor_detects_disk_wipe(self, temp_audit_logger):
        """
        Adversarial Test: When BOTH ledger file and checkpoint are wiped from disk,
        the out-of-band Windows Registry anchor provides historical high-water mark continuity
        and alerts on unauthorized log erasure.
        """
        secret = temp_audit_logger._secret_key
        # Simulate registry anchor stating high_water_mark = 10 and a valid signed hash
        fake_last_hash = "a" * 64
        fake_hwm = 10
        fake_sig = temp_audit_logger._compute_signature(f"{fake_hwm - 1}:{fake_last_hash}")

        with patch.object(
            SecurityAuditLogger,
            "_load_registry_anchor",
            return_value=(True, fake_hwm, fake_last_hash),
        ):
            # Instantiate fresh logger pointing to empty directory (both files missing)
            wiped_dir = tempfile.mkdtemp()
            wiped_log = Path(wiped_dir) / "audit_ledger.jsonl"

            recovered_logger = SecurityAuditLogger(log_path=wiped_log, secret_key=secret, enable_registry_anchor=True)
            assert recovered_logger.high_water_mark == 10

            valid, err_msg, stats = recovered_logger.verify_chain_integrity()
            assert valid is False
            assert "Rollback / Deletion attack detected" in err_msg
            assert stats["high_water_mark"] == 10

    def test_audit_logger_storage_health_check(self, temp_audit_logger):
        healthy, msg, details = temp_audit_logger.check_storage_health()
        assert healthy is True
        assert details["log_writable"] is True
        assert "fully operational" in msg
