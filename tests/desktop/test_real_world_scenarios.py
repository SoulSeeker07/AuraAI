"""
Phase 3.2 Real-World Desktop Scenario Integration Suite

25 Realistic Natural Language Goal Scenarios testing:
- Goal Parsing & Classification
- Capability Graph Resolution
- DesktopContext World Model Pre-Checks
- DesktopExecutionEngine Dispatch (Simulation Mode)
- Verification & Recovery
- Planner Trace Generation
"""

from typing import Any, Dict

import pytest

from src.desktop.native.capability_registry import CapabilityRegistry
from src.desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
    reset_desktop_execution_engine,
)
from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry
from src.desktop.planner import (
    DesktopPlanner,
    PlanState,
    StepStatus,
    StepType,
)


@pytest.fixture
def cap_registry():
    return CapabilityRegistry()


@pytest.fixture
def engine(cap_registry):
    reset_desktop_execution_engine()
    reg = NativeManagerRegistry.get_instance()
    reg.discover("src.desktop.native.managers")
    eng = DesktopExecutionEngine(
        manager_registry=reg,
        registry=cap_registry,
        config=ExecutionConfig(simulation_mode=True),
    )
    yield eng
    reset_desktop_execution_engine()


@pytest.fixture
def planner(engine, cap_registry):
    return DesktopPlanner(engine=engine, registry=cap_registry)


# 25 Realistic Scenarios Matrix
SCENARIOS = [
    # Audio Scenarios (1-5)
    ("lower volume", "set_volume", "audio"),
    ("increase volume to 80%", "set_volume", "audio"),
    ("mute system sound", "toggle_mute", "audio"),
    ("check if speakers are muted", "is_muted", "audio"),
    ("list connected microphones", "list_microphones", "audio"),
    # Window Scenarios (6-10)
    ("show all open windows", "list_windows", "window"),
    ("focus vscode window", "activate_window", "window"),
    ("minimize browser window", "minimize_window", "window"),
    ("maximize terminal window", "maximize_window", "window"),
    ("restore active window", "restore_window", "window"),
    # Clipboard Scenarios (11-15)
    ("read copied text from clipboard", "clipboard.read_text", "clipboard"),
    ("copy text to clipboard", "clipboard.write_text", "clipboard"),
    ("clear desktop clipboard", "clipboard.clear", "clipboard"),
    ("check clipboard formats", "clipboard.get_formats", "clipboard"),
    ("check if clipboard has text", "clipboard.has_text", "clipboard"),
    # Network Scenarios (16-20)
    ("check my internal ip address", "network.local_ip", "network"),
    ("get public ip address", "network.public_ip", "network"),
    ("check internet connectivity", "network.internet", "network"),
    ("enable wifi adapter", "network.enable_adapter", "network"),
    ("ping google.com", "network.ping", "network"),
    # Power & Display Scenarios (21-25)
    ("check battery level", "power.battery", "power"),
    ("check ac power status", "power.ac_status", "power"),
    ("list connected monitors", "list_displays", "display"),
    ("get main display info", "get_primary_display", "display"),
    ("flush dns cache", "network.flush_dns", "network"),
]


@pytest.mark.parametrize("goal_text,expected_cap,expected_category", SCENARIOS)
def test_real_world_scenario(planner, goal_text, expected_cap, expected_category):
    """Verify natural language scenario execution end-to-end."""
    plan = planner.plan_and_execute(goal_text)

    # 1. Verification of Goal Completion
    assert (
        plan.is_successful is True
    ), f"Scenario '{goal_text}' failed: {[s.error_message for s in plan.steps]}"
    assert plan.state == PlanState.COMPLETED
    assert (
        plan.goal.category == expected_category
        or expected_category in plan.goal.category
    )

    # 2. Verification of Target Capability Included
    action_caps = [s.capability for s in plan.steps]
    assert (
        expected_cap in action_caps
    ), f"Expected capability '{expected_cap}' not found in plan steps: {action_caps}"

    # 3. Verification of Planner Trace Generation
    assert planner.last_trace is not None
    assert planner.last_trace.goal == goal_text
    assert planner.last_trace.is_successful is True
    assert (
        len(planner.last_trace.nodes) >= 4
    )  # Parse, Classify, Resolve, Execute nodes present
