"""
Unit tests for Decision Trace (Explainability), World Timeline, and Session Replay.
Location: tests/browser/test_decision_trace_and_timeline.py
"""

import pytest

from src.core.orchestration.agent_session import AgentSession
from src.core.orchestration.decision_engine import (
    DecisionEngine,
    DecisionOutcome,
    DecisionTrace,
)
from src.core.orchestration.ownership_tracker import (
    ResourceOwner,
    ResourceOwnershipTracker,
)
from src.core.orchestration.session_replay import SessionReplay
from src.core.orchestration.world_timeline import TimelineEvent, WorldTimeline


def test_decision_trace_generation():
    engine = DecisionEngine()
    outcome = engine.evaluate("Open Instagram")

    assert isinstance(outcome, DecisionOutcome)
    assert outcome.trace is not None
    assert isinstance(outcome.trace, DecisionTrace)
    assert outcome.trace.goal == "Open Instagram"
    assert len(outcome.trace.reasoning_steps) > 0
    assert "browser" in outcome.trace.chosen_planner
    assert "Playwright" in outcome.trace.chosen_backend
    assert "Inspect World" in outcome.trace.policy_applied


def test_world_timeline_logging():
    timeline = WorldTimeline.get_instance()
    timeline.clear()

    evt1 = timeline.record_event(
        "process_start",
        "Chrome process launched",
        resource_id="chrome_123",
        owner="aura",
    )
    evt2 = timeline.record_event(
        "tab_focus", "Instagram tab focused", resource_id="win_456", owner="aura"
    )

    recent = timeline.get_recent_events(minutes=15)
    assert len(recent) == 2
    assert recent[0].event_type == "process_start"
    assert recent[1].event_type == "tab_focus"

    summary = timeline.format_summary(minutes=15)
    assert "Chrome process launched" in summary
    assert "Instagram tab focused" in summary


def test_session_replay_explanation():
    session = AgentSession(goal="Open Instagram")
    engine = DecisionEngine()
    outcome = engine.evaluate(session.goal)
    session.decision_trace = outcome.trace

    timeline = WorldTimeline.get_instance()
    timeline.clear()
    timeline.record_event(
        "session_start",
        "Session started for goal: 'Open Instagram'",
        session_id=session.session_id,
    )

    explanation = SessionReplay.explain_session(session)

    assert "Session Replay & Explanation" in explanation
    assert "Open Instagram" in explanation
    assert "Policy Applied:" in explanation
    assert "Reasoning Steps:" in explanation


def test_session_replay_resource_protection_explanation():
    tracker = ResourceOwnershipTracker.get_instance()
    tracker.clear()

    tracker.register_resource("tab", "user_tab_spotify", owner=ResourceOwner.USER)
    tracker.register_resource(
        "tab",
        "aura_tab_chrome",
        owner=ResourceOwner.AURA,
        details={"reason": "Research Python"},
    )

    user_exp = SessionReplay.explain_resource_protection("user_tab_spotify", "tab")
    aura_exp = SessionReplay.explain_resource_protection("aura_tab_chrome", "tab")

    assert "ResourceOwner.USER" in user_exp
    assert "preserved and never closed automatically" in user_exp

    assert "ResourceOwner.AURA" in aura_exp
    assert "eligible for automatic cleanup" in aura_exp
