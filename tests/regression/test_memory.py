"""
Regression tests for Memory subsystem.

These tests ensure that Memory subsystem behavior doesn't break during refactors.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


class TestMemoryRegression:
    """Test suite for Memory subsystem regression prevention."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_memory.db"
        chat_log = Path(temp_dir) / "test_chat_log.json"

        yield db_path, chat_log

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def memory(self, temp_db):
        """Create a Memory instance for testing."""
        from Memory import Memory

        db_path, chat_log = temp_db
        return Memory(db_path=str(db_path), chat_log_path=str(chat_log))

    def test_memory_initialization(self, memory):
        """Verify Memory initializes correctly with schema."""
        assert memory.db_path is not None
        assert memory.db_path.exists()

    def test_facts_persistence_across_sessions(self, temp_db):
        """Verify facts persist across multiple sessions."""
        from Memory import Memory

        db_path, chat_log = temp_db
        m1 = Memory(db_path=str(db_path), chat_log_path=str(chat_log))
        m1.upsert_fact("profile", "favorite_color", "blue")
        m1.upsert_fact("preference", "editor", "vscode")

        # Create new instance pointing at same db
        m2 = Memory(db_path=str(db_path), chat_log_path=str(chat_log))
        facts = m2.facts()

        assert len(facts) >= 2
        assert any(f.key == "favorite_color" and f.value == "blue" for f in facts)
        assert any(f.key == "editor" and f.value == "vscode" for f in facts)

    def test_conversation_persistence(self, temp_db):
        """Verify conversation turns persist across sessions."""
        from Memory import Memory

        db_path, chat_log = temp_db
        m1 = Memory(db_path=str(db_path), chat_log_path=str(chat_log))
        m1.record_turn("user question", "assistant answer", topic="test_topic")

        # Create new instance
        m2 = Memory(db_path=str(db_path), chat_log_path=str(chat_log))
        recent = m2.recent_messages(limit=5)
        assert len(recent) >= 2

    def test_build_context_includes_all_components(self, memory):
        """Verify build_context includes all expected components."""
        memory.upsert_fact("preference", "theme", "dark")
        memory.record_turn("user message", "bot response", topic="test_topic")

        context = memory.build_context(user_input="Hello", current_topic="test_topic")
        assert isinstance(context, str)
        assert len(context) > 0

    def test_chat_log_persists(self, memory):
        """Verify chat log is properly persisted."""
        memory.remember_exchange(
            query="What is 2+2?", answer="2+2 equals 4", topic="math"
        )

        assert memory.chat_log_path.exists()
        with open(memory.chat_log_path, encoding="utf-8") as f:
            chat_log = json.load(f)

        assert isinstance(chat_log, list)
        assert len(chat_log) >= 2
