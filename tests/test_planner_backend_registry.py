"""
Unit tests for PlannerRegistry and BackendRegistry (Cognitive Orchestration Layer).
"""

import pytest

from src.core.backends.adapters.antigravity_backend import AntigravityBackendAdapter
from src.core.backends.backend_registry import (
    BackendRegistry,
    DefaultNativeDesktopAdapter,
)
from src.core.backends.base_backend import BaseBackendAdapter
from src.core.orchestration.planner_registry import PlannerRegistry


def test_planner_registry_retrieval():
    PlannerRegistry.reset_instance()
    registry = PlannerRegistry.get_instance()

    desktop_p = registry.get_planner("desktop")
    assert desktop_p is not None

    research_p = registry.get_planner("research")
    assert research_p is not None

    coding_p = registry.get_planner("coding")
    assert coding_p is not None


def test_backend_registry_selection():
    BackendRegistry.reset_instance()
    registry = BackendRegistry.get_instance()

    # Coding capability selection should pick Antigravity CLI
    coding_backend = registry.select_best_backend("coding")
    assert coding_backend is not None
    assert coding_backend.name == "Antigravity CLI"

    # Desktop capability selection
    desktop_backend = registry.select_best_backend("desktop")
    assert desktop_backend is not None
    assert isinstance(desktop_backend, BaseBackendAdapter)


def test_antigravity_backend_execution():
    backend = AntigravityBackendAdapter()
    res = backend.execute(capability="coding", goal="Update compatibility layer")

    assert res.success is True
    assert res.data["backend"] == "Antigravity CLI"
    assert "PYTHON_3_14_RELEASE_NOTES.md" in res.data["modified_files"]
