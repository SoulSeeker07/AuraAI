"""
Unit tests for Memory.py chat log operations and dynamic attribute resolution.
Location: tests/unit/test_memory_chat_log.py
"""

import json
import pytest
from pathlib import Path
from Memory import Memory, MemoryFact


@pytest.fixture
def memory_fixture(tmp_path):
    db_path = tmp_path / "test_memory.db"
    chat_log = tmp_path / "Data" / "ChatLog.json"
    return Memory(db_path=str(db_path), chat_log_path=str(chat_log))


def test_recent_messages_empty_when_file_missing(tmp_path):
    db_path = tmp_path / "db.sqlite"
    missing_chat_log = tmp_path / "non_existent" / "ChatLog.json"
    mem = Memory(db_path=str(db_path), chat_log_path=str(missing_chat_log))

    assert mem.recent_messages(limit=10) == []


def test_add_and_retrieve_recent_messages(memory_fixture):
    memory_fixture.add_message("user", "Hello Aura")
    memory_fixture.add_message("assistant", "Hello! How can I help you today?")
    memory_fixture.add_message("user", "Open calculator")

    msgs = memory_fixture.recent_messages(limit=2)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["content"] == "Hello! How can I help you today?"
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "Open calculator"
    assert "timestamp" in msgs[0]


def test_recent_messages_corrupt_json_resilience(tmp_path):
    db_path = tmp_path / "db.sqlite"
    chat_log = tmp_path / "ChatLog.json"
    chat_log.write_text("{not valid json: [", encoding="utf-8")

    mem = Memory(db_path=str(db_path), chat_log_path=str(chat_log))
    assert mem.recent_messages(limit=5) == []

    # Writing after corrupt JSON safely resets/appends
    mem.add_message("user", "Recovered query")
    msgs = mem.recent_messages(limit=5)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Recovered query"


def test_build_context_includes_recent_messages_and_facts(memory_fixture):
    memory_fixture.upsert_fact("preference", "theme", "dark")
    memory_fixture.add_message("user", "My favorite editor is VS Code")
    memory_fixture.add_message("assistant", "Noted that your favorite editor is VS Code.")

    ctx = memory_fixture.build_context(user_input="What theme do I like?")
    assert "Recent Conversation:" in ctx
    assert "USER: My favorite editor is VS Code" in ctx
    assert "Preference:" in ctx or "theme" in ctx


def test_memory_dynamic_getattr_and_setattr(memory_fixture):
    # Dynamic preference set via __setattr__
    memory_fixture.editor = "VS Code"

    # Dynamic preference retrieval via __getattr__
    assert memory_fixture.editor == "VS Code"

    # Nonexistent attribute raises AttributeError after checking categories
    with pytest.raises(AttributeError) as exc_info:
        _ = memory_fixture.non_existent_attribute_xyz
    assert "non_existent_attribute_xyz" in str(exc_info.value)
