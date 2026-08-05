"""
Phase 8: Public API Validation Test
=====================================
Verifies that every public class / function that external code depends on
can be imported cleanly in isolation — without pulling in the entire application.

If any of these fail, it means a public API has been broken or moved without
updating the public-facing __init__.py.
"""

import pytest

# ─── Core Planning API ─────────────────────────────────────────────────────────


def test_base_planner_importable():
    """BasePlanner must be importable from core.planning."""
    from core.planning import BasePlanner

    assert BasePlanner is not None
    assert hasattr(
        BasePlanner, "create_plan"
    ), "BasePlanner must have a create_plan() method"
    assert hasattr(
        BasePlanner, "can_handle"
    ), "BasePlanner must have a can_handle() method"
    assert hasattr(
        BasePlanner, "execute_plan"
    ), "BasePlanner must have an execute_plan() method"


def test_plan_state_importable():
    """PlanState enum must be importable from core.planning."""
    from core.planning import PlanState

    assert PlanState is not None
    # Verify critical states exist
    assert hasattr(PlanState, "CREATED")
    assert hasattr(PlanState, "EXECUTING")
    assert hasattr(PlanState, "COMPLETED")
    assert hasattr(PlanState, "FAILED")


def test_execution_trace_importable():
    """ExecutionTrace must be importable from core.planning."""
    from core.planning import ExecutionTrace

    assert ExecutionTrace is not None


def test_execution_result_importable():
    """ExecutionResult must be importable from core.planning."""
    from core.planning import ExecutionResult

    assert ExecutionResult is not None


def test_plan_evaluator_importable():
    """PlanEvaluator must be importable from core.planning."""
    from core.planning import PlanEvaluator

    assert PlanEvaluator is not None


def test_plan_state_tracker_importable():
    """PlanStateTracker must be importable from core.planning."""
    from core.planning import PlanStateTracker

    assert PlanStateTracker is not None


# ─── Backend / Adapter API ─────────────────────────────────────────────────────


def test_base_backend_importable():
    """BaseBackendAdapter must be importable from core.backends."""
    from core.backends import BaseBackendAdapter

    assert BaseBackendAdapter is not None
    assert hasattr(
        BaseBackendAdapter, "execute"
    ), "BaseBackendAdapter must have an execute() method"
    assert hasattr(
        BaseBackendAdapter, "health_check"
    ), "BaseBackendAdapter must have a health_check() method"


def test_backend_registry_importable():
    """BackendRegistry must be importable from core.backends."""
    from core.backends import BackendRegistry

    assert BackendRegistry is not None


# ─── Execution Engine API ──────────────────────────────────────────────────────


def test_execution_engine_importable():
    """ExecutionEngine must be importable from execution."""
    from execution import ExecutionEngine

    assert ExecutionEngine is not None


def test_execution_context_importable():
    """ExecutionContext must be importable from execution."""
    from execution import ExecutionContext

    assert ExecutionContext is not None


def test_tool_registry_importable():
    """ToolRegistry must be importable from execution."""
    from execution import ToolRegistry

    assert ToolRegistry is not None


# ─── Desktop / Native API ──────────────────────────────────────────────────────


def test_capability_registry_importable():
    """CapabilityRegistry must be importable from desktop.native."""
    from desktop.native import CapabilityRegistry

    assert CapabilityRegistry is not None


def test_desktop_execution_engine_importable():
    """DesktopExecutionEngine must be importable from desktop.native."""
    from desktop.native import DesktopExecutionEngine

    assert DesktopExecutionEngine is not None


def test_native_manager_importable():
    """NativeManager must be importable from desktop.native."""
    from desktop.native import NativeManager

    assert NativeManager is not None


def test_native_manager_registry_importable():
    """NativeManagerRegistry must be importable from desktop.native.managers."""
    from desktop.native.managers import NativeManagerRegistry

    assert NativeManagerRegistry is not None


# ─── Desktop Planner API ───────────────────────────────────────────────────────


def test_desktop_planner_importable():
    """DesktopPlanner must be importable from desktop.planner."""
    from desktop.planner.planner import DesktopPlanner

    assert DesktopPlanner is not None


# ─── Orchestration API ─────────────────────────────────────────────────────────


def test_master_orchestrator_importable():
    """MasterOrchestrator must be importable from core.orchestration."""
    from core.orchestration import MasterOrchestrator

    assert MasterOrchestrator is not None


def test_planner_registry_importable():
    """PlannerRegistry must be importable from core.orchestration."""
    from core.orchestration import PlannerRegistry

    assert PlannerRegistry is not None
