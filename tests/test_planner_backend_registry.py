"""
Unit tests for PlannerRegistry and BackendRegistry (Milestone 16 Phases 2 & 3).
"""

import pytest
from src.execution.antigravity_backend import AntigravityBackend
from src.routing.backend_registry import BackendRegistry, GroqResearchBackend, NativeDesktopBackend
from src.routing.planner_registry import CodingPlanner, DesktopPlanner, PlannerRegistry, ResearchPlanner
from src.routing.task_decomposer import PlannerRole, SubTask


def test_planner_registry_retrieval():
    registry = PlannerRegistry()

    desktop_p = registry.get_planner(PlannerRole.DESKTOP)
    assert isinstance(desktop_p, DesktopPlanner)

    research_p = registry.get_planner(PlannerRole.RESEARCH)
    assert isinstance(research_p, ResearchPlanner)

    coding_p = registry.get_planner(PlannerRole.CODING)
    assert isinstance(coding_p, CodingPlanner)


def test_backend_registry_selection():
    registry = BackendRegistry()
    registry.register(AntigravityBackend())

    # Coding capability selection should pick Antigravity CLI (Score 0.98)
    coding_backend = registry.select_backend("coding")
    assert coding_backend.metadata.name == "Antigravity CLI"

    # Desktop capability selection
    desktop_backend = registry.select_backend("desktop")
    assert isinstance(desktop_backend, NativeDesktopBackend)


def test_antigravity_backend_execution():
    backend = AntigravityBackend()
    plan = {"task": "Update compatibility layer", "context": {}}

    res = backend.execute(plan)
    assert res["status"] == "success"
    assert res["backend"] == "Antigravity CLI"
    assert "PYTHON_3_14_RELEASE_NOTES.md" in res["modified_files"]
