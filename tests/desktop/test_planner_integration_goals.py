"""
Phase 3.1 Goal-Based Integration Test Suite

Verifies real-world natural language goal execution from intent to verified outcome:
1. Volume control & audio diagnostics.
2. Network adapter & IP diagnostics in simulation mode.
3. Window management & listing.
4. Power & battery status diagnostics.
5. Event stream publishing & PlanState transition auditing.
"""

from typing import List

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
    PlannerEvent,
    PlannerEventBus,
    PlanState,
    StepStatus,
    StepType,
)


@pytest.fixture
def cap_registry():
    return CapabilityRegistry()


@pytest.fixture
def event_bus():
    return PlannerEventBus()


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
def planner(engine, cap_registry, event_bus):
    return DesktopPlanner(engine=engine, registry=cap_registry, event_bus=event_bus)


def test_integration_volume_goal(planner, event_bus):
    received_events: list[str] = []
    event_bus.subscribe("*", lambda e: received_events.append(e.event_type))

    plan = planner.plan_and_execute(goal_text="get master volume")

    assert plan.is_successful is True
    assert plan.state == PlanState.COMPLETED
    assert "PlanCreated" in received_events
    assert "PlanStarted" in received_events
    assert "PlanCompleted" in received_events
    assert any(s.capability == "get_volume" for s in plan.steps)


def test_integration_network_enable_goal(planner, event_bus):
    received_events: list[str] = []
    event_bus.subscribe(
        "StepStarted", lambda e: received_events.append(e.payload.get("capability", ""))
    )

    plan = planner.plan_and_execute(
        goal_text="enable Wi-Fi adapter", capability="network.enable_adapter"
    )

    assert plan.is_successful is True
    assert plan.state == PlanState.COMPLETED
    assert "list_network_interfaces" in received_events
    assert "network.enable_adapter" in received_events
    assert "network.default_interface" in received_events


def test_integration_window_list_goal(planner):
    plan = planner.plan_and_execute(goal_text="list all open windows")

    assert plan.is_successful is True
    assert plan.state == PlanState.COMPLETED
    assert len(plan.steps) >= 1
    assert plan.steps[0].capability == "list_windows"
    assert plan.steps[0].status == StepStatus.SUCCESS


def test_integration_power_battery_goal(planner):
    plan = planner.plan_and_execute(goal_text="get battery level")

    assert plan.is_successful is True
    assert plan.state == PlanState.COMPLETED
    assert any(s.capability == "power.battery" for s in plan.steps)


def test_state_machine_transition_history(planner):
    plan = planner.create_plan("check network latency")
    history_states = [st for st, _ in plan.state_tracker.get_history()]

    assert PlanState.CREATED in history_states
    assert PlanState.ANALYZED in history_states
    assert PlanState.PLANNED in history_states
    assert PlanState.OPTIMIZED in history_states

    planner.execute_plan(plan)
    history_states_after = [st for st, _ in plan.state_tracker.get_history()]
    assert PlanState.EXECUTING in history_states_after
    assert PlanState.COMPLETED in history_states_after
