"""
Browser Capabilities & Guardrails Unit Test Suite
Location: tests/browser/test_browser_capabilities.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.capabilities.providers.browser_provider import BrowserCapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk
from browser.engine import BrowserEngine, validate_url_security
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.backend_registry import BackendRegistry


def test_browser_capability_descriptors():
    """Verify all browser capabilities have live operational descriptors and security tags."""
    provider = BrowserCapabilityProvider()
    caps = provider.list_capabilities()
    cap_names = {c.name for c in caps}

    expected_caps = {
        "browser.open",
        "browser.navigate",
        "browser.find_element",
        "browser.click",
        "browser.type",
        "browser.submit",
        "browser.extract",
        "browser.observe",
        "browser.close",
    }
    assert expected_caps.issubset(cap_names)

    for cap in caps:
        assert cap.is_live is True, f"Capability {cap.name} must be live"
        assert cap.availability == "available"
        assert cap.domain == "browser"
        assert cap.execution_backend == "browser"


def test_browser_mutation_confirmation_gates():
    """Verify mutating browser actions require explicit user confirmation and have HIGH risk."""
    provider = BrowserCapabilityProvider()

    mutating_ops = ["browser.click", "browser.type", "browser.submit"]
    for op_name in mutating_ops:
        cap = provider.get_capability(op_name)
        assert cap is not None, f"Capability {op_name} must exist"
        assert cap.risk_level == ActionRisk.HIGH, f"{op_name} must be ActionRisk.HIGH"
        assert cap.requires_confirmation is True, f"{op_name} must require confirmation"
        assert cap.is_destructive is True, f"{op_name} must be destructive"

    # Read-only ops should be LOW risk without confirmation
    read_ops = ["browser.navigate", "browser.find_element", "browser.extract", "browser.observe", "browser.open"]
    for op_name in read_ops:
        cap = provider.get_capability(op_name)
        assert cap is not None
        assert cap.risk_level == ActionRisk.LOW
        assert cap.requires_confirmation is False


def test_url_security_allowlist_and_ssrf_prevention():
    """Verify URL policy allow-lists http/https and strictly rejects prohibited schemes and private/metadata IPs."""
    # Allowed
    valid_urls = [
        "https://example.com",
        "http://example.com/test?q=1",
        "https://en.wikipedia.org/wiki/Python",
        "https://news.ycombinator.com",
        "google.com",  # will auto-prefix https://
    ]
    for url in valid_urls:
        valid, out = validate_url_security(url)
        assert valid is True, f"Expected '{url}' to be valid, got error: {out}"
        assert out.startswith("http://") or out.startswith("https://")

    # Prohibited schemes
    prohibited_schemes = [
        "file:///etc/passwd",
        "file://C:/Windows/System32/cmd.exe",
        "data:text/html,<h1>Exploit</h1>",
        "javascript:alert(document.cookie)",
        "about:blank",
    ]
    for url in prohibited_schemes:
        valid, out = validate_url_security(url)
        assert valid is False, f"Expected '{url}' to be rejected"
        assert "prohibited" in out.lower() or "blocked" in out.lower()

    # SSRF & Private / Loopback IPs
    prohibited_hosts = [
        "http://localhost:8080",
        "https://localhost",
        "http://127.0.0.1",
        "http://127.0.0.1:8000/admin",
        "http://0.0.0.0:3000",
        "http://10.0.0.1/sensitive",
        "http://192.168.1.1/router",
        "http://172.16.0.1",
        "http://169.254.169.254/latest/meta-data/",  # Cloud metadata SSRF
    ]
    for url in prohibited_hosts:
        valid, out = validate_url_security(url)
        assert valid is False, f"Expected SSRF target '{url}' to be blocked"
        assert "blocked" in out.lower() or "prohibited" in out.lower()


@pytest.mark.asyncio
async def test_find_element_fail_closed_on_ambiguity():
    """Verify find_element fails closed on 0 matches and >1 ambiguous matches with actionable guidance."""
    engine = BrowserEngine(headless=True)
    engine.is_active = True
    mock_page = MagicMock()
    engine._page = mock_page

    # Case 1: Zero matches
    mock_locator_zero = MagicMock()
    mock_locator_zero.count = AsyncMock(return_value=0)
    mock_locator_zero.first = MagicMock()
    mock_locator_zero.first.wait_for = AsyncMock()

    mock_text_locator_zero = MagicMock()
    mock_text_locator_zero.count = AsyncMock(return_value=0)

    mock_page.locator = MagicMock(return_value=mock_locator_zero)
    mock_page.get_by_text = MagicMock(return_value=mock_text_locator_zero)

    res_zero = await engine.find_element("#nonexistent-btn")
    assert res_zero["success"] is False
    assert res_zero["count"] == 0
    assert "Zero DOM elements found" in res_zero["error"]
    assert "Refine CSS selector" in res_zero["error"]

    # Case 2: Ambiguous matches (>1)
    mock_locator_multi = MagicMock()
    mock_locator_multi.count = AsyncMock(return_value=4)
    mock_locator_multi.first = MagicMock()
    mock_locator_multi.first.wait_for = AsyncMock()

    mock_page.locator = MagicMock(return_value=mock_locator_multi)

    res_multi = await engine.find_element("button")
    assert res_multi["success"] is False
    assert res_multi["count"] == 4
    assert "Ambiguous DOM target: found 4 matching elements" in res_multi["error"]
    assert "Refine selector with CSS tag, ID (#id), data-testid, aria-label" in res_multi["error"]

    # Case 3: Exactly 1 match (Success)
    mock_elem = MagicMock()
    mock_locator_one = MagicMock()
    mock_locator_one.count = AsyncMock(return_value=1)
    mock_locator_one.first = mock_elem
    mock_locator_one.first.wait_for = AsyncMock()

    mock_page.locator = MagicMock(return_value=mock_locator_one)

    res_one = await engine.find_element("#unique-checkout-btn")
    assert res_one["success"] is True
    assert res_one["count"] == 1
    assert res_one["element"] == mock_elem


def test_backend_registry_browser_resolution():
    """Verify BackendRegistry registers and resolves 'browser' adapter cleanly."""
    registry = BackendRegistry()
    adapter = registry.get_backend("browser")
    assert adapter is not None
    assert isinstance(adapter, PlaywrightBrowserAdapter)
    assert "browser.navigate" in adapter.capabilities
    assert "browser.click" in adapter.capabilities
    assert "browser.extract" in adapter.capabilities
