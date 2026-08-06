"""
Unit tests for MasterOrchestrator, DecisionEngine, and AgentSession (Cognitive Orchestration Layer).
"""

import pytest

from core.backends.backend_registry import BackendRegistry
from core.orchestration.agent_session import AgentSession, ExecutionBudget
from core.orchestration.decision_engine import DecisionEngine
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.planner_registry import PlannerRegistry


def test_decision_engine_evaluation():
    engine = DecisionEngine()
    budget = ExecutionBudget(max_time_seconds=15.0, local_only=True)
    outcome = engine.evaluate(
        "Research Python 3.14 changes and update code", budget=budget
    )

    assert outcome.should_search_first is False  # Local-only budget disables web search
    assert outcome.budget.max_time_seconds == 15.0


def test_master_orchestrator_agent_session():
    MasterOrchestrator.reset_instance()
    PlannerRegistry.reset_instance()
    BackendRegistry.reset_instance()

    orchestrator = MasterOrchestrator.get_instance()
    goal = "Research Python 3.14 changes, summarize them, open my VS Code project, create a markdown report, and ask Antigravity to update the affected files."

    budget = ExecutionBudget(
        max_time_seconds=20.0, max_cost_usd=0.05, allow_parallel=True
    )
    result = orchestrator.process_request(goal, budget=budget)

    assert result.success is True
    assert result.planner == "cognitive_orchestrator"
    assert len(result.observations) >= 3
    assert result.data["metrics"]["subtasks_completed"] >= 3

    # Check observations and artifacts
    assert len(result.artifacts) >= 2
    assert any("DecisionEngine" in obs for obs in result.observations)
