"""
Phase 2 Network Egress Filtering & Domain Allowlisting Test Suite
Location: tests/test_phase2_network_egress.py

Validates:
1. Centralized Governance Policy constants consistency.
2. NetworkPolicyEngine SSRF and Cloud Metadata hard-blocks (IPv4 & IPv6).
3. DNS Rebinding protection (validating resolved IPs against Tier-0 blocks).
4. HTTP redirect per-hop validation against metadata/private endpoints.
5. Developer domain allowlisting for PyPI, npm, GitHub, crates.io.
6. Terminal Security Gauntlet network extraction and egress interception.
7. NetworkManager mutating control capability HMAC-SHA256 human approval gates.
"""

import ipaddress
import os
import sys
import unittest.mock
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

from src.desktop.native.managers.network_manager import NetworkManager
from src.desktop.native.managers.terminal_manager import CommandRiskTier, TerminalManager
from src.desktop.native.security.approval_authority import CryptographicApprovalAuthority
from src.desktop.native.security.governance import (
    DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST,
    HARD_BLOCKED_HOSTNAMES,
    HARD_BLOCKED_IP_NETWORKS,
    HOST_CONTEXT_MUTATION_EXCEPTIONS,
    UNCONDITIONAL_HARD_BLOCKED_CAPABILITIES,
    is_host_context_exception,
    is_unconditionally_hard_blocked,
)
from src.desktop.native.security.network_policy import EgressDecision, NetworkPolicyEngine


class TestNetworkGovernanceConstants:
    """Validates centralized governance policy constants."""

    def test_governance_constants_completeness(self):
        assert "software.install" in HOST_CONTEXT_MUTATION_EXCEPTIONS
        assert "pip.install" in HOST_CONTEXT_MUTATION_EXCEPTIONS
        assert is_host_context_exception("pip.install") is True
        assert is_host_context_exception("terminal.execute") is False

        assert "security.firewall.disable" in UNCONDITIONAL_HARD_BLOCKED_CAPABILITIES
        assert "security.defender.disable" in UNCONDITIONAL_HARD_BLOCKED_CAPABILITIES
        assert is_unconditionally_hard_blocked("security.firewall.disable") is True
        assert is_unconditionally_hard_blocked("network.interfaces") is False

        # Metadata & Private network subnets
        subnets_str = [str(net) for net in HARD_BLOCKED_IP_NETWORKS]
        assert "169.254.0.0/16" in subnets_str
        assert "10.0.0.0/8" in subnets_str
        assert "172.16.0.0/12" in subnets_str
        assert "192.168.0.0/16" in subnets_str
        assert "127.0.0.0/8" in subnets_str
        assert "fe80::/10" in subnets_str
        assert "fc00::/7" in subnets_str
        assert "::1/128" in subnets_str

        # Developer domain allowlist
        assert "github.com" in DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST
        assert "*.pypi.org" in DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST
        assert "*.npmjs.org" in DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST
        assert "crates.io" in DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST


