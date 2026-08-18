"""
Network Egress Policy & Domain Allowlisting Engine
Location: src/desktop/native/security/network_policy.py

Enforces multi-tier network egress control:
- Tier 0: Unconditional Hard-Block on Cloud Metadata (169.254.169.254, fd00:ec2::254),
  Link-Local (fe80::/10), Private LANs (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7),
  Loopback (127.0.0.0/8, ::1), and DNS rebinding attacks.
- Tier 1: Developer Domain Allowlist (PyPI, npm, GitHub, crates.io) for autonomous execution.
- Tier 2: Unlisted External Destinations require cryptographic human approval tickets.

Security Invariant:
All domain evaluations resolve DNS and validate every resolved IP against Tier-0 subnet blocks,
neutralizing DNS rebinding attacks where an attacker points an allowlisted name to private/metadata IPs.
"""

from __future__ import annotations

import fnmatch
import ipaddress
import logging
import re
import socket
import threading
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from .governance import (
    DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST,
    HARD_BLOCKED_HOSTNAMES,
    HARD_BLOCKED_IP_NETWORKS,
)

logger = logging.getLogger(__name__)


class EgressDecision(str, Enum):
    """Network egress evaluation outcome."""
    ALLOW = "allow"
    CONFIRMATION_REQUIRED = "confirmation_required"
    HARD_BLOCKED = "hard_blocked"


