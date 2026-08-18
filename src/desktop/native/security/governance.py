"""
Security Governance & Capability Policy Registry
Location: src/desktop/native/security/governance.py

Centralized registry and policy definitions governing:
1. Host Context Mutation Exceptions (capabilities permitted to execute outside the sandbox post-approval).
2. Unconditional Hard-Blocked Capabilities (capabilities permanently rejected with zero bypass/ticket paths).
3. Network Egress Policy Constants:
   - Hard-blocked IP networks (Cloud IMDS, Link-Local, RFC1918, Loopback, IPv6 ULA).
   - Hard-blocked cloud metadata hostnames.
   - Developer Domain Allowlist (PyPI, npm, GitHub, crates.io, etc.).
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Final

logger = logging.getLogger(__name__)

# ============================================================================
# 1. Host Context Mutation Exceptions
# ============================================================================
# CRITICAL INVARIANT: The default for all mutating capabilities is DACL-sandboxed execution.
# This set contains the EXCLUSIVE, EXPLICIT exceptions permitted to run with host user privileges
# after cryptographic HMAC-SHA256 human approval has been verified and redeemed.
# Adding to this set is a Security Architecture Event.
HOST_CONTEXT_MUTATION_EXCEPTIONS: Final[frozenset[str]] = frozenset({
    "software.install",
    "software.uninstall",
    "software.update",
    "software.update_all",
    "pip.install",
    "npm.install",
    "npm.install_with_scripts",
})


# ============================================================================
# 2. Unconditional Hard-Blocked Capabilities
# ============================================================================
# CRITICAL INVARIANT: Capabilities in this set have NO human ticket bypass path.
# They are permanently and unconditionally rejected across all managers, routers, and dispatchers.
UNCONDITIONAL_HARD_BLOCKED_CAPABILITIES: Final[frozenset[str]] = frozenset({
    "security.firewall.disable",
    "security.antivirus.disable",
    "security.realtime_protection.disable",
    "security.tamper_protection.disable",
    "security.defender.disable",
    "file.delete_workspace_root",
})


# ============================================================================
# 3. Network Egress Governance: Hard-Blocked IP Networks & Metadata
# ============================================================================
# Blanket blocks on Cloud Metadata, Link-Local, Private Subnets, and Loopback
HARD_BLOCKED_IP_NETWORKS: Final[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]] = (
    # IPv4 Cloud Metadata & Link-Local (APIPA)
    ipaddress.ip_network("169.254.0.0/16"),
    # IPv4 RFC1918 Private Ranges (Blocked for autonomous external egress)
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # IPv4 Carrier-Grade NAT (CGNAT)
    ipaddress.ip_network("100.64.0.0/10"),
    # IPv4 Loopback
    ipaddress.ip_network("127.0.0.0/8"),
    # IPv4 Broadcast & Reserved
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("240.0.0.0/4"),

    # IPv6 Cloud Metadata (e.g. AWS IMDSv2 IPv6 /32 subnet or host)
    ipaddress.ip_network("fd00:ec2::254/128"),
    # IPv6 Link-Local Unicast (fe80::/10)
    ipaddress.ip_network("fe80::/10"),
    # IPv6 Unique Local Address (ULA - Private / fc00::/7)
    ipaddress.ip_network("fc00::/7"),
    # IPv6 Loopback (::1/128)
    ipaddress.ip_network("::1/128"),
    # IPv4-Mapped IPv6
    ipaddress.ip_network("::ffff:0:0/96"),
    # IPv6 Discard / Reserved
    ipaddress.ip_network("100::/64"),
)

HARD_BLOCKED_HOSTNAMES: Final[frozenset[str]] = frozenset({
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
    "metadata.azure.com",
    "169.254.169.254",
    "localhost",
})


# ============================================================================
# 4. Developer Domain Allowlist (Tier 1 Autonomous Access)
# ============================================================================
# Stated Invariant: Tier 1 allows developer tooling destinations. It defends
# against arbitrary external C2, but does not prevent application-level misuse
# of multi-tenant endpoints (e.g. public Gists/issues).
DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST: Final[frozenset[str]] = frozenset({
    # Python / PyPI
    "pypi.org",
    "*.pypi.org",
    "pythonhosted.org",
    "*.pythonhosted.org",
    # JavaScript / Node / npm / yarn
    "npmjs.org",
    "*.npmjs.org",
    "npmjs.com",
    "*.npmjs.com",
    "yarnpkg.com",
    "*.yarnpkg.com",
    # Rust / Cargo
    "crates.io",
    "*.crates.io",
    # Go / Golang
    "golang.org",
    "*.golang.org",
    "pkg.go.dev",
    "proxy.golang.org",
    # .NET / NuGet
    "nuget.org",
    "*.nuget.org",
    # Source Control & Git Repositories
    "github.com",
    "*.github.com",
    "githubusercontent.com",
    "*.githubusercontent.com",
    "gitlab.com",
    "*.gitlab.com",
    "bitbucket.org",
    "*.bitbucket.org",
    # AI / Model Hubs
    "huggingface.co",
    "*.huggingface.co",
})


def is_host_context_exception(capability: str) -> bool:
    """Check if capability is in the explicit host-context mutation exception list."""
    return capability.lower().strip() in HOST_CONTEXT_MUTATION_EXCEPTIONS


def is_unconditionally_hard_blocked(capability: str) -> bool:
    """Check if capability is unconditionally hard-blocked without any ticket path."""
    return capability.lower().strip() in UNCONDITIONAL_HARD_BLOCKED_CAPABILITIES
