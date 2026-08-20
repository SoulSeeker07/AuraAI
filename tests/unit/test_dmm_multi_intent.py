"""
Unit tests for DecisionMakingModule (DMM) Multi-Intent Clause Segmentation
and Sequential ExecutionMap Composition.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from brain.executive.dmm import DecisionMakingModule
from brain.executive.execution_map import Capability, ExecutionMap, StepType


@pytest.fixture
def dmm():
    return DecisionMakingModule()


def test_single_intent_app_launch(dmm):
    emap = dmm.analyze("open notepad")
    assert isinstance(emap, ExecutionMap)
    assert Capability.DESKTOP in emap.required_capabilities
    assert any(step.parameters.get("app_name") == "notepad" for step in emap.execution_plan)
    assert not emap.metadata.get("compound", False)


def test_single_intent_keyboard_type(dmm):
    emap = dmm.analyze("type hello world")
    assert isinstance(emap, ExecutionMap)
    assert Capability.DESKTOP in emap.required_capabilities
    type_step = next(s for s in emap.execution_plan if s.parameters.get("capability") == "keyboard.type")
    assert type_step.parameters.get("text") == "hello world"
    assert not emap.metadata.get("compound", False)


def test_compound_intent_open_and_write(dmm):
    """Verify compound intent 'open notepad and write hello world' generates 2 coordinated clauses."""
    emap = dmm.analyze("open notepad and write hello world")
    assert isinstance(emap, ExecutionMap)
    assert emap.metadata.get("compound") is True
    assert emap.metadata.get("clause_count") == 2

    # Verify steps contain both launch/check and typing
    plan = emap.execution_plan
    assert len(plan) >= 2

    launch_step = next((s for s in plan if s.parameters.get("operation") == "launch"), None)
    assert launch_step is not None
    assert launch_step.parameters.get("app_name") == "notepad"

    type_step = next((s for s in plan if s.parameters.get("capability") == "keyboard.type"), None)
    assert type_step is not None
    assert type_step.parameters.get("text") == "hello world"
    # Target app must be propagated to typing step
    assert type_step.parameters.get("app_name") == "notepad"

    # Verify dependency wiring: typing step depends on preceding step
    assert len(type_step.depends_on) > 0


def test_compound_intent_with_quoted_text(dmm):
    """Verify quoted typing targets have quotes cleaned properly."""
    emap = dmm.analyze("launch notepad and type 'meeting notes 2026'")
    assert emap.metadata.get("compound") is True
    type_step = next(s for s in emap.execution_plan if s.parameters.get("capability") == "keyboard.type")
    assert type_step.parameters.get("text") == "meeting notes 2026"
    assert type_step.parameters.get("app_name") == "notepad"


def test_quoted_conjunction_not_split(dmm):
    """Conjunction inside quotes must not cause false-positive clause split."""
    clauses = dmm._segment_intent_clauses("search for 'cats and dogs'")
    assert len(clauses) == 1
    assert clauses[0] == "search for 'cats and dogs'"


def test_verb_gate_rejects_noun_conjunction(dmm):
    """'open notepad and calculator' does not have an action verb after 'and' -> not split."""
    clauses = dmm._segment_intent_clauses("open notepad and calculator")
    assert len(clauses) == 1
    assert clauses[0] == "open notepad and calculator"


def test_compound_intent_session_and_browser(dmm):
    """'open chrome and summarize session' splits into app launch and session summary."""
    clauses = dmm._segment_intent_clauses("open chrome and summarize session")
    assert len(clauses) == 2
    assert clauses[0] == "open chrome"
    assert clauses[1] == "summarize session"
