"""
Tests for LongTermMemory — updated for M2 API.

M2 changes from M1:
- extract_and_store() renamed to extract_candidates() (LLM produces candidates only)
- store() is now public (called by MemoryManager._consolidate after policy gate)
- The old test called extract_and_store() and expected chroma writes inside it.
  Now: extract_candidates() only returns candidates; chroma writes are separate.
"""
import pytest
import sys
from unittest.mock import MagicMock, patch

# Mock heavy ML dependencies before importing the module to test
sys.modules['chromadb'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()

from memory.manager.long_term_memory import LongTermMemory


@pytest.fixture
def mock_provider_manager():
    manager = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '[{"fact": "User loves Python", "topic": "preferences", "importance": 4}]'
    manager.chat.return_value = mock_resp
    return manager


@patch("memory.manager.long_term_memory.chromadb")
@patch("memory.manager.long_term_memory.SentenceTransformer")
def test_extract_candidates_returns_list(mock_sentence_transformer, mock_chromadb, mock_provider_manager):
    """extract_candidates() returns candidate list — does NOT write to Chroma."""
    mock_embedder = MagicMock()
    mock_encode_result = MagicMock()
    mock_encode_result.tolist.return_value = [0.1, 0.2, 0.3]
    mock_embedder.encode.return_value = mock_encode_result
    mock_sentence_transformer.return_value = mock_embedder

    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb.PersistentClient.return_value = mock_client

    ltm = LongTermMemory(provider_manager=mock_provider_manager)

    # M2: accepts a full transcript string, not separate user/assistant args
    candidates = ltm.extract_candidates("user: I love Python\nassistant: That's great to know!")

    assert len(candidates) == 1
    assert candidates[0]["fact"] == "User loves Python"

    # Chroma must NOT be written by extract_candidates — only by store()
    mock_collection.add.assert_not_called()

    # LLM was called exactly once (primary model succeeded)
    mock_provider_manager.chat.assert_called_once()


@patch("memory.manager.long_term_memory.chromadb")
@patch("memory.manager.long_term_memory.SentenceTransformer")
def test_store_writes_to_chroma(mock_sentence_transformer, mock_chromadb, mock_provider_manager):
    """store() writes the approved fact to Chroma."""
    mock_embedder = MagicMock()
    mock_encode_result = MagicMock()
    mock_encode_result.tolist.return_value = [0.1, 0.2, 0.3]
    mock_embedder.encode.return_value = mock_encode_result
    mock_sentence_transformer.return_value = mock_embedder

    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb.PersistentClient.return_value = mock_client

    ltm = LongTermMemory(provider_manager=mock_provider_manager)
    ltm.collection = mock_collection

    ltm.store(fact="User loves Python", topic="preferences", importance=4)

    mock_collection.add.assert_called_once()
    call_kwargs = mock_collection.add.call_args.kwargs
    assert call_kwargs["documents"] == ["User loves Python"]
    assert call_kwargs["metadatas"][0]["topic"] == "preferences"
    assert call_kwargs["metadatas"][0]["importance"] == 4