class NetworkPolicyEngine:
    """
    Centralized policy engine evaluating outbound network destinations.
    Enforces SSRF prevention, Cloud Metadata blocking, DNS rebinding validation,
    and developer domain allowlisting.
    """

    _instance: NetworkPolicyEngine | None = None
    _lock = threading.Lock()

    def __init__(
        self,
        domain_allowlist: set[str] | None = None,
        custom_blocked_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None,
    ):
        self._allowlist: set[str] = set(domain_allowlist or DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST)
        self._blocked_networks = list(HARD_BLOCKED_IP_NETWORKS) + (custom_blocked_networks or [])
        self._blocked_hostnames: set[str] = set(HARD_BLOCKED_HOSTNAMES)

    @classmethod
    def get_instance(cls) -> NetworkPolicyEngine:
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for isolated test fixtures."""
        with cls._lock:
            cls._instance = None

    @property
    def allowlist(self) -> set[str]:
        return self._allowlist

    def add_allowed_domain(self, domain: str) -> None:
        """Add a domain or wildcard pattern to the active allowlist."""
        clean = domain.lower().strip()
        if clean:
            self._allowlist.add(clean)

    def extract_host(self, target: str) -> str:
        """
        Extract canonical host string from raw URLs, hostnames, IP strings, or git endpoints.
        """
        raw = target.strip()
        if not raw:
            return ""

        # Handle git SSH syntax: git@github.com:org/repo.git
        if "@" in raw and ":" in raw and not raw.startswith(("http://", "https://", "ssh://")):
            parts = raw.split("@", 1)[-1].split(":", 1)
            return parts[0].lower().strip()

        # Add scheme prefix if missing for URL parser
        candidate = raw
        if "://" not in candidate:
            candidate = f"http://{candidate}"

        try:
            parsed = urlparse(candidate)
            hostname = parsed.hostname or ""
            if not hostname and parsed.netloc:
                hostname = parsed.netloc.split(":")[0]
            return hostname.lower().strip("[]").strip()
        except Exception:
            # Fallback regex extraction
            match = re.search(r"([a-zA-Z0-9.\-_]+)", raw)
            return match.group(1).lower().strip() if match else raw.lower().strip()

    def is_ip_hard_blocked(self, ip_str: str) -> tuple[bool, str]:
        """
        Check if an IP address falls within any hard-blocked network CIDR.
        """
        try:
            ip_obj = ipaddress.ip_address(ip_str.strip())
        except ValueError:
            return False, f"Invalid IP address format: {ip_str}"

        for net in self._blocked_networks:
            if ip_obj in net:
                desc = "Cloud Metadata / Link-Local / Private Network"
                if ip_obj.is_loopback:
                    desc = "Loopback (127.0.0.0/8 or ::1)"
                elif ip_obj.is_link_local:
                    desc = "Link-Local / APIPA / Cloud Metadata (169.254.0.0/16 or fe80::/10)"
                elif ip_obj.is_private:
                    desc = "RFC1918 / Private LAN (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)"
                return True, f"Destination IP '{ip_str}' is within hard-blocked network {net} ({desc})."

        return False, "IP is not in hard-blocked CIDR ranges."

    def matches_domain_allowlist(self, hostname: str) -> bool:
        """
        Check if hostname matches any pattern in the developer domain allowlist
        (supports exact match, wildcards, and subdomain matching).
        """
        host = hostname.lower().strip()
        if not host:
            return False

        for pattern in self._allowlist:
            p = pattern.lower().strip()
            # Exact match
            if host == p:
                return True
            # Wildcard fnmatch (e.g. *.github.com)
            if fnmatch.fnmatch(host, p):
                return True
            # Domain prefix wildcard matching
            if p.startswith("*."):
                root = p[2:]
                if host == root or host.endswith(f".{root}"):
                    return True

        return False

    def resolve_destination(self, hostname: str) -> list[str]:
        """
        Resolve a hostname to all associated IPv4 and IPv6 addresses.
        """
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            resolved_ips = list({info[4][0] for info in addr_info if info and info[4]})
            return resolved_ips
        except Exception as exc:
            logger.warning(f"DNS resolution failed for '{hostname}': {exc}")
            return []

    def evaluate_destination(
        self,
        target: str,
        resolve_dns: bool = True,
    ) -> tuple[EgressDecision, str, dict[str, Any]]:
        """
        Evaluate an outbound network target destination.

        Returns:
            (EgressDecision, reason_message, metadata)
        """
        host = self.extract_host(target)
        if not host:
            return (
                EgressDecision.HARD_BLOCKED,
                f"Invalid or empty network destination: '{target}'",
                {"target": target, "host": ""},
            )

        # 1. Check Hard-Blocked Hostnames (metadata.google.internal, 169.254.169.254, etc.)
        if host in self._blocked_hostnames:
            return (
                EgressDecision.HARD_BLOCKED,
                f"Destination '{host}' is an unconditionally hard-blocked cloud metadata / internal target.",
                {"target": target, "host": host, "category": "cloud_metadata_hard_block"},
            )

        # 2. Check if host is a literal IP address
        try:
            ip_obj = ipaddress.ip_address(host)
            is_blocked, block_msg = self.is_ip_hard_blocked(str(ip_obj))
            if is_blocked:
                return (
                    EgressDecision.HARD_BLOCKED,
                    f"Direct connection to blocked IP '{host}' rejected: {block_msg}",
                    {"target": target, "host": host, "resolved_ips": [host], "category": "ip_cidr_hard_block"},
                )
            # Literal public IP not in allowlist
            return (
                EgressDecision.CONFIRMATION_REQUIRED,
                f"Direct connection to public IP '{host}' requires cryptographic human approval.",
                {"target": target, "host": host, "resolved_ips": [host], "category": "unlisted_ip_egress"},
            )
        except ValueError:
            # Host is a domain name
            pass

        # 3. DNS Resolution & Rebinding Validation
        resolved_ips: list[str] = []
        if resolve_dns:
            resolved_ips = self.resolve_destination(host)
            for ip_str in resolved_ips:
                is_blocked, block_msg = self.is_ip_hard_blocked(ip_str)
                if is_blocked:
                    # DNS Rebinding or Private LAN Resolution Detected
                    return (
                        EgressDecision.HARD_BLOCKED,
                        f"SSRF / DNS Rebinding Protection: Host '{host}' resolves to hard-blocked IP '{ip_str}' ({block_msg}).",
                        {
                            "target": target,
                            "host": host,
                            "resolved_ips": resolved_ips,
                            "blocked_ip": ip_str,
                            "category": "dns_rebinding_ssrf_hard_block",
                        },
                    )

        # 4. Check Developer Domain Allowlist
        if self.matches_domain_allowlist(host):
            return (
                EgressDecision.ALLOW,
                f"Host '{host}' is on the verified developer domain allowlist.",
                {"target": target, "host": host, "resolved_ips": resolved_ips, "category": "developer_allowlist"},
            )

        # 5. Unlisted Public Domain -> Requires Confirmation
        return (
            EgressDecision.CONFIRMATION_REQUIRED,
            f"Outbound network connection to unlisted destination '{host}' requires cryptographic human approval.",
            {"target": target, "host": host, "resolved_ips": resolved_ips, "category": "unlisted_domain_egress"},
        )

    def validate_redirect(self, from_url: str, to_url: str) -> tuple[bool, str]:
        """
        Validate HTTP redirect target against Tier-0 hard blocks.
        """
        decision, reason, _ = self.evaluate_destination(to_url, resolve_dns=True)
        if decision == EgressDecision.HARD_BLOCKED:
            return False, f"Redirect from '{from_url}' to '{to_url}' rejected: {reason}"
        return True, "Redirect target validated successfully."


import urllib.error
import urllib.request


class SafeHTTPRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    urllib redirect handler enforcing NetworkPolicyEngine per-hop validation.
    Prevents HTTP redirects from pivoting into Cloud Metadata or private LANs.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        valid, reason = NetworkPolicyEngine.get_instance().validate_redirect(req.full_url, newurl)
        if not valid:
            raise urllib.error.HTTPError(newurl, code, f"SSRF / Redirect Hard-Blocked: {reason}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


try:
    import requests

    class SafeSession(requests.Session):
        """
        Requests Session subclass enforcing NetworkPolicyEngine validation
        on initial request and all redirect hops.
        """

        def send(self, request, **kwargs):
            decision, reason, _ = NetworkPolicyEngine.get_instance().evaluate_destination(request.url)
            if decision == EgressDecision.HARD_BLOCKED:
                raise PermissionError(f"Network Policy Hard-Block: {reason}")
            return super().send(request, **kwargs)

        def resolve_redirects(
            self,
            resp,
            req,
            stream=False,
            timeout=None,
            verify=True,
            cert=None,
            proxies=None,
            yield_requests=False,
            **adapter_kwargs,
        ):
            for redirect_req in super().resolve_redirects(
                resp,
                req,
                stream=stream,
                timeout=timeout,
                verify=verify,
                cert=cert,
                proxies=proxies,
                yield_requests=yield_requests,
                **adapter_kwargs,
            ):
                target_url = redirect_req.url if hasattr(redirect_req, "url") else str(redirect_req)
                valid, reason = NetworkPolicyEngine.get_instance().validate_redirect(req.url, target_url)
                if not valid:
                    raise PermissionError(f"SSRF / Redirect Hard-Blocked: {reason}")
                yield redirect_req

except ImportError:
    SafeSession = None  # type: ignore
