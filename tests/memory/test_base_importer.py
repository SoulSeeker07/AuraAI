"""
Unit tests for External Memory Import Pipeline
Location: tests/memory/test_base_importer.py
"""

import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from memory.importers.base_importer import (
    IMPORTED_DEFAULT_CONFIDENCE,
    IMPORTED_DEFAULT_IMPORTANCE,
    ExternalMemoryImporter,
    ImportResult,
    RawMemoryFact,
    check_policy_gates,
)
from memory.importers.claude_importer import ClaudeImporter
from memory.importers.chatgpt_importer import ChatGPTImporter
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource


class FakeCognitiveMemoryEngine:
    """In-memory fake of CognitiveMemoryEngine for fast, isolated testing."""

    def __init__(self):
        self.memories: dict[str, MemoryItem] = {}

    def store_memory(self, memory: MemoryItem) -> MemoryItem:
        self.memories[memory.memory_id] = memory
        return memory

    def search_memories(self, query: str = "", project_id: str = "global", limit: int = 50) -> list[MemoryItem]:
        if not query:
            return list(self.memories.values())[:limit]
        query_words = set(query.lower().split())
        matched = []
        for mem in self.memories.values():
            content_words = set(mem.content.lower().split())
            if query_words & content_words:
                matched.append(mem)
        return matched[:limit]

    def count_memories(self) -> int:
        return len(self.memories)


class DummyImporter(ExternalMemoryImporter):
    """Concrete test importer that returns predefined facts."""

    def __init__(self, facts: list[RawMemoryFact]):
        self._facts = facts

    @property
    def source_name(self) -> str:
        return "dummy"

    @property
    def provenance_source(self) -> ProvenanceSource:
        return ProvenanceSource.IMPORTED

    def parse(self, export_path: str) -> list[RawMemoryFact]:
        return self._facts


def test_raw_memory_fact_creation():
    fact = RawMemoryFact(
        text="Prefers dark theme in VS Code",
        category_hint="preference",
        timestamp="2026-08-25T10:00:00",
        source="claude",
        original_key="entry_1",
    )
    assert fact.text == "Prefers dark theme in VS Code"
    assert fact.category_hint == "preference"
    assert fact.source == "claude"


def test_check_policy_gates_hard_exclusion():
    # Hard exclusion patterns like 'password is ...' or 'api_key: ...'
    passed, reason = check_policy_gates("My password is supersecret123", "security")
    assert not passed
    assert "hard_exclusion" in reason or "matched pattern" in reason


def test_check_policy_gates_sensitive_info():
    # Sensitive info patterns (e.g. ssn, credit card, health/medical)
    passed, reason = check_policy_gates("My social security number is 000-12-3456", "personal")
    assert not passed
    assert "sensitive_info" in reason or "hard_exclusion" in reason or not passed


def test_check_policy_gates_valid_fact_passes_gate_3():
    # Normal preference fact should pass even with forced importance=5
    passed, reason = check_policy_gates("User prefers writing unit tests in pytest", "tools")
    assert passed
    assert reason == "passed_all_gates"


def test_import_to_memory_basic_flow():
    engine = FakeCognitiveMemoryEngine()
    facts = [
        RawMemoryFact(text="User prefers Python over JavaScript", category_hint="preference"),
        RawMemoryFact(text="Active project is AuraAI desktop agent", category_hint="project"),
    ]
    importer = DummyImporter(facts)
    result = importer.import_to_memory("dummy_path", engine, dry_run=False)

    assert result.imported_count == 2
    assert result.skipped_count == 0
    assert result.conflict_count == 0
    assert result.batch_id.startswith("import_dummy_")
    assert len(engine.memories) == 2

    # Verify attributes of stored memories
    stored = list(engine.memories.values())
    assert any(m.type == MemoryType.PREFERENCE for m in stored)
    assert any(m.type == MemoryType.PROJECT for m in stored)
    for m in stored:
        assert m.importance == IMPORTED_DEFAULT_IMPORTANCE
        assert m.confidence == IMPORTED_DEFAULT_CONFIDENCE
        assert m.provenance.source_type == ProvenanceSource.IMPORTED
        assert m.metadata["import_batch_id"] == result.batch_id


def test_import_to_memory_dry_run():
    engine = FakeCognitiveMemoryEngine()
    facts = [
        RawMemoryFact(text="User favorite color is cyan", category_hint="preference"),
    ]
    importer = DummyImporter(facts)
    result = importer.import_to_memory("dummy_path", engine, dry_run=True)

    assert result.imported_count == 1
    assert result.skipped_count == 0
    # Dry run should NOT write to DB
    assert len(engine.memories) == 0


def test_import_to_memory_skips_policy_violations():
    engine = FakeCognitiveMemoryEngine()
    facts = [
        RawMemoryFact(text="Valid preference for dark mode", category_hint="preference"),
        RawMemoryFact(text="My secret API key is sk-1234567890abcdef", category_hint="secrets"),
    ]
    importer = DummyImporter(facts)
    result = importer.import_to_memory("dummy_path", engine, dry_run=False)

    assert result.imported_count == 1
    assert result.skipped_count == 1
    assert len(engine.memories) == 1


def test_import_to_memory_flags_conflicts():
    engine = FakeCognitiveMemoryEngine()
    # Seed an existing memory
    engine.store_memory(
        MemoryItem(
            content="User prefers Python programming language for development",
            type=MemoryType.PREFERENCE,
            importance=0.8,
            confidence=0.95,
        )
    )

    # Import an overlapping/conflicting memory
    facts = [
        RawMemoryFact(text="User prefers Python programming language for all development projects", category_hint="preference"),
    ]
    importer = DummyImporter(facts)
    result = importer.import_to_memory("dummy_path", engine, dry_run=False)

    assert result.conflict_count == 1
    assert result.pending_count == 1
    assert result.imported_count == 1

    # Find the imported memory
    imported_mem = [m for m in engine.memories.values() if m.metadata.get("import_batch_id") == result.batch_id][0]
    assert imported_mem.metadata["pending_confirmation"] is True
    assert imported_mem.confidence == 0.0


def test_claude_importer_parse_json(tmp_path):
    memories_data = [
        {"content": "Prefers concise code explanations", "type": "preference", "created_at": "2026-08-01T12:00:00"},
        {"text": "Project uses Python 3.11 with SQLite", "type": "project", "created_at": "2026-08-02T12:00:00"},
    ]
    json_file = tmp_path / "memories.json"
    json_file.write_text(json.dumps(memories_data), encoding="utf-8")

    importer = ClaudeImporter()
    facts = importer.parse(str(json_file))

    assert len(facts) == 2
    assert facts[0].text == "Prefers concise code explanations"
    assert facts[0].category_hint == "preference"
    assert facts[0].source == "claude"
    assert facts[1].text == "Project uses Python 3.11 with SQLite"


def test_chatgpt_importer_parse_json(tmp_path):
    memories_data = {
        "memory": [
            "User likes FastAPI for REST APIs",
            "User has an NVIDIA GPU on Windows",
        ]
    }
    json_file = tmp_path / "memory.json"
    json_file.write_text(json.dumps(memories_data), encoding="utf-8")

    importer = ChatGPTImporter()
    facts = importer.parse(str(json_file))

    assert len(facts) == 2
    assert facts[0].text == "User likes FastAPI for REST APIs"
    assert facts[0].source == "chatgpt"
    assert facts[1].text == "User has an NVIDIA GPU on Windows"
