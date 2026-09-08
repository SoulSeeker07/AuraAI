"""
Unit tests for Hybrid Semantic Recall Engine and Pre-caching in Cognitive Memory.
Location: tests/unit/test_semantic_recall_engine.py
"""

import sqlite3
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from memory.cognitive_memory import CognitiveMemoryEngine
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource
from memory.recall_engine import RecallEngine, SEMANTIC_WEIGHT, LEXICAL_WEIGHT


def test_recall_engine_constants():
    """Verify semantic and lexical split constants."""
    assert SEMANTIC_WEIGHT == 0.70
    assert LEXICAL_WEIGHT == 0.30
    engine = RecallEngine()
    assert engine.semantic_weight == 0.70
    assert engine.lexical_weight == 0.30


def test_hybrid_scoring_surfaces_semantic_match_without_keyword_overlap():
    """Neovim memory must match 'Where do I program?' via vector similarity without lexical overlap."""
    engine = RecallEngine()

    # Create dummy 384-dim normalized vectors
    vec_dim = 384
    q_vec = np.zeros(vec_dim, dtype=np.float32)
    q_vec[0] = 1.0  # Unit vector for query

    mem_rel_vec = np.zeros(vec_dim, dtype=np.float32)
    mem_rel_vec[0] = 0.8
    mem_rel_vec[1] = 0.6  # Unit vector with dot product 0.8 with q_vec

    mem_unrel_vec = np.zeros(vec_dim, dtype=np.float32)
    mem_unrel_vec[2] = 1.0  # Dot product 0.0 with q_vec

    mem_rel = MemoryItem(
        content="User writes software using Neovim",
        type=MemoryType.PREFERENCE,
        importance=0.8,
        embedding=mem_rel_vec.tobytes(),
    )
    mem_unrel = MemoryItem(
        content="User likes chocolate cake",
        type=MemoryType.PREFERENCE,
        importance=0.8,
        embedding=mem_unrel_vec.tobytes(),
    )

    with patch("memory.vector_memory.VectorMemoryEngine.get_instance") as mock_vec_inst:
        mock_engine = MagicMock()
        mock_engine.encode.return_value = q_vec
        mock_vec_inst.return_value = mock_engine

        # Query has 0 keyword overlap with 'User writes software using Neovim'
        scored = engine.score_and_rank("Where do I program?", [mem_unrel, mem_rel])
        assert len(scored) == 2
        top_score, top_item = scored[0]

        # Semantic match must be ranked #1
        assert top_item.content == "User writes software using Neovim"
        # Hybrid relevance: 0.7 * 0.8 + 0.3 * 0.0 = 0.56
        assert hasattr(top_item, "_recall_relevance")
        assert top_item._recall_relevance == pytest.approx(0.56, abs=0.01)


def test_no_inline_embedding_computation_during_recall():
    """RecallEngine must only encode the query once and NEVER encode candidate memories inline."""
    engine = RecallEngine()

    mem1 = MemoryItem(content="Item 1", type=MemoryType.PREFERENCE, embedding=None)
    mem2 = MemoryItem(content="Item 2", type=MemoryType.PREFERENCE, embedding=None)
    mem3 = MemoryItem(content="Item 3", type=MemoryType.PREFERENCE, embedding=None)

    with patch("memory.vector_memory.VectorMemoryEngine.get_instance") as mock_vec_inst:
        mock_engine = MagicMock()
        mock_engine.encode.return_value = np.ones(384, dtype=np.float32)
        mock_vec_inst.return_value = mock_engine

        engine.score_and_rank("test search query", [mem1, mem2, mem3])

        # Query encoded exactly once
        assert mock_engine.encode.call_count == 1
        mock_engine.encode.assert_called_once_with("test search query")


def test_graceful_lexical_fallback_when_embeddings_absent():
    """When items have embedding=None, RecallEngine safely scores pure lexical."""
    engine = RecallEngine()
    item = MemoryItem(content="User prefers dark mode", type=MemoryType.PREFERENCE, embedding=None)

    with patch("memory.vector_memory.VectorMemoryEngine.get_instance") as mock_vec_inst:
        mock_engine = MagicMock()
        mock_engine.encode.return_value = None  # Model unavailable
        mock_vec_inst.return_value = mock_engine

        scored = engine.score_and_rank("dark mode", [item])
        assert len(scored) == 1
        assert scored[0][1]._recall_relevance == 1.0


