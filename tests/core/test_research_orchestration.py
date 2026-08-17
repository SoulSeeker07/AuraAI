"""
Tests for Research Orchestration and Goal Decomposition (Milestone 21)
======================================================================
Location: tests/core/test_research_orchestration.py

Verifies:
1. Natural language research goal decomposition into search -> synthesize DAGs.
2. Universal capability registry graph validation for research.* capabilities.
3. MasterOrchestrator execution of multi-step research DAG with artifact propagation.
"""

import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.planner_registry import PlannerRole
from core.orchestration.task_decomposer import TaskDecomposer


def test_task_decomposer_creates_two_step_research_dag():
    """Verify compound research goal decomposes into search -> synthesize DAG."""
    decomposer = TaskDecomposer()
    graph = decomposer.decompose("research latest developments in quantum computing and synthesize findings")
    subtasks = list(graph.subtasks.values())

    assert len(subtasks) == 2
    t1 = subtasks[0]
    t2 = subtasks[1]

    # Task 1: research.search
    assert t1.capability == "research.search"
    assert t1.required_role == PlannerRole.RESEARCH
    assert "art_search_results" in t1.output_artifacts
    assert t1.dependencies == []

    # Task 2: research.synthesize
    assert t2.capability == "research.synthesize"
    assert t2.required_role == PlannerRole.RESEARCH
    assert "art_search_results" in t2.input_artifacts
    assert t1.task_id in t2.dependencies


def test_task_decomposer_pure_search_goal():
    """Verify pure search goal decomposes into a single research.search subtask."""
    decomposer = TaskDecomposer()
    graph = decomposer.decompose("search web for Python 3.14 release notes")
    subtasks = list(graph.subtasks.values())

    assert len(subtasks) == 1
    t1 = subtasks[0]
    assert t1.capability == "research.search"
    assert t1.required_role == PlannerRole.RESEARCH


def test_task_decomposer_deep_research_goal():
    """Verify deep research goal decomposes into research.deep_query."""
    decomposer = TaskDecomposer()
    graph = decomposer.decompose("deep research on generative autonomous agents")
    subtasks = list(graph.subtasks.values())

    assert len(subtasks) == 1
    t1 = subtasks[0]
    assert t1.capability == "research.deep_query"
    assert t1.required_role == PlannerRole.RESEARCH


def test_universal_registry_validates_research_dag_graph():
    """Verify CapabilityRegistry validates research search -> synthesize graph."""
    registry = CapabilityRegistry.get_instance()

    # 1. Valid graph: search -> synthesize
    plan_caps = ["research.search", "research.synthesize"]
    res_valid = registry.validate_plan_graph(plan_caps, require_live=True, require_prerequisites=True)
    assert res_valid.valid is True
    assert len(res_valid.errors) == 0

    # 2. Missing prerequisite: synthesize without search
    plan_missing = ["research.synthesize"]
    res_missing = registry.validate_plan_graph(plan_missing, require_live=True, require_prerequisites=True)
    assert res_missing.valid is False
    assert len(res_missing.missing_prerequisites) > 0
    assert "research.search" in res_missing.missing_prerequisites[0]


def test_master_orchestrator_executes_research_dag_end_to_end():
    """Verify MasterOrchestrator executes research search -> synthesize DAG with artifact flow."""
    orchestrator = MasterOrchestrator()
    goal = "research advancements in neuromorphic computing and synthesize findings"

    result = orchestrator.process_request(goal)

    assert result.success is True
    assert len(result.observations) > 0
    obs_all = " ".join(result.observations)
    assert "Synthesized findings" in obs_all or "sources" in obs_all.lower()

