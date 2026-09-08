"""
Unit and integration tests for AmbientContextBuilder Cognitive Memory 2.0 wiring.
Location: tests/core/test_ambient_context_cognitive_memory.py
"""

from unittest.mock import MagicMock
import pytest

from core.context.ambient_context_builder import AmbientContextBuilder
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource
from tests.memory.test_context_builder_gated_memory import MockCognitiveEngine


def test_ambient_context_injects_cognitive_memory():
    """AmbientContextBuilder must surface gated cognitive memory into ambient info."""
    mem = MemoryItem(
        content="User's favorite code editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=1.0,
        provenance=MemoryProvenance(source_type=ProvenanceSource.USER_EXPLICIT),
    )
    fake_engine = MockCognitiveEngine([mem])

    mock_core = MagicMock()
    mock_core.memory = MagicMock()
    mock_core.memory.cognitive = fake_engine
    mock_core.embedding_warmup = None
    mock_core.speculative_indexer = None

    context_str = AmbientContextBuilder.build_ambient_context(mock_core, query="What is my favorite editor?")
    assert "Relevant User Facts & Preferences" in context_str
    assert "VS Code" in context_str


def test_ambient_context_skips_generic_query():
    """AmbientContextBuilder must NOT inject preference memories for generic queries."""
    mem = MemoryItem(
        content="User's favorite code editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=1.0,
    )
    fake_engine = MockCognitiveEngine([mem])

    mock_core = MagicMock()
    mock_core.memory = MagicMock()
    mock_core.memory.cognitive = fake_engine
    mock_core.memory.get_relevant_facts.return_value = []
    mock_core.memory.all_facts.return_value = []
    mock_core.memory.facts.return_value = []
    mock_core.embedding_warmup = None
    mock_core.speculative_indexer = None

    context_str = AmbientContextBuilder.build_ambient_context(mock_core, query="What is the capital of France?")
    assert "VS Code" not in context_str
    assert "Relevant User Facts & Preferences" not in context_str


def test_ambient_context_fails_closed_on_error():
    """Exceptions in cognitive memory gate must fail-closed cleanly."""
    mock_core = MagicMock()
    bad_cognitive = MagicMock()
    bad_cognitive.get_retrieval_gate.side_effect = RuntimeError("DB locked")
    mock_core.memory.cognitive = bad_cognitive
    mock_core.memory.get_relevant_facts.return_value = []
    mock_core.memory.all_facts.return_value = []
    mock_core.embedding_warmup = None
    mock_core.speculative_indexer = None

    context_str = AmbientContextBuilder.build_ambient_context(mock_core, query="What is my favorite editor?")
    assert "Current System Time" in context_str
    assert "Relevant User Facts & Preferences" not in context_str


def test_ambient_context_falls_back_to_legacy_on_cognitive_exception():
    """When cognitive memory encounters an unhandled exception, it must fall back to legacy facts as a degraded floor."""
    mock_core = MagicMock()
    bad_cognitive = MagicMock()
    bad_cognitive.get_retrieval_gate.side_effect = RuntimeError("DB locked / transient error")
    mock_core.memory.cognitive = bad_cognitive

    legacy_fact = MagicMock()
    legacy_fact.category = "preferences"
    legacy_fact.key = "editor"
    legacy_fact.value = "VS Code (Degraded Legacy Fallback)"

    mock_core.memory.get_relevant_facts.return_value = [legacy_fact]
    mock_core.memory.all_facts.return_value = [legacy_fact]
    mock_core.embedding_warmup = None
    mock_core.speculative_indexer = None

    context_str = AmbientContextBuilder.build_ambient_context(mock_core, query="What is my favorite editor?")

    # Assert legacy fallback was called and injected
    mock_core.memory.get_relevant_facts.assert_called_once_with("What is my favorite editor?", limit=10)
    assert "Relevant User Facts & Preferences" in context_str
    assert "VS Code (Degraded Legacy Fallback)" in context_str


def test_transient_recall_relevance_does_not_pollute_metadata():
    """Verify that score_and_rank sets _recall_relevance as an attribute, not in metadata dict."""
    from memory.recall_engine import RecallEngine
    re = RecallEngine()
    item = MemoryItem(
        content="User prefers dark mode",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        metadata={"user_tag": "ui_setting"}
    )
    scored = re.score_and_rank("dark mode", [item])
    assert len(scored) == 1
    score, res_item = scored[0]

    # Must be accessible via attribute
    assert hasattr(res_item, "_recall_relevance")
    assert getattr(res_item, "_recall_relevance") > 0.0

    # Must NOT pollute metadata dict
    assert "_recall_relevance" not in res_item.metadata
    assert res_item.metadata == {"user_tag": "ui_setting"}


