"""
Golden Path Runtime Integration Test Suite
============================================
Tests the complete end-to-end cognitive execution pipeline:
User Goal -> AuraCore.process_request() -> Memory Recall -> DecisionEngine ->
MasterOrchestrator -> TaskDecomposer -> SupervisorAgent -> PlannerRegistry ->
BackendRegistry -> ExecutionResult -> ResultMerger -> Memory Write -> Final Response.
"""

import pytest

from core.backends import BackendRegistry
from core.orchestration import (
    AgentSession,
    DecisionEngine,
    ExecutionBudget,
    IntentType,
    MasterOrchestrator,
    PlannerRegistry,
)


@pytest.mark.asyncio
async def test_golden_path_full_runtime_execution():
    """Verify that a goal flows through the entire 7-stage cognitive pipeline cleanly."""
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    goal = "Check desktop awareness and open notepad"
    budget = ExecutionBudget(max_time_seconds=30.0, local_only=True)

    result = await orchestrator.process_request_async(goal_text=goal, budget=budget)

    assert result is not None
    assert isinstance(result.success, bool)
    assert result.goal == goal
    assert len(result.observations) > 0

    # Verify DecisionEngine ran
    decision_obs = [
        obs
        for obs in result.observations
        if "DecisionEngine" in obs or "Decision" in obs
    ]
    assert len(decision_obs) > 0
    assert result.planner != ""


@pytest.mark.asyncio
async def test_system_query_routing_does_not_invoke_research():
    """Verify system query intent (who are you / capabilities) does NOT invoke external research."""
    engine = DecisionEngine()
    goal = "Hi Aura. Tell me what you are and what capabilities you currently have."
    outcome = engine.evaluate(goal=goal)

    assert outcome.intent_type == IntentType.SYSTEM_QUERY
    assert outcome.should_search_first is False


@pytest.mark.asyncio
async def test_desktop_action_routing():
    """Verify desktop commands route to DESKTOP_ACTION intent."""
    engine = DecisionEngine()
    goal = "Open notepad and read clipboard text"
    outcome = engine.evaluate(goal=goal)

    assert outcome.intent_type == IntentType.DESKTOP_ACTION


@pytest.mark.asyncio
async def test_coding_request_routing():
    """Verify coding goals route to CODING intent."""
    engine = DecisionEngine()
    goal = "Refactor code and write python unit tests for auth module"
    outcome = engine.evaluate(goal=goal)

    assert outcome.intent_type == IntentType.CODING


@pytest.mark.asyncio
async def test_research_request_routing():
    """Verify explicit research goals route to RESEARCH intent."""
    engine = DecisionEngine()
    goal = "Research web search for OAuth2 security best practices"
    outcome = engine.evaluate(goal=goal)

    assert outcome.intent_type == IntentType.RESEARCH
    assert outcome.should_search_first is True


@pytest.mark.asyncio
async def test_latency_metrics_recorded():
    """Verify stage latency metrics are recorded in session and execution result."""
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    goal = "Tell me what you are"
    result = await orchestrator.process_request_async(goal_text=goal)

    metrics = result.data.get("metrics", {})
    assert "memory_recall_ms" in metrics
    assert "decision_engine_ms" in metrics
    assert "decomposition_ms" in metrics
    assert "execution_ms" in metrics
    assert "result_merger_ms" in metrics
    assert "total_request_ms" in metrics


@pytest.mark.asyncio
async def test_real_desktop_workflow():
    """Verify multi-step desktop workflow (Open Notepad, Create file, Write text, Save)."""
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    goal = (
        "Open Notepad, create notes.md on Desktop, write 'Testing Aura', save and close"
    )
    result = await orchestrator.process_request_async(goal_text=goal)

    assert result is not None
    assert result.success is True
    assert len(result.observations) > 0


@pytest.mark.asyncio
async def test_multi_planner_mixed_workflow():
    """Verify multi-planner mixed workflow combining research, coding synthesis, and desktop opening."""
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    goal = "Research latest Python release, create markdown summary, save into workspace, and open VS Code"
    result = await orchestrator.process_request_async(goal_text=goal)

    assert result is not None
    assert result.success is True
    metrics = result.data.get("metrics", {})
    assert metrics.get("subtasks_total", 0) >= 2
