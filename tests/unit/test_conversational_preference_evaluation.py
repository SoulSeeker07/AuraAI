"""
Real-World Conversational Phrasing & Anti-Hallucination Evaluation for Preference Learner
Location: tests/unit/test_conversational_preference_evaluation.py

Evaluates messy, real-world conversational turns against PreferenceLearner to assert:
1. Natural phrasing detection ("going forward I guess", "keep everything concise").
2. Negative bug/diagnostic suppression ("bug in dark mode", "error in pytest").
3. Multi-turn conversational progression and clean prompt context synthesis.
"""

import sys
from pathlib import Path
import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from memory.cognitive_memory import CognitiveMemoryEngine
from memory.preference_learner import PreferenceLearner


@pytest.fixture
def temp_db(tmp_path):
    return tmp_path / "test_eval_memory.db"


@pytest.fixture
def memory_engine(temp_db):
    return CognitiveMemoryEngine(db_path=temp_db)


# ── 1. Real Conversational Phrasing Test Cases ────────────────────────────────


def test_conversational_hedged_confirmation():
    learner = PreferenceLearner()
    # Hedged phrasing with "going forward"
    text = "yeah let's just go with pnpm going forward I guess"
    candidates = learner.extract_preference_candidates(text, session_id="real_sess_1")

    assert len(candidates) == 1
    assert candidates[0].metadata["status"] == "CONFIRMED"
    assert candidates[0].metadata["keyword"] == "pnpm"
    assert candidates[0].confidence >= 0.90


def test_conversational_communication_style_extraction():
    learner = PreferenceLearner()
    text = "I hate verbose output, keep everything concise"
    candidates = learner.extract_preference_candidates(text, session_id="real_sess_2")

    assert len(candidates) == 1
    assert candidates[0].metadata["status"] == "CONFIRMED"
    assert candidates[0].metadata["category"] == "communication"
    assert candidates[0].metadata["keyword"] == "concise"


# ── 2. Negative Bug & Diagnostic Context Suppression ──────────────────────────


@pytest.mark.parametrize(
    "bug_query",
    [
        "there's a bug in dark mode where buttons turn white",
        "why is pytest failing with an unhandled exception here?",
        "got an error running docker container on windows",
        "can you help with investigating this black formatting issue?",
        "diagnose why mypy crashed on line 45",
    ],
)
def test_suppresses_bug_reports_and_diagnostics(bug_query):
    learner = PreferenceLearner()
    candidates = learner.extract_preference_candidates(bug_query, session_id="bug_sess")

    # MUST NOT extract a positive user preference from a bug description or diagnostic question
    assert len(candidates) == 0, f"False positive extracted from bug query: {bug_query}"


# ── 3. Multi-Turn Session Progression ─────────────────────────────────────────


def test_multi_turn_realistic_lifecycle(memory_engine):
    # Turn 1: Bug report about npm -> No preference extracted
    t1 = memory_engine.learn_preferences_from_text("there's an issue with npm installing peer deps", session_id="turn_1")
    assert len(t1) == 0

    # Turn 2: User tries yarn as a quick one-off -> PROVISIONAL
    t2 = memory_engine.learn_preferences_from_text("can you test this with yarn real quick?", session_id="turn_2")
    assert len(t2) == 1
    assert t2[0].metadata["status"] == "PROVISIONAL"
    assert t2[0].metadata["keyword"] == "yarn"

    # Context check: Provisional NOT injected
    recalled = memory_engine.recall_ranked("tooling", limit=5)
    ctx = memory_engine.context_formatter.format_planning_context(recalled)
    assert "yarn" not in ctx

    # Turn 3: User decides to stick with pnpm -> CONFIRMED + Supersedes yarn
    t3 = memory_engine.learn_preferences_from_text("actually let's stick with pnpm going forward", session_id="turn_3")
    assert len(t3) >= 1
    pnpm_item = next((m for m in t3 if m.metadata.get("keyword") == "pnpm"), None)
    assert pnpm_item is not None
    assert pnpm_item.metadata["status"] == "CONFIRMED"

    # Context check: Now pnpm IS injected in <user_preferences>, and yarn is excluded
    recalled_final = memory_engine.recall_ranked("tooling", limit=5)
    ctx_final = memory_engine.context_formatter.format_planning_context(recalled_final)
    assert "<user_preferences>" in ctx_final
    assert "pnpm" in ctx_final
    assert "yarn" not in ctx_final
