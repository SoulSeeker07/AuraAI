"""
Phase 3.3 Adaptive Planning & Execution Memory Test Suite

Tests:
1. Universal ExecutionTrace and ExecutionTraceNode.
2. PlanEvaluator quality scoring (0-100).
3. ExecutionMemory plan storage, retrieval, and statistics.
4. StrategySelector learning and optimal adapter preference.
5. DesktopPlanner.explain_plan() Dry Run / Explain Mode.
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
    DesktopPlanner,
    EvaluationResult,
    ExecutionMemory,
    ExecutionTrace,
    PlanEvaluator,
    StrategySelector,
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


def test_universal_execution_trace():
    trace = ExecutionTrace(trace_id="t1", agent_subsystem="desktop", goal="test goal")
    trace.add_node("Parse", "Parsed goal", duration_ms=1.5)
    trace.complete(success=True, score=95.0)

    t_dict = trace.to_dict()
    assert t_dict["agent_subsystem"] == "desktop"
    assert t_dict["is_successful"] is True
    assert t_dict["quality_score"] == 95.0
    assert len(t_dict["nodes"]) == 1


def test_plan_evaluator_scoring(planner):
    plan = planner.plan_and_execute("check master volume")
    evaluator = PlanEvaluator()

    res = evaluator.evaluate(plan)
    assert isinstance(res, EvaluationResult)
    assert res.overall_score >= 80.0
    assert res.verification_passed is True
    assert "Plan succeeded" in res.summary


def test_execution_memory_storage_and_reuse(planner):
    memory = ExecutionMemory()
    plan1 = planner.plan_and_execute("check wifi connection")

    assert planner.last_evaluation is not None
    memory.store_plan(plan1, planner.last_evaluation)

    stats = memory.get_summary_stats()
    assert stats["total_plans"] == 1
    assert stats["successful_plans"] == 1

    reused_plan = memory.find_best_plan("check wifi connection")
    assert reused_plan is not None
    assert reused_plan.plan_id == plan1.plan_id


def test_strategy_selector_learning():
    selector = StrategySelector()
    selector.record_execution("network.interfaces", "WMINetworkAdapter", True, 20.0)
    selector.record_execution("network.interfaces", "PsutilNetworkAdapter", True, 5.0)

    best = selector.select_best_adapter(
        "network.interfaces", ["WMINetworkAdapter", "PsutilNetworkAdapter"]
    )
    assert best == "PsutilNetworkAdapter"


def test_dry_run_explain_plan(planner):
    explanation = planner.explain_plan(
        "enable wifi adapter", capability="network.enable_adapter"
    )

    assert explanation["goal"] == "enable wifi adapter"
    assert explanation["total_steps"] >= 3
    assert explanation["overall_risk_level"] in ("HIGH", "CRITICAL")
    assert "control" in explanation["required_permissions"]
    assert "Plan requires" in explanation["explain_summary"]
