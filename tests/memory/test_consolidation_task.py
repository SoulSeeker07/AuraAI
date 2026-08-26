"""
Unit tests for Auto-Dream Memory Consolidation Task
Location: tests/memory/test_consolidation_task.py
"""

import datetime as dt
from contextlib import contextmanager

import pytest

from memory.consolidation_task import (
    CONFIDENCE_CEILING,
    CONFIRMATION_BOOST,
    ConsolidationReport,
    MemoryConsolidationTask,
)
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource


class FakeEngineForConsolidation:
    """In-memory fake engine supporting all operations used by ConsolidationTask."""

    def __init__(self, memories: list[MemoryItem] | None = None):
        self.memories: dict[str, MemoryItem] = {m.memory_id: m for m in (memories or [])}

    def search_memories(self, query: str = "", limit: int = 500) -> list[MemoryItem]:
        return list(self.memories.values())[:limit]

    def store_memory(self, memory: MemoryItem) -> MemoryItem:
        self.memories[memory.memory_id] = memory
        return memory

    @contextmanager
    def _connect(self):
        class FakeCursor:
            def __init__(self, parent):
                self.parent = parent

            def execute(self, sql, params=()):
                if "DELETE FROM cognitive_memories" in sql:
                    mem_id = params[0]
                    self.parent.memories.pop(mem_id, None)

        yield FakeCursor(self)


def test_consolidation_task_dry_run():
    # Two duplicate memories
    mem1 = MemoryItem(
        memory_id="mem_1",
        content="User prefers Python for data science and AI applications",
        type=MemoryType.PREFERENCE,
        confidence=0.8,
    )
    mem2 = MemoryItem(
        memory_id="mem_2",
        content="User prefers Python for data science and AI applications",
        type=MemoryType.PREFERENCE,
        confidence=0.6,
    )
    engine = FakeEngineForConsolidation([mem1, mem2])
    task = MemoryConsolidationTask()

    report = task.run(engine, dry_run=True)
    assert report.dry_run is True
    assert report.deduped_count == 1
    # Dry run should NOT delete from engine
    assert len(engine.memories) == 2


def test_consolidation_task_dedup_merges_duplicates():
    mem1 = MemoryItem(
        memory_id="mem_1",
        content="User prefers dark theme in Visual Studio Code editor",
        type=MemoryType.PREFERENCE,
        confidence=0.9,
        access_count=5,
        metadata={"key1": "val1"},
    )
    mem2 = MemoryItem(
        memory_id="mem_2",
        content="User prefers dark theme in Visual Studio Code editor",
        type=MemoryType.PREFERENCE,
        confidence=0.6,
        access_count=2,
        metadata={"key2": "val2"},
    )
    engine = FakeEngineForConsolidation([mem1, mem2])
    task = MemoryConsolidationTask()

    report = task.run(engine, dry_run=False)
    assert report.deduped_count == 1
    # mem_2 should be deleted, mem_1 kept with merged access count & metadata
    assert "mem_1" in engine.memories
    assert "mem_2" not in engine.memories
    kept = engine.memories["mem_1"]
    assert kept.access_count == 7
    assert kept.metadata.get("key2") == "val2"
    assert kept.metadata.get("merged_from") == "mem_2"


def test_consolidation_task_prune_expired():
    # Expired memory (in past)
    expired_mem = MemoryItem(
        memory_id="mem_expired",
        content="Temporary notification banner showed",
        type=MemoryType.WORKING,
        importance=0.1,
        expires_at=(dt.datetime.now() - dt.timedelta(days=1)).isoformat(),
    )
    # Non-expired memory
    active_mem = MemoryItem(
        memory_id="mem_active",
        content="User is building AuraAI desktop application",
        type=MemoryType.PROJECT,
        importance=0.8,
    )
    engine = FakeEngineForConsolidation([expired_mem, active_mem])
    task = MemoryConsolidationTask()

    report = task.run(engine, dry_run=False)
    assert report.pruned_count >= 1
    assert "mem_expired" not in engine.memories
    assert "mem_active" in engine.memories


def test_consolidation_task_preference_safeguard_at_low_importance():
    # An imported PREFERENCE at importance=0.50 (below 0.9) must NOT be pruned
    # because type == PREFERENCE branch of the OR guard in DecayEngine protects it.
    old_time = (dt.datetime.now() - dt.timedelta(days=365)).isoformat()
    pref_mem = MemoryItem(
        memory_id="mem_pref",
        content="User prefers keyboard navigation",
        type=MemoryType.PREFERENCE,
        importance=0.50,  # Below 0.9!
        confidence=0.60,
        last_accessed=old_time,
        updated_at=old_time,
        provenance=MemoryProvenance(source_type=ProvenanceSource.CLAUDE_IMPORT),
    )
    engine = FakeEngineForConsolidation([pref_mem])
    task = MemoryConsolidationTask()

    report = task.run(engine, dry_run=False)
    assert report.pruned_count == 0
    assert "mem_pref" in engine.memories


def test_consolidation_task_audit_exempt_skipped():
    audit_entry = MemoryItem(
        memory_id="mem_audit",
        content="Consolidation run summary",
        type=MemoryType.EPISODIC,
        importance=1.0,
        metadata={"audit_exempt": True},
    )
    engine = FakeEngineForConsolidation([audit_entry])
    task = MemoryConsolidationTask()

    report = task.run(engine, dry_run=False)
    assert report.skipped_audit_count == 1
    assert "mem_audit" in engine.memories


def test_consolidation_task_confidence_promotion():
    imported = MemoryItem(
        memory_id="mem_imported",
        content="User uses Python pytest framework for automated testing",
        type=MemoryType.SEMANTIC,
        confidence=0.60,
        importance=0.50,
        provenance=MemoryProvenance(source_type=ProvenanceSource.CLAUDE_IMPORT),
    )
    observed = MemoryItem(
        memory_id="mem_observed",
        content="Session verified Python pytest framework test runs",
        type=MemoryType.EPISODIC,
        confidence=0.95,
        importance=0.80,
        provenance=MemoryProvenance(source_type=ProvenanceSource.RUNTIME_SESSION),
    )
    engine = FakeEngineForConsolidation([imported, observed])
    task = MemoryConsolidationTask()

    report = task.run(engine, dry_run=False)
    assert report.promoted_count == 1
    # 0.60 + 0.10 = 0.70
    assert engine.memories["mem_imported"].confidence == pytest.approx(0.70, 0.01)
    # Importance must remain untouched at 0.50
    assert engine.memories["mem_imported"].importance == 0.50


def test_consolidation_task_confidence_promotion_ceiling():
    imported = MemoryItem(
        memory_id="mem_imported_high",
        content="User uses Python pytest framework",
        type=MemoryType.SEMANTIC,
        confidence=0.92,
        importance=0.50,
        provenance=MemoryProvenance(source_type=ProvenanceSource.CHATGPT_IMPORT),
    )
    observed = MemoryItem(
        memory_id="mem_observed_high",
        content="User confirmed Python pytest framework",
        type=MemoryType.EPISODIC,
        confidence=0.95,
        importance=0.80,
        provenance=MemoryProvenance(source_type=ProvenanceSource.RUNTIME_SESSION),
    )
    engine = FakeEngineForConsolidation([imported, observed])
    task = MemoryConsolidationTask()

    report = task.run(engine, dry_run=False)
    assert report.promoted_count == 1
    # 0.92 + 0.10 = 1.02 -> capped at 0.95
    assert engine.memories["mem_imported_high"].confidence == CONFIDENCE_CEILING