def test_stopword_query_skips_vector_encoding():
    """Queries consisting purely of stopwords must not invoke vector encoding."""
    engine = RecallEngine()
    item = MemoryItem(content="Test content", type=MemoryType.PREFERENCE)

    with patch("memory.vector_memory.VectorMemoryEngine.get_instance") as mock_vec_inst:
        mock_engine = MagicMock()
        mock_vec_inst.return_value = mock_engine

        scored = engine.score_and_rank("what is that", [item])
        mock_engine.encode.assert_not_called()
        assert scored[0][1]._recall_relevance == 0.0


def test_cognitive_memory_pre_caches_and_persists_embedding(tmp_path):
    """store_memory must pre-cache vector embedding on write and persist it to SQLite."""
    db_file = tmp_path / "test_cog.db"
    dummy_vec = np.linspace(0.1, 0.9, 384, dtype=np.float32)

    with patch("memory.vector_memory.VectorMemoryEngine.get_instance") as mock_vec_inst:
        mock_engine = MagicMock()
        mock_engine.encode.return_value = dummy_vec
        mock_vec_inst.return_value = mock_engine

        cog = CognitiveMemoryEngine(db_path=db_file)
        item = MemoryItem(
            content="Preferred font is Fira Code",
            type=MemoryType.PREFERENCE,
            importance=0.9,
        )

        stored = cog.store_memory(item)
        assert stored.embedding is not None
        assert isinstance(stored.embedding, bytes)
        assert len(stored.embedding) == 384 * 4  # 384 float32 values

        # Verify SQLite schema has embedding column populated
        with sqlite3.connect(db_file) as conn:
            row = conn.execute("SELECT embedding FROM cognitive_memories WHERE memory_id = ?", (stored.memory_id,)).fetchone()
            assert row is not None
            assert row[0] is not None
            unpacked = np.frombuffer(row[0], dtype=np.float32)
            np.testing.assert_allclose(unpacked, dummy_vec, rtol=1e-5)

        # Retrieve via get_memory and search_memories
        retrieved = cog.get_memory(stored.memory_id)
        assert retrieved is not None
        assert retrieved.embedding == stored.embedding

        search_res = cog.search_memories("font")
        assert len(search_res) == 1
        assert search_res[0].embedding == stored.embedding


def test_repeated_init_db_does_not_throw(tmp_path):
    """Multiple CognitiveMemoryEngine initializations on the same DB must succeed without OperationalError."""
    db_file = tmp_path / "repeated_init.db"
    cog1 = CognitiveMemoryEngine(db_path=db_file)
    # Second init on same DB file must succeed cleanly
    cog2 = CognitiveMemoryEngine(db_path=db_file)
    assert cog2.count_memories() == 0


def test_row_to_memory_item_supports_row_and_tuple(tmp_path):
    """_row_to_memory_item must cleanly deserialize both sqlite3.Row mappings and legacy raw tuples."""
    db_file = tmp_path / "row_test.db"
    cog = CognitiveMemoryEngine(db_path=db_file)

    # 1. From real sqlite3.Row via get_memory
    item = MemoryItem(content="Test item", type=MemoryType.PREFERENCE)
    cog.store_memory(item)
    with cog._connect() as conn:
        row = conn.execute("SELECT * FROM cognitive_memories WHERE memory_id = ?", (item.memory_id,)).fetchone()
        assert hasattr(row, "keys")
        deserialized = cog._row_to_memory_item(row)
        assert deserialized.memory_id == item.memory_id
        assert deserialized.content == "Test item"

    # 2. From raw tuple (mocked or legacy caller)
    raw_tuple = (
        "mem_123", "preference", "Tuple content", "{}", "2026-09-08T00:00:00",
        "2026-09-08T00:00:00", 0.8, 1.0, "global", "general", 0, "2026-09-08T00:00:00",
        None, "{}", None
    )
    from_tuple = cog._row_to_memory_item(raw_tuple)
    assert from_tuple.memory_id == "mem_123"
    assert from_tuple.content == "Tuple content"

