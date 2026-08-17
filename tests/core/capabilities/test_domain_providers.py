"""
Tests for Domain Capability Providers
=====================================
Location: tests/core/capabilities/test_domain_providers.py
"""

from core.capabilities.providers.browser_provider import BrowserCapabilityProvider
from core.capabilities.providers.coding_provider import CodingCapabilityProvider
from core.capabilities.providers.memory_provider import MemoryCapabilityProvider
from core.capabilities.providers.research_provider import ResearchCapabilityProvider


def test_coding_capability_provider():
    """Verify CodingCapabilityProvider distinguishes live vs scaffolded backends."""
    provider = CodingCapabilityProvider()
    assert provider.domain == "coding"

    # Live capabilities
    analyze = provider.get_capability("code.analyze")
    assert analyze is not None
    assert analyze.is_live is True
    assert analyze.availability == "online"

    edit = provider.get_capability("code.edit")
    assert edit is not None
    assert edit.is_live is True
    assert edit.supports_undo is True
    assert "workspace.walk" in edit.requires

    # Scaffolded capabilities
    test_cap = provider.get_capability("code.test")
    assert test_cap is not None
    assert test_cap.is_live is False
    assert test_cap.availability == "scaffolded"

    repair_cap = provider.get_capability("code.repair")
    assert repair_cap is not None
    assert repair_cap.is_live is False
    assert repair_cap.availability == "scaffolded"


def test_browser_capability_provider():
    """Verify BrowserCapabilityProvider defines typed contracts with live operational liveness."""
    provider = BrowserCapabilityProvider()
    assert provider.domain == "browser"

    caps = provider.list_capabilities()
    assert len(caps) >= 5

    for cap in caps:
        assert cap.domain == "browser"
        assert cap.is_live is True
        assert cap.availability == "available"

    nav = provider.get_capability("browser.navigate")
    assert nav is not None
    assert nav.requires == ["browser.open"]
    assert nav.verifies == ["browser.observe"]


def test_memory_capability_provider():
    """Verify MemoryCapabilityProvider defines live memory store and recall contracts."""
    provider = MemoryCapabilityProvider()
    assert provider.domain == "memory"

    store_cap = provider.get_capability("memory.store")
    assert store_cap is not None
    assert store_cap.is_live is True

    recall_cap = provider.get_capability("memory.recall")
    assert recall_cap is not None
    assert recall_cap.is_live is True


def test_research_capability_provider():
    """Verify ResearchCapabilityProvider registers search and synthesis."""
    provider = ResearchCapabilityProvider()
    assert provider.domain == "research"

    search_cap = provider.get_capability("research.search")
    assert search_cap is not None
    assert search_cap.is_live is True

    synth_cap = provider.get_capability("research.synthesize")
    assert synth_cap is not None
    assert synth_cap.is_live is True
    assert synth_cap.requires == ["research.search"]

    deep_cap = provider.get_capability("research.deep_query")
    assert deep_cap is not None
    assert deep_cap.is_live is True
    assert deep_cap.availability == "online"
