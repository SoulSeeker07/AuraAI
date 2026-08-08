"""
Unit tests for the Adaptive Learning Runtime Infrastructure.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from core.learning import BehaviorStore, LearningEngine, LearningRule, RuleType


def test_behavior_store_persistence(tmp_path):
    store_file = tmp_path / "BehaviorStore.json"
    store = BehaviorStore(store_path=store_file)

    # Store should be empty initially
    assert len(store.list_rules()) == 0

    # Add a custom behavior rule
    rule = LearningRule(
        rule_id="test_rule_1",
        rule_type=RuleType.BEHAVIOR,
        trigger="Summarize today's session",
        behavior={"action": "custom_summary", "format": "markdown"},
    )
    store.add_rule(rule)

    # Verify in-memory and persistence
    assert len(store.list_rules()) == 1
    assert store.get_rule("test_rule_1").trigger == "Summarize today's session"

    # Reload from disk
    store_reload = BehaviorStore(store_path=store_file)
    assert len(store_reload.list_rules()) == 1
    assert store_reload.get_rule("test_rule_1").behavior["format"] == "markdown"


def test_rule_matcher(tmp_path):
    store_file = tmp_path / "BehaviorStore.json"
    engine = LearningEngine(store=BehaviorStore(store_path=store_file))

    # Add a workflow rule trigger
    rule = LearningRule(
        rule_id="work_mode_rule",
        rule_type=RuleType.WORKFLOW,
        trigger="Launch Work Mode",
        behavior={"sequence": ["open VS Code", "open Slack"]},
    )
    engine.store.add_rule(rule)

    # Match goals
    match_exact = engine.matcher.match("Launch Work Mode")
    assert match_exact is not None
    assert match_exact.rule_id == "work_mode_rule"

    match_partial = engine.matcher.match("Please launch work mode now")
    assert match_partial is not None

    match_fail = engine.matcher.match("Summarize today's session")
    assert match_fail is None


def test_engine_analyze_feedback(tmp_path):
    store_file = tmp_path / "BehaviorStore.json"
    engine = LearningEngine(store=BehaviorStore(store_path=store_file))

    rule = engine.analyze_feedback(
        user_goal="summarize session",
        correction="use markdown bullets with timeline events",
    )

    assert rule is not None
    assert rule.rule_type == RuleType.BEHAVIOR
    assert rule.trigger == "summarize session"
    assert rule.behavior["details"] == "use markdown bullets with timeline events"
