"""
Phase 3 Desktop Planner Expansion Unit Test Suite

Tests:
1. BasePlanner abstract class contract.
2. GoalParser and GoalClassifier intent resolution.
3. GoalGraph node generation and duration estimates.
4. PlanOptimizer deduplication and optimization.
5. ExecutionMonitor metrics tracking.
6. PlanCache caching and retrieval.
"""

import pytest

from desktop.native.capability_registry import CapabilityRegistry
from desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
    reset_desktop_execution_engine,
)
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.planner import (
    BasePlanner,
    DesktopGoal,
    DesktopPlanner,
    ExecutionMonitor,
    GoalClassifier,
    GoalGraph,
    GoalParser,
    GoalPriority,
    PlanCache,
    PlanOptimizer,
)


@pytest.fixture
def cap_registry():
    return CapabilityRegistry()


@pytest.fixture
def engine(cap_registry):
    reset_desktop_execution_engine()
    reg = NativeManagerRegistry.get_instance()
    reg.discover("desktop.native.managers")
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


def test_base_planner_inheritance(planner):
    assert isinstance(planner, BasePlanner)


def test_goal_parser_and_classifier():
    parser = GoalParser()
    classifier = GoalClassifier()

    goal = parser.parse("urgent check wifi connection")
    assert goal.priority == GoalPriority.CRITICAL
    assert classifier.classify(goal.goal) == "network"

    parsed_cap = parser.parse("clipboard.read_text:get copied data")
    assert parsed_cap.explicit_capability == "clipboard.read_text"


def test_goal_graph_building(cap_registry):
    goal = DesktopGoal(goal="enable wifi")
    graph_builder = GoalGraph(registry=cap_registry)

    nodes = graph_builder.build_graph(goal, "network.enable_adapter")
    assert len(nodes) >= 3
    caps = [n.capability for n in nodes]
    assert "list_network_interfaces" in caps
    assert "network.enable_adapter" in caps
    assert "network.default_interface" in caps


def test_plan_optimizer(planner):
    plan = planner.create_plan("enable wifi", capability="network.enable_adapter")
    initial_count = len(plan.steps)

    optimizer = PlanOptimizer()
    optimized = optimizer.optimize(plan)
    assert len(optimized.steps) <= initial_count


def test_execution_monitor(planner):
    plan = planner.create_plan("get battery level", capability="power.battery")
    executed = planner.execute_plan(plan)

    summary = planner.monitor.get_summary()
    assert summary["total_steps"] >= 1
    assert summary["successful_steps"] >= 1
    assert summary["total_duration_ms"] >= 0.0


def test_plan_cache(planner):
    cache = PlanCache(max_size=10)

    p1 = planner.create_plan("check volume", capability="get_volume")
    cache.put("check volume", p1)

    cached = cache.get("check volume")
    assert cached is not None
    assert cached.plan_id == p1.plan_id