class TestNetworkPolicyEngine:
    """Validates SSRF prevention, DNS rebinding defenses, redirects, and domain allowlisting."""

    @pytest.fixture(autouse=True)
    def setup_policy_engine(self):
        NetworkPolicyEngine.reset_instance()
        self.engine = NetworkPolicyEngine.get_instance()

    def test_cloud_metadata_literal_ips_hard_blocked(self):
        # IPv4 Cloud IMDS & APIPA
        d1, r1, _ = self.engine.evaluate_destination("169.254.169.254")
        assert d1 == EgressDecision.HARD_BLOCKED
        assert "cloud metadata" in r1.lower() or "link-local" in r1.lower() or "hard-blocked" in r1.lower()

        d2, r2, _ = self.engine.evaluate_destination("http://169.254.1.1:8080/latest/meta-data")
        assert d2 == EgressDecision.HARD_BLOCKED

        # IPv6 Cloud IMDS
        d3, r3, _ = self.engine.evaluate_destination("http://[fd00:ec2::254]/latest/meta-data")
        assert d3 == EgressDecision.HARD_BLOCKED

        # IPv6 Link-Local and ULA Private
        d4, r4, _ = self.engine.evaluate_destination("http://[fe80::1]:80")
        assert d4 == EgressDecision.HARD_BLOCKED

        d5, r5, _ = self.engine.evaluate_destination("http://[fc00::1]:8080")
        assert d5 == EgressDecision.HARD_BLOCKED

    def test_metadata_hostnames_hard_blocked(self):
        d1, r1, _ = self.engine.evaluate_destination("http://metadata.google.internal/computeMetadata/v1")
        assert d1 == EgressDecision.HARD_BLOCKED
        assert "hard-blocked" in r1

        d2, r2, _ = self.engine.evaluate_destination("metadata.azure.com")
        assert d2 == EgressDecision.HARD_BLOCKED

        d3, r3, _ = self.engine.evaluate_destination("http://instance-data/latest/meta-data")
        assert d3 == EgressDecision.HARD_BLOCKED

    def test_private_rfc1918_ips_hard_blocked(self):
        d1, r1, _ = self.engine.evaluate_destination("http://10.0.0.5:8080")
        assert d1 == EgressDecision.HARD_BLOCKED
        assert "Private" in r1 or "10.0.0.0/8" in r1

        d2, r2, _ = self.engine.evaluate_destination("http://192.168.1.1")
        assert d2 == EgressDecision.HARD_BLOCKED

        d3, r3, _ = self.engine.evaluate_destination("http://172.20.0.1")
        assert d3 == EgressDecision.HARD_BLOCKED

        d4, r4, _ = self.engine.evaluate_destination("http://127.0.0.1:5000")
        assert d4 == EgressDecision.HARD_BLOCKED

    def test_dns_rebinding_adversarial_detection(self):
        """
        Adversarial Test: An attacker-controlled domain (or lookalike domain)
        that resolves to Cloud Metadata or private IP is hard-blocked.
        """
        with patch.object(self.engine, "resolve_destination", return_value=["169.254.169.254"]):
            decision, reason, meta = self.engine.evaluate_destination("http://rebound-metadata-exfil.com")
            assert decision == EgressDecision.HARD_BLOCKED
            assert "DNS Rebinding Protection" in reason
            assert meta["category"] == "dns_rebinding_ssrf_hard_block"
            assert meta["blocked_ip"] == "169.254.169.254"

        with patch.object(self.engine, "resolve_destination", return_value=["192.168.1.50"]):
            decision, reason, _ = self.engine.evaluate_destination("http://internal-lan-pivot.org")
            assert decision == EgressDecision.HARD_BLOCKED
            assert "DNS Rebinding Protection" in reason

    def test_redirect_validation_per_hop(self):
        # Redirect to safe external public domain
        with patch.object(self.engine, "resolve_destination", return_value=["93.184.216.34"]):
            valid, _ = self.engine.validate_redirect("https://github.com", "https://pypi.org")
            assert valid is True

        # Redirect to Cloud Metadata
        valid_bad, err = self.engine.validate_redirect("https://github.com", "http://169.254.169.254/latest/meta-data")
        assert valid_bad is False
        assert "rejected" in err

        # Redirect to LAN endpoint
        valid_lan, err_lan = self.engine.validate_redirect("https://github.com", "http://10.0.0.1:8080/admin")
        assert valid_lan is False
        assert "rejected" in err_lan

    def test_developer_domain_allowlist_matches(self):
        with patch.object(self.engine, "resolve_destination", return_value=["140.82.121.4"]):
            # GitHub
            d1, _, _ = self.engine.evaluate_destination("https://github.com/torvalds/linux.git")
            assert d1 == EgressDecision.ALLOW

            d2, _, _ = self.engine.evaluate_destination("git@github.com:user/repo.git")
            assert d2 == EgressDecision.ALLOW

            # PyPI
            d3, _, _ = self.engine.evaluate_destination("https://pypi.org/simple/requests/")
            assert d3 == EgressDecision.ALLOW

            d4, _, _ = self.engine.evaluate_destination("https://files.pythonhosted.org/packages/test.whl")
            assert d4 == EgressDecision.ALLOW

            # npm
            d5, _, _ = self.engine.evaluate_destination("https://registry.npmjs.org/express")
            assert d5 == EgressDecision.ALLOW

            # crates.io
            d6, _, _ = self.engine.evaluate_destination("https://crates.io/api/v1/crates/serde")
            assert d6 == EgressDecision.ALLOW

    def test_unlisted_external_domain_requires_confirmation(self):
        with patch.object(self.engine, "resolve_destination", return_value=["93.184.216.34"]):
            decision, reason, meta = self.engine.evaluate_destination("https://some-unlisted-web-api.com/data")
            assert decision == EgressDecision.CONFIRMATION_REQUIRED
            assert "requires cryptographic human approval" in reason
            assert meta["category"] == "unlisted_domain_egress"


