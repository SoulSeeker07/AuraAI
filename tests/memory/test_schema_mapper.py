"""
Unit tests for Schema Mapper (classification & conflict detection)
Location: tests/memory/test_schema_mapper.py
"""

import pytest

from memory.importers.base_importer import RawMemoryFact
from memory.importers.schema_mapper import SchemaMapper, _jaccard_similarity, _tokenize
from memory.models import MemoryItem, MemoryType


class FakeCognitiveEngine:
    def __init__(self, memories: list[MemoryItem] | None = None):
        self._memories = memories or []

    def search_memories(self, query: str = "", limit: int = 5) -> list[MemoryItem]:
        query_tokens = _tokenize(query)
        res = []
        for m in self._memories:
            m_tokens = _tokenize(m.content)
            if query_tokens & m_tokens:
                res.append(m)
        return res[:limit]


def test_classify_store_by_category_hint():
    mapper = SchemaMapper()
    fact = RawMemoryFact(text="Some text", category_hint="preference")
    assert mapper.classify_store(fact) == MemoryType.PREFERENCE

    fact2 = RawMemoryFact(text="Some project fact", category_hint="project")
    assert mapper.classify_store(fact2) == MemoryType.PROJECT

    fact3 = RawMemoryFact(text="Step 1 do this", category_hint="procedural")
    assert mapper.classify_store(fact3) == MemoryType.PROCEDURAL

    fact4 = RawMemoryFact(text="Learned definition", category_hint="knowledge")
    assert mapper.classify_store(fact4) == MemoryType.SEMANTIC

    fact5 = RawMemoryFact(text="Met with team", category_hint="event")
    assert mapper.classify_store(fact5) == MemoryType.EPISODIC

    fact6 = RawMemoryFact(text="Fix bug 123", category_hint="task")
    assert mapper.classify_store(fact6) == MemoryType.TASK


def test_classify_store_by_keywords():
    mapper = SchemaMapper()
    assert mapper.classify_store(RawMemoryFact(text="I prefer using dark mode")) == MemoryType.PREFERENCE
    assert mapper.classify_store(RawMemoryFact(text="My favorite editor is VS Code")) == MemoryType.PREFERENCE
    assert mapper.classify_store(RawMemoryFact(text="This repository contains the AuraAI codebase")) == MemoryType.PROJECT
    assert mapper.classify_store(RawMemoryFact(text="Here is the step-by-step workflow to deploy")) == MemoryType.PROCEDURAL
    assert mapper.classify_store(RawMemoryFact(text="AuraAI is defined as an autonomous assistant")) == MemoryType.SEMANTIC
    assert mapper.classify_store(RawMemoryFact(text="Yesterday we discussed the new feature")) == MemoryType.EPISODIC
    assert mapper.classify_store(RawMemoryFact(text="Need to resolve the issue with audio")) == MemoryType.TASK


def test_classify_store_fallback():
    mapper = SchemaMapper()
    fact = RawMemoryFact(text="Quantum mechanics explores subatomic behavior")
    assert mapper.classify_store(fact) == MemoryType.LONG_TERM


def test_classify_topic():
    mapper = SchemaMapper()
    assert mapper.classify_topic(RawMemoryFact(text="Custom", category_hint="custom_cat")) == "imported:custom_cat"
    assert mapper.classify_topic(RawMemoryFact(text="I love VS Code as my primary editor")) == "imported:tools:editor"
    assert mapper.classify_topic(RawMemoryFact(text="Python 3.11 is installed")) == "imported:programming:python"
    assert mapper.classify_topic(RawMemoryFact(text="NVIDIA RTX 4090 GPU")) == "imported:hardware:gpu"
    assert mapper.classify_topic(RawMemoryFact(text="Something obscure without keywords")) == "imported:general"


def test_tokenize_and_jaccard():
    t1 = _tokenize("User prefers Python language")
    t2 = _tokenize("User loves Python language for coding")
    assert "prefers" in t1 and "python" in t1
    sim = _jaccard_similarity(t1, t2)
    assert 0.0 < sim < 1.0
    assert _jaccard_similarity(t1, t1) == 1.0
    assert _jaccard_similarity(set(), t1) == 0.0


def test_check_conflict_detected():
    existing = [
        MemoryItem(
            content="User prefers Python programming language for building agents",
            type=MemoryType.PREFERENCE,
        )
    ]
    engine = FakeCognitiveEngine(existing)
    mapper = SchemaMapper()

    conflict_fact = RawMemoryFact(text="User prefers Python programming language for all agent building")
    assert mapper.check_conflict(conflict_fact, engine) is True


def test_check_conflict_not_detected():
    existing = [
        MemoryItem(
            content="User prefers Python programming language",
            type=MemoryType.PREFERENCE,
        )
    ]
    engine = FakeCognitiveEngine(existing)
    mapper = SchemaMapper()

    non_conflict_fact = RawMemoryFact(text="User likes drinking espresso in the morning")
    assert mapper.check_conflict(non_conflict_fact, engine) is False
