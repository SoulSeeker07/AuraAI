"""
Desktop Planner Unit & Graph Resolution Test Suite

Tests:
1. DesktopGoal, DesktopStep, and DesktopPlan data models.
2. DependencyResolver resolving capability graph links into multi-step plans.
3. DesktopPlanner creating and executing plans via DesktopExecutionEngine.
"""

import pytest

from src.desktop.native.capability_registry import CapabilityRegistry
from src.desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
    reset_desktop_execution_engine,
)
from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry
from src.desktop.planner import (
    DependencyResolver,
    DesktopGoal,
    DesktopPlan,
    DesktopPlanner,
    DesktopStep,
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


def test_goal_step_plan_models():
    goal = DesktopGoal(goal="Lower brightness", parameters={"level": 50})
    assert goal.goal == "Lower brightness"
    assert goal.parameters["level"] == 50

    step = DesktopStep(
        step_id="step_1",
        capability="set_brightness",
        description="Set brightness to 50%",
        step_type=StepType.ACTION,
    )
    assert step.step_id == "step_1"
    assert step.status == StepStatus.PENDING

    plan = DesktopPlan(plan_id="p1", goal=goal)
    plan.add_step(step)
    assert len(plan.steps) == 1
    assert plan.get_step_by_id("step_1") is step


def test_dependency_resolver_graph_plan(cap_registry):
    resolver = DependencyResolver(registry=cap_registry)
    goal = DesktopGoal(goal="activate window", parameters={"window_title": "VS Code"})

    plan = resolver.resolve_plan(goal, capability_name="activate_window")

    # activate_window has requires=["list_windows"], verifies=["get_window"]
    assert len(plan.steps) >= 3
    types = [s.step_type for s in plan.steps]
    assert StepType.PREPARATION in types
    assert StepType.ACTION in types
    assert StepType.VERIFICATION in types

    prep_step = [s for s in plan.steps if s.step_type == StepType.PREPARATION][0]
    assert prep_step.capability == "list_windows"

    action_step = [s for s in plan.steps if s.step_type == StepType.ACTION][0]
    assert action_step.capability == "activate_window"

    verify_step = [s for s in plan.steps if s.step_type == StepType.VERIFICATION][0]
    assert verify_step.capability == "get_window"


def test_planner_plan_creation_and_execution(planner):
    plan = planner.create_plan(
        goal_text="enable Wi-Fi adapter",
        capability="network.enable_adapter",
        parameters={"adapter_name": "Wi-Fi"},
    )
    assert plan.plan_id.startswith("plan_")
    assert len(plan.steps) >= 3

    executed_plan = planner.execute_plan(plan)
    assert executed_plan.is_successful is True
    assert executed_plan.completed_at is not None
    assert all(s.status == StepStatus.SUCCESS for s in executed_plan.steps)


def test_planner_plan_and_execute_shortcut(planner):
    plan = planner.plan_and_execute(goal_text="check local ip address")
    assert plan.is_successful is True
    assert len(plan.steps) >= 1
    assert any(s.capability == "network.local_ip" for s in plan.steps)