class TestTerminalEgressInterception:
    """Validates TerminalManager command scanning and network policy enforcement."""

    @pytest.fixture(autouse=True)
    def setup_terminal(self):
        CryptographicApprovalAuthority.reset_instance()
        NetworkPolicyEngine.reset_instance()
        self.auth = CryptographicApprovalAuthority.get_instance()
        self.engine = NetworkPolicyEngine.get_instance()
        self.manager = TerminalManager(auth=self.auth, network_policy=self.engine)
        self.manager.initialize()

    def test_terminal_blocks_cloud_metadata_probe(self):
        tier, reason = self.manager.evaluate_command_risk("curl http://169.254.169.254/latest/meta-data")
        assert tier == CommandRiskTier.HARD_BLOCKED
        assert "Network Policy Violation" in reason

        tier2, reason2 = self.manager.evaluate_command_risk("Invoke-WebRequest -Uri http://metadata.google.internal")
        assert tier2 == CommandRiskTier.HARD_BLOCKED
        assert "Network Policy Violation" in reason2

    def test_terminal_allows_allowlisted_developer_egress(self):
        with patch.object(self.engine, "resolve_destination", return_value=["140.82.121.4"]):
            tier, _ = self.manager.evaluate_command_risk("git clone https://github.com/torvalds/linux.git")
            assert tier == CommandRiskTier.WORKSPACE_DEV

    def test_terminal_gates_unlisted_external_egress(self):
        with patch.object(self.engine, "resolve_destination", return_value=["93.184.216.34"]):
            tier, reason = self.manager.evaluate_command_risk("git clone https://unlisted-server.org/repo.git")
            assert tier == CommandRiskTier.CONFIRMATION_REQUIRED
            assert "unlisted network destination" in reason


