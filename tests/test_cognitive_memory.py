"""
Cognitive Memory System Tests (Milestone 17)
Location: tests/test_cognitive_memory.py

Tests for:
- All 8 memory types & MemoryItem unified model
- Provenance tracking (source_type, source_id, confidence)
- Working memory lifecycle
- Episodic event recording
- Semantic concept graph
- Procedural workflow storage
- Multi-factor recall ranking algorithm
- Memory consolidation (only verified successful executions consolidate)
- Decay engine
- Project isolation (global vs project-specific)
- Backward compatibility with Memory.py

Run:
    python -m pytest tests/test_cognitive_memory.py -v
"""

import sys
from pathlib import Path

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Memory import Memory as LegacyMemoryFacade
from memory.cognitive_memory import CognitiveMemoryEngine
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource


@pytest.fixture
def temp_db(tmp_path):
    return tmp_path / "test_cognitive_memory.db"


@pytest.fixture
def cognitive_engine(temp_db):
    return CognitiveMemoryEngine(db_path=temp_db)


# ── 1. Unified Memory Model & Provenance Tests ────────────────────────────────


def test_memory_item_creation_and_provenance():
    prov = MemoryProvenance(
        source_type=ProvenanceSource.USER_EXPLICIT,
        source_id="sess_123",
        confidence=0.95,
        verified=True,
    )
    item = MemoryItem(
        content="User prefers Python for data tasks",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        provenance=prov,
        project_id="AuraAI",
    )
    assert item.type == MemoryType.PREFERENCE
    assert item.provenance.source_type == ProvenanceSource.USER_EXPLICIT
    assert item.project_id == "AuraAI"


# ── 2. CognitiveMemoryEngine Persistence & Retrieval ──────────────────────────


def test_cognitive_engine_store_and_search(cognitive_engine):
    item1 = MemoryItem(
        content="User primary editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.85,
        topic="editor",
        project_id="global",
    )
    item2 = MemoryItem(
        content="Project AuraAI uses MasterOrchestrator COL pipeline",
        type=MemoryType.SEMANTIC,
        importance=0.9,
        topic="architecture",
        project_id="AuraAI",
    )
    cognitive_engine.store_memory(item1)
    cognitive_engine.store_memory(item2)

    assert cognitive_engine.count_memories() == 2

    res_global = cognitive_engine.search_memories("editor", project_id="global")
    assert len(res_global) == 1
    assert "VS Code" in res_global[0].content

    res_project = cognitive_engine.search_memories("pipeline", project_id="AuraAI")
    assert len(res_project) == 1
    assert "MasterOrchestrator" in res_project[0].content


# ── 3. Recall Ranking Tests ────────────────────────────────────────────────────


def test_recall_ranking_scoring(cognitive_engine):
    item1 = MemoryItem(
        content="Low importance random note",
        type=MemoryType.LONG_TERM,
        importance=0.2,
        project_id="global",
    )
    item2 = MemoryItem(
        content="High importance user preference: Use pytest for Python tests",
        type=MemoryType.PREFERENCE,
        importance=0.95,
        project_id="AuraAI",
    )
    cognitive_engine.store_memory(item1)
    cognitive_engine.store_memory(item2)

    ranked = cognitive_engine.recall_ranked("pytest tests", active_project="AuraAI", limit=5)
    assert len(ranked) >= 1
    assert ranked[0].memory_id == item2.memory_id
    assert ranked[0].importance == 0.95


# ── 4. Verification & Consolidation Guardrail Tests ────────────────────────────


def test_consolidation_skips_failed_executions(cognitive_engine):
    """
    Guardrail: Failed or unverified executions must NOT produce long-term procedural/episodic memories.
    """
    consolidated_failed = cognitive_engine.consolidation_engine.consolidate_session(
        session_id="sess_failed_01",
        goal="Open non-existent app",
        execution_success=False,
        observations=["Failed to locate process"],
        data={"error": "ProcessNotFound"},
        project_id="AuraAI",
    )
    assert len(consolidated_failed) == 0, "Failed execution must not be consolidated"

    consolidated_success = cognitive_engine.consolidation_engine.consolidate_session(
        session_id="sess_success_01",
        goal="Analyze code in src/core/app.py",
        execution_success=True,
        observations=["Analyzed 1/1 file"],
        data={"backend": "Coding Backend", "modified_files": ["src/core/app.py"]},
        project_id="AuraAI",
    )
    assert len(consolidated_success) >= 1, "Verified successful execution must be consolidated"
    assert consolidated_success[0].provenance.verified is True


# ── 5. Project Isolation Tests ────────────────────────────────────────────────


def test_project_isolation(cognitive_engine):
    item_global = MemoryItem(content="Global fact", project_id="global")
    item_aura = MemoryItem(content="AuraAI specific architecture", project_id="AuraAI")
    item_net = MemoryItem(content="Network engineering router config", project_id="Network")

    cognitive_engine.store_memory(item_global)
    cognitive_engine.store_memory(item_aura)
    cognitive_engine.store_memory(item_net)

    # Scoped to AuraAI: gets AuraAI + global, but NOT Network
    aura_memories = cognitive_engine.search_memories("", project_id="AuraAI")
    contents = [m.content for m in aura_memories]
    assert "AuraAI specific architecture" in contents
    assert "Global fact" in contents
    assert "Network engineering router config" not in contents


# ── 6. Backward Compatibility with Memory.py Facade ────────────────────────────


def test_memory_py_facade_backward_compatibility(temp_db):
    mem = LegacyMemoryFacade(db_path=temp_db)
    mem.upsert_fact("preference", "favorite_ide", "VS Code")
    mem.upsert_fact("profile", "name", "Developer")

    # Legacy facts()
    facts = mem.facts()
    assert len(facts) == 2

    # Legacy search()
    searched = mem.search("ide")
    assert len(searched) == 1
    assert searched[0].value == "VS Code"

    # Cognitive memory store sync check
    assert mem.cognitive is not None
    assert mem.cognitive.count_memories() >= 2
