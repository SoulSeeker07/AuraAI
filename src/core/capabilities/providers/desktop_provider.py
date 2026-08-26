"""
Desktop Capability Provider
===========================
Location: src/core/capabilities/providers/desktop_provider.py

Projects the native Desktop Capability Registry into canonical universal Capabilities
with zero cache skew and zero disruption to the underlying desktop layer.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_src_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk

try:
    from desktop.native.capability_registry import (
        CapabilityDescriptor,
        CapabilityRegistry as NativeCapabilityRegistry,
        PermissionRequired,
        RiskLevel as NativeRiskLevel,
    )
    from desktop.native.managers.native_manager_registry import NativeManagerRegistry
except (ImportError, ModuleNotFoundError):
    try:
        from src.desktop.native.capability_registry import (
            CapabilityDescriptor,
            CapabilityRegistry as NativeCapabilityRegistry,
            PermissionRequired,
            RiskLevel as NativeRiskLevel,
        )
        from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry
    except Exception:
        class CapabilityDescriptor:
            pass

        class NativeCapabilityRegistry:
            def list_capabilities(self):
                return []
            def get(self, name):
                return None

        PermissionRequired = None  # type: ignore
        NativeRiskLevel = None  # type: ignore

        class NativeManagerRegistry:
            def list_managers(self):
                return {}

logger = logging.getLogger(__name__)


def map_native_to_action_risk(
    native_risk: NativeRiskLevel,
    native_perm: PermissionRequired,
    is_destructive: bool = False,
    requires_confirmation: bool = False,
    requires_admin: bool = False,
) -> ActionRisk:
    """
    Deterministically map native desktop risk/permission levels to canonical ActionRisk.
    """
    base_map = {
        NativeRiskLevel.SAFE: ActionRisk.LOW,
        NativeRiskLevel.LOW: ActionRisk.LOW,
        NativeRiskLevel.MODERATE: ActionRisk.MEDIUM,
        NativeRiskLevel.HIGH: ActionRisk.HIGH,
        NativeRiskLevel.CRITICAL: ActionRisk.CRITICAL,
    }
    risk = base_map.get(native_risk, ActionRisk.MEDIUM)

    # Permission Elevation
    if native_perm == PermissionRequired.ADMIN or requires_admin:
        risk = ActionRisk.CRITICAL
    elif native_perm == PermissionRequired.WRITE and risk == ActionRisk.LOW:
        risk = ActionRisk.MEDIUM

    # Explicit Safety Overrides
    if is_destructive or requires_confirmation:
        if requires_admin or native_perm == PermissionRequired.ADMIN:
            risk = ActionRisk.CRITICAL
        elif risk in (ActionRisk.LOW, ActionRisk.MEDIUM):
            risk = ActionRisk.HIGH

    return risk


class DesktopCapabilityProvider(ICapabilityProvider):
    """
    Adapter provider projecting 100+ native desktop capabilities into the universal registry.
    """

    DOMAIN = "desktop"

    def __init__(self, native_registry: NativeCapabilityRegistry | None = None) -> None:
        self._native_registry = native_registry or NativeCapabilityRegistry()

    @property
    def domain(self) -> str:
        return self.DOMAIN

    def _descriptor_to_capability(self, desc: CapabilityDescriptor) -> Capability:
        """Convert native CapabilityDescriptor to canonical universal Capability."""
        action_risk = map_native_to_action_risk(
            native_risk=desc.risk_level,
            native_perm=desc.permission,
            is_destructive=desc.is_destructive,
            requires_confirmation=desc.requires_confirmation,
            requires_admin=desc.requires_admin,
        )

        perm_str = desc.permission.value if isinstance(desc.permission, PermissionRequired) else str(desc.permission)

        return Capability(
            name=desc.name,
            domain=self.DOMAIN,
            description=desc.description,
            category=desc.category,
            version="1.0",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
            risk_level=action_risk,
            permissions=[f"desktop:{perm_str}"] if perm_str != "none" else [],
            is_destructive=desc.is_destructive,
            requires_confirmation=desc.requires_confirmation,
            requires_admin=desc.requires_admin,
            execution_backend="desktop_native",
            timeout_seconds=desc.timeout_seconds,
            supports_undo=desc.supports_undo,
            rollback_description=desc.rollback_description,
            is_live=True,
            availability="online",
            requires=list(desc.requires),
            verifies=list(desc.verifies),
            rollback_capabilities=list(desc.rollback_capabilities),
            tags=list(desc.tags),
            metadata={
                "manager": desc.manager,
                "supports_visualization": desc.supports_visualization,
                "success_message_template": desc.success_message_template,
                "backend_required": desc.backend_required,
                "minimum_windows_version": desc.minimum_windows_version,
                "alternative_actions": desc.alternative_actions,
            },
        )

    def list_capabilities(self) -> list[Capability]:
        """
        Dynamically project all native descriptors.
        Filters out capabilities of managers excluded at runtime by NativeManagerRegistry.
        """
        manager_reg = NativeManagerRegistry.get_instance()
        available_caps: list[Capability] = []

        for desc in self._native_registry.list_all():
            # If native manager registry is active, verify the underlying manager is registered and healthy
            if manager_reg._managers:
                mgr = manager_reg.get(desc.manager)
                if mgr is None:
                    # Manager was excluded or not discovered
                    continue
            available_caps.append(self._descriptor_to_capability(desc))

        # Built-in system capabilities
        built_in_names = {c.name for c in available_caps}
        if "system_info" not in built_in_names:
            available_caps.append(
                Capability(
                    name="system_info",
                    domain=self.DOMAIN,
                    description="Query system information and hardware specs.",
                    category="query",
                    risk_level=ActionRisk.LOW,
                    execution_backend="desktop_native",
                    is_live=True,
                    availability="online",
                    tags=["desktop", "system", "info"],
                )
            )
        if "chat" not in built_in_names:
            available_caps.append(
                Capability(
                    name="chat",
                    domain=self.DOMAIN,
                    description="General conversational chat or knowledge answering.",
                    category="general",
                    risk_level=ActionRisk.LOW,
                    execution_backend="desktop_native",
                    is_live=True,
                    availability="online",
                    tags=["chat", "general"],
                )
            )

        # First-class network capabilities
        network_caps = [
            Capability(
                name="network.interface_list",
                domain=self.DOMAIN,
                description="List physical and virtual network adapters, IP assignments, and operational status.",
                category="network",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["network", "interfaces", "adapters"],
            ),
            Capability(
                name="network.ping",
                domain=self.DOMAIN,
                description="Probe target host/IP via ICMP echo to evaluate round-trip latency and packet loss.",
                category="network",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["network", "ping", "latency", "diagnostics"],
            ),
            Capability(
                name="network.dns_query",
                domain=self.DOMAIN,
                description="Query DNS name resolution records (A, AAAA, CNAME, MX) and resolver response times.",
                category="network",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["network", "dns", "lookup", "diagnostics"],
            ),
            Capability(
                name="network.route_inspect",
                domain=self.DOMAIN,
                description="Inspect local routing tables, default gateways, and network interface metric bindings.",
                category="network",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["network", "routing", "gateway"],
            ),
            Capability(
                name="network.traceroute",
                domain=self.DOMAIN,
                description="Perform hop-by-hop route tracing to identify latency bottlenecks and packet drop points.",
                category="network",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["network", "traceroute", "hops", "diagnostics"],
            ),
            Capability(
                name="network.socket_probe",
                domain=self.DOMAIN,
                description="Test TCP/UDP socket connectivity and handshake response on target host and port.",
                category="network",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["network", "socket", "tcp", "port", "diagnostics"],
            ),
            Capability(
                name="network.remediate",
                domain=self.DOMAIN,
                description="Execute authorized network remediation (e.g. flush DNS cache, renew DHCP, reset adapter).",
                category="network",
                risk_level=ActionRisk.HIGH,
                requires_confirmation=True,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["network", "remediation", "repair"],
            ),
        ]

        # First-class security audit capabilities
        security_caps = [
            Capability(
                name="security.credential_scan",
                domain=self.DOMAIN,
                description="Scan workspace files, configs, and memory for exposed API keys, tokens, and credentials.",
                category="security",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["security", "credentials", "secrets", "audit"],
            ),
            Capability(
                name="security.attack_surface_audit",
                domain=self.DOMAIN,
                description="Audit listening network ports, running elevated processes, and exposed services.",
                category="security",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["security", "ports", "services", "attack_surface"],
            ),
            Capability(
                name="security.cve_check",
                domain=self.DOMAIN,
                description="Correlate installed software, packages, and dependencies against known vulnerability patterns.",
                category="security",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["security", "cve", "vulnerabilities", "audit"],
            ),
            Capability(
                name="security.firewall_audit",
                domain=self.DOMAIN,
                description="Audit Windows Firewall profiles, inbound/outbound rules, and Windows Defender status.",
                category="security",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["security", "firewall", "defender", "compliance"],
            ),
            Capability(
                name="security.remediate",
                domain=self.DOMAIN,
                description="Execute authorized security remediation (e.g. revoke compromised token, adjust firewall rule).",
                category="security",
                risk_level=ActionRisk.HIGH,
                requires_confirmation=True,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["security", "remediation", "hardening"],
            ),
        ]

        # First-class financial analysis capabilities
        finance_caps = [
            Capability(
                name="finance.extract_tabular",
                domain=self.DOMAIN,
                description="Extract structured financial tabular figures, line items, and periods from sheets or reports.",
                category="finance",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["finance", "extract", "tabular", "balance_sheet", "pnl"],
            ),
            Capability(
                name="finance.compute_metrics",
                domain=self.DOMAIN,
                description="Compute financial statement metrics (Gross Margin, EBITDA, Operating Margin, Debt/Equity, YoY Growth).",
                category="finance",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["finance", "metrics", "ratios", "ebitda", "margin"],
            ),
            Capability(
                name="finance.variance_analysis",
                domain=self.DOMAIN,
                description="Perform budget vs actual, period-over-period, and variance percentage calculations.",
                category="finance",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["finance", "variance", "budget", "forecast"],
            ),
            Capability(
                name="finance.forecast_model",
                domain=self.DOMAIN,
                description="Build financial forecast models with declared growth assumptions and sensitivity scenarios.",
                category="finance",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["finance", "forecast", "model", "cagr", "sensitivity"],
            ),
            Capability(
                name="finance.generate_report",
                domain=self.DOMAIN,
                description="Generate structured financial summary reports with full provenance citations and formula tables.",
                category="finance",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["finance", "report", "synthesis", "provenance"],
            ),
        ]

        # First-class keyboard and input capabilities
        input_caps = [
            Capability(
                name="keyboard.type",
                domain=self.DOMAIN,
                description="Type text string into active or targeted desktop window.",
                category="input",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["desktop", "keyboard", "type", "input"],
            ),
            Capability(
                name="keyboard.press",
                domain=self.DOMAIN,
                description="Press a keyboard key or hotkey combination (e.g. enter, tab, ctrl+s).",
                category="input",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["desktop", "keyboard", "press", "hotkey"],
            ),
            Capability(
                name="keyboard.hotkey",
                domain=self.DOMAIN,
                description="Trigger keyboard hotkey combination.",
                category="input",
                risk_level=ActionRisk.LOW,
                availability="online",
                tags=["desktop", "keyboard", "hotkey"],
            ),
        ]

        # Document generation and notification capabilities
        document_and_notif_caps = [
            Capability(
                name="document.generate",
                domain=self.DOMAIN,
                description="Transform research and telemetry artifacts into a formatted markdown document.",
                category="generation",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["desktop", "document", "generate", "markdown"],
            ),
            Capability(
                name="notification.send",
                domain=self.DOMAIN,
                description="Send an interactive or toast desktop notification to the user.",
                category="notification",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["desktop", "notification", "toast", "alert"],
            ),
            Capability(
                name="notification.show",
                domain=self.DOMAIN,
                description="Show a desktop notification banner.",
                category="notification",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["desktop", "notification", "banner"],
            ),
        ]

        for ncap in network_caps + security_caps + finance_caps + input_caps + document_and_notif_caps:
            if ncap.name not in built_in_names:
                available_caps.append(ncap)

        return available_caps

    def get_capability(self, name: str) -> Capability | None:
        """Get a projected capability by name."""
        if name == "system_info":
            return Capability(
                name="system_info",
                domain=self.DOMAIN,
                description="Query system information and hardware specs.",
                category="query",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["desktop", "system", "info"],
            )
        if name == "chat":
            return Capability(
                name="chat",
                domain=self.DOMAIN,
                description="General conversational chat or knowledge answering.",
                category="general",
                risk_level=ActionRisk.LOW,
                execution_backend="desktop_native",
                is_live=True,
                availability="online",
                tags=["chat", "general"],
            )

        # Check network capabilities
        for c in self.list_capabilities():
            if c.name == name:
                return c

        desc = self._native_registry.get(name)
        if desc is None and name.startswith("filesystem."):
            alias_name = name.replace("filesystem.", "file.", 1)
            desc = self._native_registry.get(alias_name)

        if desc is None:
            return None

        # Always return the capability even when the underlying native manager
        # is not currently registered in NativeManagerRegistry.  The capability
        # still exists in the native descriptor registry; the manager may simply
        # have been excluded during auto-discovery on this boot.  We let the
        # execution backend surface the error at runtime instead of silently
        # hiding the capability from plan validation.
        return self._descriptor_to_capability(desc)

