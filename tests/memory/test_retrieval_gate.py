"""
Unit tests for Memory Retrieval Gate
Location: tests/memory/test_retrieval_gate.py
"""

from unittest.mock import MagicMock

import pytest

from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource
from memory.recall_engine import RecallEngine
from memory.retrieval_gate import (
    DomainClassifier,
    FactSource,
    InjectedFact,
    MemoryContext,
    MemoryRetrievalGate,
)


class FakeCognitiveEngineWithRecall:
    """Fake CognitiveMemoryEngine that supports recall_ranked and has a real RecallEngine."""

    def __init__(self, memories: list[MemoryItem] | None = None):
        self.memories = memories or []
        self.recall_engine = RecallEngine()

    def recall_ranked(self, query: str, active_project: str = "global", limit: int = 10) -> list[MemoryItem]:
        scored = self.recall_engine.score_and_rank(query, self.memories, active_project=active_project, limit=limit)
        return [m for s, m in scored]


def test_domain_classifier_generic_query():
    classifier = DomainClassifier()
    # Generic question with no personal/preference/tech keywords
    scores = classifier.classify("What is the capital of France?")
    assert len(scores) == 0


def test_domain_classifier_preference_query():
    classifier = DomainClassifier()
    scores = classifier.classify("What is my favorite text editor?")
    assert "preferences" in scores
    assert scores["preferences"] >= 0.10


def test_domain_classifier_sensitive_domain():
    classifier = DomainClassifier()
    scores = classifier.classify("What medication did my doctor prescribe?")
    assert "health" in scores


def test_retrieval_gate_skips_generic_query():
    engine = FakeCognitiveEngineWithRecall([
        MemoryItem(content="Favorite editor is VS Code", type=MemoryType.PREFERENCE, importance=0.9, confidence=1.0)
    ])
    gate = MemoryRetrievalGate(engine, domain_prefilter_min=0.10)

    ctx = gate.get_context("What is the capital of France?")
    assert ctx.retrieval_skipped is True
    assert ctx.skip_reason == "no_domain_match"
    assert len(ctx.facts) == 0
    assert ctx.to_prompt_fragment() == ""


def test_retrieval_gate_surfaces_relevant_preference():
    mem = MemoryItem(
        content="User's favorite code editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=1.0,
        provenance=MemoryProvenance(source_type=ProvenanceSource.USER_EXPLICIT),
    )
    engine = FakeCognitiveEngineWithRecall([mem])
    gate = MemoryRetrievalGate(engine, min_relevance=0.20, domain_prefilter_min=0.10)

    ctx = gate.get_context("What is my favorite editor?")
    assert ctx.retrieval_skipped is False
    assert len(ctx.facts) >= 1
    assert "VS Code" in ctx.facts[0].text
    assert ctx.facts[0].source == FactSource.OBSERVED

    # Check to_prompt_fragment outputs bare statements without meta-narration
    fragment = ctx.to_prompt_fragment()
    assert fragment.startswith("- User's favorite code editor is VS Code")
    assert "I recall" not in fragment
    assert "based on memory" not in fragment.lower()


def test_retrieval_gate_imported_fact_discount():
    imported_mem = MemoryItem(
        content="User likes dark theme in terminal",
        type=MemoryType.PREFERENCE,
        importance=0.8,
        confidence=0.60,
        provenance=MemoryProvenance(source_type=ProvenanceSource.CLAUDE_IMPORT),
    )
    engine = FakeCognitiveEngineWithRecall([imported_mem])
    # Set threshold high enough that discounted fact might be affected or checked
    gate = MemoryRetrievalGate(engine, min_relevance=0.10, imported_discount=0.70, domain_prefilter_min=0.10)

    ctx = gate.get_context("What terminal theme do I like?")
    assert len(ctx.facts) == 1
    assert ctx.facts[0].source == FactSource.IMPORTED
    # effective_confidence = 0.60 * 0.70 = 0.42
    assert ctx.facts[0].effective_confidence == pytest.approx(0.42, 0.01)


def test_retrieval_gate_excludes_pending_confirmation():
    unconfirmed_mem = MemoryItem(
        content="User prefers Vim over VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=0.0,
        metadata={"pending_confirmation": True},
    )
    engine = FakeCognitiveEngineWithRecall([unconfirmed_mem])
    gate = MemoryRetrievalGate(engine, domain_prefilter_min=0.10)

    ctx = gate.get_context("What editor do I prefer?")
    assert len(ctx.facts) == 0
    assert ctx.skip_reason == "all_pending_confirmation"


def test_retrieval_gate_fail_closed_on_exception():
    bad_engine = MagicMock()
    bad_engine.recall_ranked.side_effect = RuntimeError("Database locked")
    gate = MemoryRetrievalGate(bad_engine, domain_prefilter_min=0.10)

    # Should not raise exception — returns empty context
    ctx = gate.get_context("What is my favorite editor?")
    assert ctx.retrieval_skipped is True
    assert ctx.skip_reason == "retrieval_error"
    assert len(ctx.facts) == 0