class TestNetworkManagerHardening:
    """Validates NetworkManager HMAC gates on host-modifying control operations."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        CryptographicApprovalAuthority.reset_instance()
        self.auth = CryptographicApprovalAuthority.get_instance()
        self.manager = NetworkManager(auth=self.auth)
        self.manager.initialize()

    def test_read_only_interfaces_allowed_without_ticket(self):
        with patch.object(self.manager.adapter, "get_interfaces", return_value=[{"name": "Ethernet", "status": "Up"}]):
            res = self.manager.execute("network.interfaces")
            assert res.success is True
            assert "interfaces" in res.data

    def test_disable_adapter_without_ticket_fails_and_issues_ticket(self):
        res = self.manager.execute("network.disable_adapter", arguments={"adapter_name": "Ethernet"})
        assert res.success is False
        assert "requires cryptographic human approval" in res.error
        assert res.data["requires_confirmation"] is True
        assert res.data["approval_ticket_id"].startswith("tkt_")
        assert res.data["action_type"] == "network.disable_adapter"
        assert res.data["target"] == "Ethernet"

    def test_disable_adapter_with_forged_ticket_rejected(self):
        ticket_id = self.auth.create_ticket("network.disable_adapter", "Ethernet", {"capability": "network.disable_adapter", "target": "Ethernet"})
        res = self.manager.execute(
            "network.disable_adapter",
            arguments={
                "adapter_name": "Ethernet",
                "approval_ticket_id": ticket_id,
                "approval_signature": "forged_signature_0000" * 4,
            },
        )
        assert res.success is False
        assert "Human authorization failed" in res.error
        assert res.data.get("security_alert") == "unauthorized_or_forged_approval"

    def test_disable_adapter_with_valid_signed_ticket_executes(self):
        res_prompt = self.manager.execute("network.disable_adapter", arguments={"adapter_name": "Ethernet"})
        ticket_id = res_prompt.data["approval_ticket_id"]
        sig = self.auth.generate_human_signature(ticket_id)
        assert sig is not None

        with patch.object(self.manager.adapter, "disable_adapter", return_value=True):
            res_exec = self.manager.execute(
                "network.disable_adapter",
                arguments={
                    "adapter_name": "Ethernet",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            assert res_exec.success is True
            assert res_exec.data["adapter"] == "Ethernet"
            assert "network_adapter_disabled" in res_exec.events

    def test_adapter_substitution_adversarial_rejection(self):
        """
        Adversarial Test: Ticket signed for 'Ethernet' cannot be redeemed to disable 'Wi-Fi'.
        """
        res_prompt = self.manager.execute("network.disable_adapter", arguments={"adapter_name": "Ethernet"})
        ticket_id = res_prompt.data["approval_ticket_id"]
        sig = self.auth.generate_human_signature(ticket_id)
        assert sig is not None

        with patch.object(self.manager.adapter, "disable_adapter") as mock_disable:
            res_tampered = self.manager.execute(
                "network.disable_adapter",
                arguments={
                    "adapter_name": "Wi-Fi",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            assert res_tampered.success is False
            assert "Human authorization failed" in res_tampered.error
            mock_disable.assert_not_called()

    def test_flush_dns_and_wifi_disconnect_are_gated(self):
        res1 = self.manager.execute("network.flush_dns")
        assert res1.success is False
        assert res1.data["requires_confirmation"] is True

        res2 = self.manager.execute("network.disconnect_wifi")
        assert res2.success is False
        assert res2.data["requires_confirmation"] is True


from src.brain.page_reader import PageReader
from src.desktop.native.security.network_policy import SafeHTTPRedirectHandler, SafeSession
from src.research.content_fetcher import ContentFetcher


class TestProgrammaticHttpClientSecurity:
    """Validates real HTTP client enforcement (SafeSession & SafeHTTPRedirectHandler)."""

    def test_content_fetcher_direct_metadata_fetch_blocked(self):
        fetcher = ContentFetcher()
        # Direct fetch to metadata URL fails safely
        doc = fetcher.fetch("http://169.254.169.254/latest/meta-data")
        assert doc is None

    def test_safe_session_redirect_to_private_ip_blocked(self):
        session = SafeSession()
        # Mock initial request to safe domain and redirect response pointing to private LAN
        mock_initial_req = MagicMock()
        mock_initial_req.url = "https://safe-domain.org/redirect"

        mock_redirect_req = MagicMock()
        mock_redirect_req.url = "http://10.0.0.1:8080/admin/dump"

        with patch("requests.Session.resolve_redirects", return_value=[mock_redirect_req]):
            with pytest.raises(PermissionError) as exc_info:
                list(session.resolve_redirects(MagicMock(), mock_initial_req))
            assert "SSRF / Redirect Hard-Blocked" in str(exc_info.value)

    def test_page_reader_metadata_fetch_blocked_with_access_denied(self):
        reader = PageReader()
        content = reader.read_page("http://169.254.169.254/latest/meta-data")
        assert content.title == "Access Denied"
        assert "Security Error: Network policy hard-block" in content.main_text

    def test_safe_http_redirect_handler_blocks_metadata_redirect(self):
        import urllib.error
        handler = SafeHTTPRedirectHandler()
        mock_req = MagicMock()
        mock_req.full_url = "http://example.com/download"

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            handler.redirect_request(
                req=mock_req,
                fp=None,
                code=302,
                msg="Found",
                headers={},
                newurl="http://169.254.169.254/latest/meta-data",
            )
        assert "SSRF / Redirect Hard-Blocked" in str(exc_info.value)
