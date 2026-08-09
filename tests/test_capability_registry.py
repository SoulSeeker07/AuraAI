"""
Tests for M19.6 Capability Registry
Location: tests/test_capability_registry.py
"""

import pytest
from src.core.capabilities.capability_registry import (
    CapabilityRegistry,
    CapabilityDefinition,
)
from src.core.orchestration.autonomy_mode import ActionRisk


def test_capability_registry_defaults_and_custom():
    registry = CapabilityRegistry.get_instance()
    discovered = registry.discover()
    assert len(discovered) >= 5

    # Fetch default capability
    read_cap = registry.get("filesystem.read")
    assert read_cap is not None
    assert read_cap.risk_level == ActionRisk.LOW

    # Register custom capability
    custom_cap = CapabilityDefinition(
        name="terminal.execute",
        description="Execute a shell command",
        risk_level=ActionRisk.HIGH,
        permissions=["terminal"],
    )
    registry.register(custom_cap)

    fetched = registry.get("terminal.execute")
    assert fetched is not None
    assert fetched.risk_level == ActionRisk.HIGH
