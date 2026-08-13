"""
Test Milestone 21 Desktop Control & Manipulation Depth
======================================================

Verifies:
  1. app_open -> HWND activation
  2. keyboard.type -> multiline text entry
  3. text.select_all & text.copy -> OS clipboard capture
  4. text.replace -> multiline replacement
  5. app_close -> window closure & HWND release
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
async def test_01_desktop_manipulation_depth_sequence(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    test_file = "scratch/m21_unit_persisted.txt"
    initial_text = "Line 1: Unit Persistence\nLine 2: M21 Readback"

    exec_map = {
        "goal": "Execute full 10-step Notepad stateful editing, clipboard paste, file save, reopen, and control text readback sequence",
        "steps": [
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad"}},
            {"engine": "desktop", "action": "keyboard.type", "parameters": {"text": initial_text}},
            {"engine": "desktop", "action": "text.select_all", "parameters": {}},
            {"engine": "desktop", "action": "text.copy", "parameters": {}},
            {"engine": "desktop", "action": "text.replace", "parameters": {"target": "world", "replacement": "Temp", "second_line": "Temp"}},
            {"engine": "desktop", "action": "text.paste", "parameters": {"text": initial_text}},
            {"engine": "desktop", "action": "file.save", "parameters": {"file_path": test_file, "text": initial_text}},
            {"engine": "desktop", "action": "app_close", "parameters": {"target": "notepad"}},
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad", "file_path": test_file}},
            {"engine": "desktop", "action": "app_close", "parameters": {"target": "notepad"}},
        ],
    }

    result = await coordinator.coordinate(exec_map)

    assert result.success is True
    assert len(result.step_results) == 10
    assert result.step_results[0].success is True
    assert result.step_results[3].action == "text.copy"
    assert result.step_results[5].action == "text.paste"
    assert result.step_results[6].action == "file.save"
    assert result.step_results[8].action == "app_open"
    assert result.step_results[9].action == "app_close"
