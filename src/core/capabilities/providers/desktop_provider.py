"""
Desktop Capability Provider
===========================
Location: src/core/capabilities/providers/desktop_provider.py

Projects the native Desktop Capability Registry into canonical universal Capabilities
with zero cache skew and zero disruption to the underlying desktop layer.
"""

from __future__ import annotations

import logging

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk
from desktop.native.capability_registry import (
    CapabilityDescriptor,
    CapabilityRegistry as NativeCapabilityRegistry,
    PermissionRequired,
    RiskLevel as NativeRiskLevel,
)
from desktop.native.managers.native_manager_registry import NativeManagerRegistry

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

        desc = self._native_registry.get(name)
        if desc is None:
            return None

        manager_reg = NativeManagerRegistry.get_instance()
        if manager_reg._managers and manager_reg.get(desc.manager) is None:
            return None

        return self._descriptor_to_capability(desc)