def test_auracore_build_chat_messages_surfaces_cognitive_memory():
    """AuraCore._build_chat_messages must include recalled cognitive memories in the system prompt."""
    from core.aura_core import AuraCore

    mem = MemoryItem(
        content="User's favorite code editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=1.0,
        provenance=MemoryProvenance(source_type=ProvenanceSource.USER_EXPLICIT),
    )
    fake_engine = MockCognitiveEngine([mem])

    mock_core = MagicMock(spec=AuraCore)
    mock_core.memory = MagicMock()
    mock_core.memory.cognitive = fake_engine
    mock_core.embedding_warmup = None
    mock_core.speculative_indexer = None
    mock_core.conversation_history = []

    # Call unbound _build_chat_messages method directly on mock_core
    messages = AuraCore._build_chat_messages(mock_core, user_message="What is my favorite editor?")
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert "User's favorite code editor is VS Code" in messages[0]["content"]
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "What is my favorite editor?"


def test_ambient_context_no_duplicate_facts_when_both_paths_available():
    """When cognitive memory surfaces relevant facts, legacy facts must NOT be duplicated or appended."""
    mem = MemoryItem(
        content="User's favorite code editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=1.0,
        provenance=MemoryProvenance(source_type=ProvenanceSource.USER_EXPLICIT),
    )
    fake_engine = MockCognitiveEngine([mem])

    legacy_fact = MagicMock()
    legacy_fact.category = "preferences"
    legacy_fact.key = "editor"
    legacy_fact.value = "VS Code (Legacy KV)"

    mock_core = MagicMock()
    mock_core.memory = MagicMock()
    mock_core.memory.cognitive = fake_engine
    mock_core.memory.get_relevant_facts.return_value = [legacy_fact]
    mock_core.memory.all_facts.return_value = [legacy_fact]
    mock_core.embedding_warmup = None
    mock_core.speculative_indexer = None

    context_str = AmbientContextBuilder.build_ambient_context(mock_core, query="What is my favorite editor?")
    
    # Must contain the Cognitive Memory 2.0 fact
    assert "User's favorite code editor is VS Code" in context_str
    # Must NOT contain the legacy fact (fallback branch was cleanly bypassed)
    assert "VS Code (Legacy KV)" not in context_str
    # Exactly one User Facts section
    assert context_str.count("Relevant User Facts & Preferences") == 1


def test_memory_item_tolerates_dynamic_attributes():
    """Verify that MemoryItem is a standard unslotted dataclass with __dict__ that round-trips setattr."""
    item = MemoryItem(content="Test item", type=MemoryType.PREFERENCE)
    
    # Assert standard __dict__ exists (not slotted, not Pydantic extra='forbid')
    assert hasattr(item, "__dict__")
    
    # Set and get dynamic attribute
    setattr(item, "_recall_relevance", 0.8842)
    assert getattr(item, "_recall_relevance") == 0.8842
    assert item._recall_relevance == 0.8842
    
    # Assert metadata dict is separate and unpolluted
    assert "_recall_relevance" not in item.metadata


def test_ambient_context_cognitive_rejection_is_authoritative():
    """When cognitive memory rejects a query as generic/irrelevant, legacy fallback must NOT fire."""
    mem = MemoryItem(
        content="User's favorite code editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
    )
    fake_engine = MockCognitiveEngine([mem])

    legacy_fact = MagicMock()
    legacy_fact.category = "tech"
    legacy_fact.key = "language"
    legacy_fact.value = "Python"

    mock_core = MagicMock()
    mock_core.memory = MagicMock()
    mock_core.memory.cognitive = fake_engine
    # Even if legacy facts table has facts, it should NOT be queried when cognitive engine rejected the query
    mock_core.memory.get_relevant_facts.return_value = [legacy_fact]
    mock_core.memory.all_facts.return_value = [legacy_fact]
    mock_core.embedding_warmup = None
    mock_core.speculative_indexer = None

    context_str = AmbientContextBuilder.build_ambient_context(mock_core, query="What is the capital of France?")
    
    # Assert neither cognitive nor legacy facts are injected
    assert "Relevant User Facts & Preferences" not in context_str
    assert "Python" not in context_str
    assert "VS Code" not in context_str
    mock_core.memory.get_relevant_facts.assert_not_called()



