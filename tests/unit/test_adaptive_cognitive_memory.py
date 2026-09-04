"""
Unit & Integration Tests for Adaptive Cognitive Memory 2.0
Location: tests/unit/test_adaptive_cognitive_memory.py

Tests:
- Explicit vs. Provisional preference extraction.
- Multi-hit promotion of provisional preferences (N >= 2).
- Conflict resolution and superseded preference tracking.
- Access count reinforcement and anti-popularity importance floor.
- Structured prompt context formatting with token limits.
- End-to-end integration via CognitiveMemoryEngine.
"""

import sys
from pathlib import Path
import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from memory.cognitive_memory import CognitiveMemoryEngine
from memory.context_formatter import MemoryContextFormatter
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource
from memory.preference_learner import PreferenceLearner
from memory.recall_engine import RecallEngine


@pytest.fixture
def temp_db(tmp_path):
    return tmp_path / "test_adaptive_memory.db"


@pytest.fixture
def memory_engine(temp_db):
    return CognitiveMemoryEngine(db_path=temp_db)


# ── 1. Explicit vs. Provisional Extraction Tests ───────────────────────────────


def test_explicit_preference_extraction():
    learner = PreferenceLearner()
    text = "Always use pytest -v for running backend unit tests"
    candidates = learner.extract_preference_candidates(text, session_id="sess_1")

    assert len(candidates) == 1
    pref = candidates[0]
    assert pref.type == MemoryType.PREFERENCE
    assert pref.metadata["status"] == "CONFIRMED"
    assert pref.metadata["is_explicit"] is True
    assert pref.confidence >= 0.90
    assert pref.importance >= 0.85
    assert pref.provenance.source_type == ProvenanceSource.USER_EXPLICIT
    assert pref.provenance.verified is True


def test_provisional_preference_extraction():
    learner = PreferenceLearner()
    text = "run tests with ruff"
    candidates = learner.extract_preference_candidates(text, session_id="sess_2")

    assert len(candidates) == 1
    pref = candidates[0]
    assert pref.type == MemoryType.PREFERENCE
    assert pref.metadata["status"] == "PROVISIONAL"
    assert pref.metadata["is_explicit"] is False
    assert pref.confidence == 0.50
    assert pref.importance == 0.40
    assert pref.provenance.verified is False


# ── 2. Multi-Hit Promotion Tests ──────────────────────────────────────────────


def test_multi_hit_provisional_promotion(memory_engine):
    # Session 1: One-off command -> PROVISIONAL
    items1 = memory_engine.learn_preferences_from_text("use pnpm for this installation", session_id="sess_1")
    assert len(items1) == 1
    assert items1[0].metadata["status"] == "PROVISIONAL"
    assert items1[0].metadata["hit_count"] == 1

    # Format context -> provisional should NOT be injected
    recalled = memory_engine.recall_ranked("package manager", limit=5)
    ctx = memory_engine.context_formatter.format_planning_context(recalled, include_provisional=False)
    assert "pnpm" not in ctx

    # Session 2: Second occurrence -> Promoted to CONFIRMED
    items2 = memory_engine.learn_preferences_from_text("run build with pnpm", session_id="sess_2")
    assert len(items2) == 1
    assert items2[0].metadata["status"] == "CONFIRMED"
    assert items2[0].metadata["hit_count"] == 2
    assert items2[0].confidence >= 0.90

    # Format context -> Now CONFIRMED is injected
    recalled = memory_engine.recall_ranked("package manager", limit=5)
    ctx = memory_engine.context_formatter.format_planning_context(recalled, include_provisional=False)
    assert "<user_preferences>" in ctx
    assert "pnpm" in ctx


# ── 3. Conflict Resolution & Superseding Tests ────────────────────────────────


def test_conflict_resolution_supersedes_older_preference(memory_engine):
    # Set initial preference
    memory_engine.learn_preferences_from_text("I prefer light theme for daytime work", session_id="sess_1")
    recalled = memory_engine.recall_ranked("theme", limit=5)
    assert any("light" in m.content for m in recalled)

    # User changes preference
    memory_engine.learn_preferences_from_text("From now on, always use dark theme", session_id="sess_2")
    recalled_after = memory_engine.recall_ranked("theme", limit=5)

    # Dark theme should be active CONFIRMED
    dark_item = next((m for m in recalled_after if "dark" in m.content), None)
    assert dark_item is not None
    assert dark_item.metadata["status"] == "CONFIRMED"

    # Context formatting should only contain dark theme
    ctx = memory_engine.context_formatter.format_planning_context(recalled_after)
    assert "dark theme" in ctx
    assert "light theme" not in ctx


# ── 4. Normalized Reinforcement & Anti-Popularity Floor Tests ─────────────────


def test_recall_engine_anti_popularity_floor():
    engine = RecallEngine()

    # Rare, high-importance architectural constraint (accessed once)
    high_imp = MemoryItem(
        content="Never execute backend commands without approval token",
        type=MemoryType.LONG_TERM,
        importance=0.95,
        confidence=0.95,
        access_count=1,
        project_id="AuraAI",
    )

    # Noisy, low-importance trivia (accessed 100 times)
    noisy_trivial = MemoryItem(
        content="User said hello",
        type=MemoryType.SHORT_TERM,
        importance=0.20,
        confidence=0.50,
        access_count=100,
        project_id="AuraAI",
    )

    scored = engine.score_and_rank("command execution", [high_imp, noisy_trivial], active_project="AuraAI")
    assert len(scored) == 2
    # High importance MUST rank first despite low access count
    assert scored[0][1].content == high_imp.content
    assert scored[0][0] > scored[1][0]


def test_access_reinforcement_updates_db(memory_engine):
    item = MemoryItem(
        content="User primary runtime is Python 3.11",
        type=MemoryType.PREFERENCE,
        importance=0.85,
        project_id="global",
    )
    memory_engine.store_memory(item)
    assert item.access_count == 0

    # Recall ranked should reinforce access count
    recalled = memory_engine.recall_ranked("Python", record_access_stats=True)
    assert len(recalled) == 1

    # Check updated access count from fresh query
    recalled_again = memory_engine.recall_ranked("Python", record_access_stats=False)
    assert recalled_again[0].access_count == 1


# ── 5. Context Formatter Token Limits & Tag Structure ─────────────────────────


def test_context_formatter_token_bounding():
    formatter = MemoryContextFormatter(max_tokens=50)  # ~200 chars

    items = [
        MemoryItem(content=f"User preference #{i}: Detailed coding preference line {i}", type=MemoryType.PREFERENCE, importance=0.8)
        for i in range(10)
    ]
    ctx = formatter.format_planning_context(items)
    assert "<user_preferences>" in ctx
    assert len(ctx) <= 250
