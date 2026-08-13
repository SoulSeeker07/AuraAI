"""
Test Milestone 22: General Browser Adaptability & Cross-Site Reasoning (M22.1)
=============================================================================

Verifies:
  1. Dynamic form inspection & field filling without site-specific hardcoded selectors
  2. Dynamic tabular structure extraction & row selection
  3. Dynamic pagination control detection & transition
  4. Multi-tab tracking & active tab focus switching
"""

import pytest
from brain.aca.engine_interface import EngineRegistry
from brain.execution_coordinator import ExecutionCoordinator
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend


@pytest.fixture
def clean_registry():
    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")
    return registry, desktop, browser


@pytest.mark.asyncio
async def test_01_dynamic_form_inspection_and_filling(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Inspect live form and fill form fields dynamically",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<input name='username'><input name='search'>"}},
            {"engine": "browser", "action": "browser.inspect_form", "parameters": {}},
            {"engine": "browser", "action": "browser.fill_form_field", "parameters": {"field": "username", "value": "aura_agent"}},
            {"engine": "browser", "action": "browser.fill_form_field", "parameters": {"field": "search", "value": "Python tutorials"}},
        ],
    }

    result = await coordinator.coordinate(exec_map)

    assert result.success is True
    assert len(result.step_results) == 4
    assert result.step_results[1].action == "browser.inspect_form"
    assert result.step_results[2].action == "browser.fill_form_field"
    assert result.step_results[3].action == "browser.fill_form_field"


@pytest.mark.asyncio
async def test_02_dynamic_table_extraction_and_row_selection(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Extract table headers and select matching row dynamically",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<table class='grid-table'><thead><tr><th>Subscriber</th><th>Status</th></tr></thead><tbody><tr><td>Acme</td><td>Active</td></tr></tbody></table>"}},
            {"engine": "browser", "action": "browser.extract_table", "parameters": {}},
            {"engine": "browser", "action": "browser.select_table_row", "parameters": {"query": "Active"}},
        ],
    }

    result = await coordinator.coordinate(exec_map)

    assert result.success is True
    assert len(result.step_results) == 3
    assert result.step_results[1].action == "browser.extract_table"
    assert result.step_results[2].action == "browser.select_table_row"


@pytest.mark.asyncio
async def test_03_multi_tab_coordination_and_pagination(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "List active browser tabs and transition page via dynamic pagination",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<a href='%23page2' aria-label='Next-page'>Next</a>"}},
            {"engine": "browser", "action": "browser.list_tabs", "parameters": {}},
            {"engine": "browser", "action": "browser.switch_tab", "parameters": {"tab_index": 0}},
            {"engine": "browser", "action": "browser.next_page", "parameters": {}},
        ],
    }

    result = await coordinator.coordinate(exec_map)

    assert result.success is True
    assert len(result.step_results) == 4
    assert result.step_results[1].action == "browser.list_tabs"
    assert result.step_results[2].action == "browser.switch_tab"
    assert result.step_results[3].action == "browser.next_page"


@pytest.mark.asyncio
async def test_04_failure_injection_adaptive_selector_recovery(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Search query with invalid primary selector and verify adaptive recovery",
        "steps": [
            {
                "engine": "browser",
                "action": "browser.search",
                "parameters": {
                    "query": "Apex Global",
                    "primary_selector": "input#nonexistent_search_input.invalid",
                    "alternative_selector": "input[name='query']",
                },
            },
        ],
    }

    result = await coordinator.coordinate(exec_map)

    assert result.success is True
    assert len(result.step_results) == 1
    assert result.step_results[0].action == "browser.search"
    assert result.step_results[0].data.get("recovered_selector") == "input[name='query']"
    assert result.step_results[0].data.get("recovery_trace", {}).get("recovery_status") == "RECOVERED_SUCCESS"


@pytest.mark.asyncio
async def test_05_browser_context_isolation_no_os_launcher_leakage(clean_registry, monkeypatch):
    from unittest.mock import MagicMock
    import webbrowser
    import subprocess
    import os

    mock_webbrowser_open = MagicMock()
    mock_popen = MagicMock()
    mock_startfile = MagicMock()

    monkeypatch.setattr(webbrowser, "open", mock_webbrowser_open)
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", mock_startfile)

    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    test_urls = [
        "https://example.com",
        "data:text/html,<h1>Test%20Isolation%201</h1>",
        "data:text/html,<h1>Test%20Isolation%202</h1>",
    ]

    for url in test_urls:
        exec_map = {
            "goal": f"Navigate to {url} and verify zero OS shell leakage",
            "steps": [
                {"engine": "browser", "action": "browser.navigate", "parameters": {"url": url}},
                {"engine": "browser", "action": "browser.list_tabs", "parameters": {}},
            ],
        }

        result = await coordinator.coordinate(exec_map)
        assert result.success is True

    # Regression Assertions: OS shell launchers MUST NEVER be invoked by browser operations
    mock_webbrowser_open.assert_not_called()
    mock_popen.assert_not_called()
    if hasattr(os, "startfile"):
        mock_startfile.assert_not_called()


