"""
Unit tests for ReferenceResolver and Concrete Task Decomposer Capability Specifications.
Location: tests/browser/test_reference_resolver.py
"""

import pytest

from src.core.orchestration.reference_resolver import ReferenceResolver
from src.core.orchestration.task_decomposer import TaskDecomposer
from src.core.orchestration.world_timeline import WorldTimeline


def test_reference_resolver_substitutes_pronoun():
    timeline = WorldTimeline.get_instance()
    timeline.clear()
    timeline.record_event(
        "app_open", "Opened application 'Notepad'", resource_id="Notepad", owner="aura"
    )

    resolved_goal, meta = ReferenceResolver.resolve_references("Minimize it")

    assert meta["resolved"] is True
    assert "Notepad" in resolved_goal
    assert meta["target"] == "Notepad"


def test_task_decomposer_concrete_capabilities():
    decomposer = TaskDecomposer()

    graph_open = decomposer.decompose("Open Notepad")
    assert len(graph_open.subtasks) == 1
    t_open = list(graph_open.subtasks.values())[0]
    assert t_open.capability == "app_open"
    assert t_open.parameters["app_name"] == "notepad"

    graph_min = decomposer.decompose("Minimize Notepad")
    assert len(graph_min.subtasks) == 1
    t_min = list(graph_min.subtasks.values())[0]
    assert t_min.capability == "window.minimize"

    graph_close = decomposer.decompose("Close Notepad")
    assert len(graph_close.subtasks) == 1
    t_close = list(graph_close.subtasks.values())[0]
    assert t_close.capability == "app_close"
