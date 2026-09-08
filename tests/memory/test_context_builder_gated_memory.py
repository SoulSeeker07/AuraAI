"""
Unit and integration tests for Gated Cognitive Memory wiring into ContextBuilder.
Location: tests/memory/test_context_builder_gated_memory.py
"""

import pytest
from unittest.mock import MagicMock

from brain.context_builder import ContextBuilder
from brain.models import Intent
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource
from tests.memory.test_retrieval_gate import FakeCognitiveEngineWithRecall


class MockCognitiveEngine(FakeCognitiveEngineWithRecall):
    def __init__(self, memories: list[MemoryItem] | None = None):
        super().__init__(memories)
        self._retrieval_gate = None

    def get_retrieval_gate(self):
        if self._retrieval_gate is None:
            from memory.retrieval_gate import MemoryRetrievalGate
            self._retrieval_gate = MemoryRetrievalGate(self)
        return self._retrieval_gate


@pytest.fixture(autouse=True)
def mock_rag_service(monkeypatch):
    mock_rag = MagicMock()
    mock_rag.get_relevant_context.return_value = ""
    monkeypatch.setattr("knowledge.rag_service.RAGService.get_instance", lambda: mock_rag)


def _make_context_builder_with_engine(items: list[MemoryItem]) -> ContextBuilder:
    fake_cognitive = MockCognitiveEngine(items)

    mock_memory = MagicMock()
    mock_memory.get_context.return_value = ""
    mock_memory.recent_messages.return_value = []
    mock_memory.cognitive = fake_cognitive

    return ContextBuilder(memory=mock_memory)


def test_context_builder_injects_recalled_cognitive_memory():
    """Relevant query must inject gated memory prompt fragment."""
    mem = MemoryItem(
        content="User's favorite code editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=1.0,
        provenance=MemoryProvenance(source_type=ProvenanceSource.USER_EXPLICIT),
    )
    cb = _make_context_builder_with_engine([mem])

    ctx = cb.build("What is my favorite editor?", intent=Intent("provider_chat"))
    sys_messages = [m.content for m in ctx.messages if m.role == "system"]

    recalled_block = next((m for m in sys_messages if "Recalled Contextual Memory" in m), None)
    assert recalled_block is not None
    assert "VS Code" in recalled_block


def test_context_builder_skips_generic_query():
    """Generic query must NOT inject any memory fragment."""
    mem = MemoryItem(
        content="User's favorite code editor is VS Code",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=1.0,
    )
    cb = _make_context_builder_with_engine([mem])

    ctx = cb.build("What is the capital of France?", intent=Intent("provider_chat"))
    sys_messages = [m.content for m in ctx.messages if m.role == "system"]

    recalled_block = next((m for m in sys_messages if "Recalled Contextual Memory" in m), None)
    assert recalled_block is None


def test_context_builder_skips_conversational_filler_words():
    """'like' in conversational context must not trigger preferences."""
    mem = MemoryItem(
        content="User prefers dark mode",
        type=MemoryType.PREFERENCE,
        importance=0.9,
        confidence=1.0,
    )
    cb = _make_context_builder_with_engine([mem])

    ctx = cb.build("I would like you to explain quicksort", intent=Intent("provider_chat"))
    sys_messages = [m.content for m in ctx.messages if m.role == "system"]

    recalled_block = next((m for m in sys_messages if "Recalled Contextual Memory" in m), None)
    assert recalled_block is None


def test_context_builder_fails_closed_on_error():
    """Exceptions during memory recall must fail-closed without crashing prompt construction."""
    mock_memory = MagicMock()
    mock_memory.get_context.return_value = ""
    mock_memory.recent_messages.return_value = []

    bad_cognitive = MagicMock()
    bad_cognitive.get_retrieval_gate.side_effect = RuntimeError("DB failure")
    mock_memory.cognitive = bad_cognitive

    cb = ContextBuilder(memory=mock_memory)
    ctx = cb.build("What is my favorite editor?", intent=Intent("provider_chat"))

    # Must complete cleanly with user input preserved
    assert ctx.user_input == "What is my favorite editor?"
    sys_messages = [m.content for m in ctx.messages if m.role == "system"]
    recalled_block = next((m for m in sys_messages if "Recalled Contextual Memory" in m), None)
    assert recalled_block is None
