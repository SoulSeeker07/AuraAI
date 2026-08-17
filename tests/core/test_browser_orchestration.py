"""
Browser Orchestration & Capability Graph Integration Test Suite
Location: tests/core/test_browser_orchestration.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.planner_registry import PlannerRole
from core.orchestration.task_decomposer import TaskDecomposer


def test_browser_task_decomposition_extract():
    """Verify natural language browser extraction goal decomposes into a multi-step DAG with artifacts."""
    decomposer = TaskDecomposer()
    goal = "navigate to https://example.com and extract page content"
    graph = decomposer.decompose(goal)

    assert graph is not None
    assert len(graph.subtasks) >= 2

    # Check capabilities present
    caps = [t.capability for t in graph.subtasks.values()]
    assert "browser.navigate" in caps
    assert "browser.extract" in caps

    # Verify dependency wiring
    nav_task = next(t for t in graph.subtasks.values() if t.capability == "browser.navigate")
    extract_task = next(t for t in graph.subtasks.values() if t.capability == "browser.extract")

    assert nav_task.parameters.get("url") == "https://example.com"
    assert nav_task.task_id in extract_task.dependencies
    assert "art_browser_content" in extract_task.output_artifacts


def test_browser_task_decomposition_click():
    """Verify natural language browser click goal decomposes into a verified DAG."""
    decomposer = TaskDecomposer()
    goal = "navigate to https://example.com and click 'button#submit-order'"
    graph = decomposer.decompose(goal)

    assert graph is not None
    caps = [t.capability for t in graph.subtasks.values()]
    assert "browser.navigate" in caps
    assert "browser.click" in caps

    click_task = next(t for t in graph.subtasks.values() if t.capability == "browser.click")
    nav_task = next(t for t in graph.subtasks.values() if t.capability == "browser.navigate")

    assert click_task.parameters.get("selector") == "button#submit-order"
    assert nav_task.task_id in click_task.dependencies


def test_browser_task_decomposition_type():
    """Verify natural language browser type goal decomposes into a verified DAG."""
    decomposer = TaskDecomposer()
    goal = "navigate to https://example.com and type 'admin' into 'input#user'"
    graph = decomposer.decompose(goal)

    assert graph is not None
    caps = [t.capability for t in graph.subtasks.values()]
    assert "browser.navigate" in caps
    assert "browser.type" in caps

    type_task = next(t for t in graph.subtasks.values() if t.capability == "browser.type")
    nav_task = next(t for t in graph.subtasks.values() if t.capability == "browser.navigate")

    assert type_task.parameters.get("text") == "admin"
    assert type_task.parameters.get("selector") == "input#user"
    assert nav_task.task_id in type_task.dependencies


def test_universal_registry_validates_browser_dag_graph():
    """Verify CapabilityRegistry validates browser DAG graph topology."""
    registry = CapabilityRegistry.get_instance()

    # 1. Valid graph: browser.open -> browser.navigate -> browser.extract
    plan_caps = ["browser.open", "browser.navigate", "browser.extract"]
    res_valid = registry.validate_plan_graph(plan_caps, require_live=True, require_prerequisites=True)
    assert res_valid.valid is True
    assert len(res_valid.errors) == 0

    # 2. Missing prerequisite: navigate without open
    plan_missing = ["browser.navigate"]
    res_missing = registry.validate_plan_graph(plan_missing, require_live=True, require_prerequisites=True)
    assert res_missing.valid is False
    assert len(res_missing.missing_prerequisites) > 0
    assert "browser.open" in res_missing.missing_prerequisites[0]


def test_master_orchestrator_executes_browser_dag_mocked():
    """Verify MasterOrchestrator processes browser requests cleanly with state observation."""
    orchestrator = MasterOrchestrator()
    goal = "navigate to https://example.com and extract page content"

    result = orchestrator.process_request(goal)
    assert result.success is True
    assert len(result.observations) > 0
