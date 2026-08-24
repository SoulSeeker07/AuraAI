"""
Tests for Universal Capability Registry
=======================================
Location: tests/core/capabilities/test_universal_capability_registry.py
"""

import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import Capability, PlanGraphError
from core.orchestration.autonomy_mode import ActionRisk


@pytest.fixture(autouse=True)
def clean_registry():
    CapabilityRegistry.reset_instance()
    yield
    CapabilityRegistry.reset_instance()


def test_registry_singleton_and_defaults():
    """Verify CapabilityRegistry initializes default providers and maintains singleton state."""
    reg1 = CapabilityRegistry.get_instance()
    reg2 = CapabilityRegistry.get_instance()
    assert reg1 is reg2

    caps = reg1.list()
    assert len(caps) > 100

    # Domains present
    domains = {cap.domain for cap in caps}
    assert "desktop" in domains
    assert "coding" in domains
    assert "browser" in domains
    assert "memory" in domains
    assert "research" in domains


def test_registry_canonical_and_alias_lookup():
    """Verify direct canonical name and domain-prefixed alias lookups."""
    reg = CapabilityRegistry.get_instance()

    # Canonical lookups
    battery = reg.get("power.battery")
    assert battery is not None
    assert battery.domain == "desktop"

    code_edit = reg.get("code.edit")
    assert code_edit is not None
    assert code_edit.domain == "coding"

    # Alias lookups
    alias_battery = reg.get("desktop:power.battery")
    assert alias_battery is not None
    assert alias_battery.name == "power.battery"

    alias_code = reg.get("coding:code.edit")
    assert alias_code is not None
    assert alias_code.name == "code.edit"

    # Non-matching alias returns None
    assert reg.get("browser:power.battery") is None
    assert reg.get("non_existent_cap") is None


def test_registry_domain_resolution():
    """Verify resolve_domain maps capability names to owning domain engines."""
    reg = CapabilityRegistry.get_instance()

    assert reg.resolve_domain("power.battery") == "desktop"
    assert reg.resolve_domain("window.activate") == "desktop"
    assert reg.resolve_domain("code.analyze") == "coding"
    assert reg.resolve_domain("browser.navigate") == "browser"
    assert reg.resolve_domain("memory.store") == "memory"
    assert reg.resolve_domain("research.search") == "research"
    assert reg.resolve_domain("unknown.capability") is None


def test_validate_plan_graph_trivial_empty_requires():
    """Verify capabilities with empty requires list pass validation trivially with zero overhead."""
    reg = CapabilityRegistry.get_instance()

    # Single-subtask independent action
    res = reg.validate_plan_graph(["power.battery"], require_live=True)
    assert res.valid is True
    assert len(res.errors) == 0
    assert len(res.missing_prerequisites) == 0

    # Multi-step independent actions
    res2 = reg.validate_plan_graph(["power.battery", "code.analyze"], require_live=True)
    assert res2.valid is True
    assert len(res2.errors) == 0


def test_validate_plan_graph_liveness_gating():
    """Verify plan validation fails closed when a primary capability or prerequisite is scaffolded."""
    reg = CapabilityRegistry.get_instance()

    # Scaffolded primary capability (e.g. code.repair)
    res = reg.validate_plan_graph(["code.repair"], require_live=True)
    assert res.valid is False
    assert any("scaffolded (is_live=False)" in err for err in res.errors)
    assert "code.repair" in res.unwired_capabilities

    # When require_live=False, scaffolded capabilities pass liveness check
    res_sim = reg.validate_plan_graph(["code.repair"], require_live=False)
    assert res_sim.valid is True


def test_validate_plan_graph_cycle_detection():
    """Verify cycle detection in task graphs fails closed with PlanGraphError."""
    reg = CapabilityRegistry.get_instance()

    # Register cyclic dummy capabilities
    cap_a = Capability(name="plan.step_a", domain="coding", description="Step A", requires=["plan.step_b"])
    cap_b = Capability(name="plan.step_b", domain="coding", description="Step B", requires=["plan.step_a"])

    reg.register(cap_a)
    reg.register(cap_b)

    # Validation should detect cycle and report error
    res = reg.validate_plan_graph(["plan.step_a", "plan.step_b"], require_live=False)
    assert res.valid is False
    assert any("Cyclic capability dependency detected" in err for err in res.errors)

    # In strict mode, raises PlanGraphError directly
    with pytest.raises(PlanGraphError) as exc_info:
        reg.validate_plan_graph(["plan.step_a", "plan.step_b"], require_live=False, strict_fail_closed=True)
    assert "Cyclic capability dependency detected" in str(exc_info.value)
