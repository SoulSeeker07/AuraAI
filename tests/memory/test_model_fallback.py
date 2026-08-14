"""
Test: LongTermMemory model fallback chain.
Primary model failure → fallback 1 tried.
Fallback 1 failure → fallback 2 tried.
All fail → [] returned, no exception.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from memory.manager.long_term_memory import LongTermMemory


def _make_ltm():
    pm = MagicMock()
    with patch("memory.manager.long_term_memory.SentenceTransformer"), \
         patch("memory.manager.long_term_memory.chromadb.PersistentClient"):
        ltm = LongTermMemory(provider_manager=pm)
    ltm.provider_manager = pm
    return ltm


def test_primary_model_succeeds_no_fallback():
    ltm = _make_ltm()
    mock_resp = MagicMock()
    mock_resp.text = '[{"fact": "User likes Firefox", "topic": "prefs", "importance": 4}]'
    ltm.provider_manager.chat.return_value = mock_resp

    result = ltm.extract_candidates("user: I like Firefox\nassistant: Noted.")

    assert len(result) == 1
    assert result[0]["fact"] == "User likes Firefox"
    # Only one chat call — primary model succeeded
    assert ltm.provider_manager.chat.call_count == 1


def test_primary_fails_fallback1_succeeds():
    ltm = _make_ltm()

    mock_resp = MagicMock()
    mock_resp.text = '[{"fact": "User uses VS Code", "topic": "tools", "importance": 4}]'

    call_count = [0]
    def side_effect(req):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("primary model down")
        return mock_resp

    ltm.provider_manager.chat.side_effect = side_effect

    result = ltm.extract_candidates("user: I use VS Code\nassistant: Got it.")
    assert len(result) == 1
    assert ltm.provider_manager.chat.call_count == 2  # primary failed, fallback succeeded


def test_all_models_fail_returns_empty_list():
    ltm = _make_ltm()
    ltm.provider_manager.chat.side_effect = RuntimeError("all models down")

    # Must NOT raise
    result = ltm.extract_candidates("user: Hello\nassistant: Hi.")
    assert result == []
    # All three models attempted
    assert ltm.provider_manager.chat.call_count == 3


def test_unparseable_json_triggers_next_model():
    """If one model returns unparseable JSON, try the next model."""
    ltm = _make_ltm()

    mock_bad = MagicMock()
    mock_bad.text = "This is not JSON at all"

    mock_good = MagicMock()
    mock_good.text = '[{"fact": "User prefers Linux", "topic": "os", "importance": 4}]'

    responses = [mock_bad, mock_good]
    call_count = [0]

    def side_effect(req):
        resp = responses[min(call_count[0], len(responses) - 1)]
        call_count[0] += 1
        return resp

    ltm.provider_manager.chat.side_effect = side_effect

    result = ltm.extract_candidates("user: I use Linux\nassistant: Noted.")
    assert len(result) == 1
    assert result[0]["fact"] == "User prefers Linux"
