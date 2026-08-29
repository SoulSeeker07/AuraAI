"""
Tests for Desktop Capability Provider
=====================================
Location: tests/core/capabilities/test_desktop_capability_provider.py
"""

from core.capabilities.providers.desktop_provider import (
    DesktopCapabilityProvider,
    map_native_to_action_risk,
)
from core.orchestration.autonomy_mode import ActionRisk
from desktop.native.capability_registry import (
    CapabilityDescriptor,
    PermissionRequired,
    RiskLevel as NativeRiskLevel,
)
from desktop.native.managers.native_manager_registry import NativeManagerRegistry


def test_map_native_to_action_risk_table():
    """Verify exact 5-tier risk mapping table and override rules."""
    # 1. Base mappings (no flags)
    assert map_native_to_action_risk(NativeRiskLevel.SAFE, PermissionRequired.NONE) == ActionRisk.LOW
    assert map_native_to_action_risk(NativeRiskLevel.LOW, PermissionRequired.READ) == ActionRisk.LOW
    assert map_native_to_action_risk(NativeRiskLevel.MODERATE, PermissionRequired.CONTROL) == ActionRisk.MEDIUM
    assert map_native_to_action_risk(NativeRiskLevel.HIGH, PermissionRequired.WRITE) == ActionRisk.HIGH
    assert map_native_to_action_risk(NativeRiskLevel.CRITICAL, PermissionRequired.CONTROL) == ActionRisk.CRITICAL

    # 2. Permission elevations
    assert map_native_to_action_risk(NativeRiskLevel.SAFE, PermissionRequired.WRITE) == ActionRisk.MEDIUM
    assert map_native_to_action_risk(NativeRiskLevel.LOW, PermissionRequired.ADMIN) == ActionRisk.CRITICAL
    assert map_native_to_action_risk(NativeRiskLevel.SAFE, PermissionRequired.NONE, requires_admin=True) == ActionRisk.CRITICAL

    # 3. Destructive and confirmation overrides
    assert map_native_to_action_risk(NativeRiskLevel.LOW, PermissionRequired.READ, is_destructive=True) == ActionRisk.HIGH
    assert map_native_to_action_risk(NativeRiskLevel.SAFE, PermissionRequired.READ, requires_confirmation=True) == ActionRisk.HIGH
    assert map_native_to_action_risk(NativeRiskLevel.LOW, PermissionRequired.READ, is_destructive=True, requires_admin=True) == ActionRisk.CRITICAL


def test_desktop_provider_projection_and_graph_preservation():
    """Verify live projection of desktop native descriptors into universal capabilities."""
    provider = DesktopCapabilityProvider()
    caps = provider.list_capabilities()

    assert len(caps) >= 100, f"Expected 100+ native capabilities, found {len(caps)}"

    # Check key capabilities
    battery_cap = provider.get_capability("power.battery")
    assert battery_cap is not None
    assert battery_cap.name == "power.battery"
    assert battery_cap.domain == "desktop"
    assert battery_cap.risk_level == ActionRisk.LOW
    assert battery_cap.is_live is True
    assert battery_cap.availability == "online"

    # Check app_open capability
    app_open = provider.get_capability("app_open")
    assert app_open is not None
    assert app_open.name == "app_open"
    assert app_open.domain == "desktop"
    assert app_open.risk_level == ActionRisk.LOW
    assert isinstance(app_open.requires, list)
    assert isinstance(app_open.verifies, list)
    assert isinstance(app_open.rollback_capabilities, list)


def test_desktop_provider_respects_runtime_manager_exclusion(monkeypatch):
    """Verify that if a native manager is excluded at runtime, its capabilities are omitted from universal projection."""
    NativeManagerRegistry.reset_instance()
    reg = NativeManagerRegistry.get_instance()

    try:
        # Discover real managers
        reg.discover("desktop.native.managers")
        provider = DesktopCapabilityProvider()

        initial_count = len(provider.list_capabilities())
        assert provider.get_capability("power.battery") is not None

        # Simulate excluding power manager
        if "power" in reg._managers:
            del reg._managers["power"]

        # Projection should immediately reflect exclusion with zero cache skew
        updated_caps = provider.list_capabilities()
        assert len(updated_caps) < initial_count
        assert provider.get_capability("power.battery") is None

    finally:
        NativeManagerRegistry.reset_instance()
        NativeManagerRegistry.get_instance().discover("desktop.native.managers")
