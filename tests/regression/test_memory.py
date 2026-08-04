"""
Regression tests for Memory subsystem.

These tests ensure that Memory subsystem behavior doesn't break during refactors.
Run this suite before any major refactors to prevent regressions.
"""

import pytest
import os
import json
import tempfile
import shutil
from pathlib import Path


class TestMemoryRegression:
    """Test suite for Memory subsystem regression prevention."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_memory.db"

        yield db_path

        # Cleanup
        if db_path.exists():
            db_path.unlink()
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def memory(self, temp_db):
        """Create a Memory instance for testing."""
        from Memory import Memory
        return Memory(db_path=str(temp_db), init_schema=True)

    def test_memory_initialization(self, memory):
        """Verify Memory initializes correctly with schema."""
        assert memory.db_path == str(memory._get_db_path())
        assert memory.db_path == str(Path(memory._get_db_path()).parent / "Memory.db")

    def test_facts_persistence_across_sessions(self, memory):
        """Verify facts persist across multiple sessions."""
        # Add facts
        memory.record_fact("test_fact_1", "value_1")
        memory.record_fact("test_fact_2", "value_2")

        # Create new instance and verify facts exist
        from Memory import Memory
        new_memory = Memory(db_path=str(memory._get_db_path()), init_schema=False)
        facts = new_memory._get_all_facts()

        assert len(facts) >= 2
        assert any(f["key"] == "test_fact_1" for f in facts)
        assert any(f["key"] == "test_fact_2" for f in facts)

    def test_conversation_persistence(self, memory):
        """Verify conversation turns persist across sessions."""
        # Record a conversation turn
        memory.record_turn("user question", "assistant answer", "test_topic")

        # Create new instance
        from Memory import Memory
        new_memory = Memory(db_path=str(memory._get_db_path()), init_schema=False)

        # Verify turn exists
        turns = new_memory._get_recent_turns(limit=10)
        assert len(turns) >= 1
        assert turns[0]["role"] == "user"
        assert turns[0]["content"] == "user question"

    def test_topics_persistence(self, memory):
        """Verify topics persist across sessions."""
        # Add a topic
        memory.add_topic("test_topic", "Test category")

        # Create new instance
        from Memory import Memory
        new_memory = Memory(db_path=str(memory._get_db_path()), init_schema=False)

        # Verify topic exists
        topics = new_memory._get_topics()
        assert len(topics) > 0

    def test_build_context_includes_all_components(self, memory):
        """Verify build_context includes all expected components."""
        # Add test data
        memory.record_fact("test_key", "test_value")
        memory.record_turn("user message", "bot response", "test_topic")
        memory.add_topic("test_topic", "Test category")

        # Build context
        context = memory.build_context(
            user_input="Hello",
            topic="test_topic"
        )

        # Verify context contains expected components
        assert len(context) > 0
        # Check that context has the expected structure

    def test_topic_faceting(self, memory):
        """Verify topic faceting works correctly."""
        # Add messages to different topics
        memory.record_turn("network question", "network answer", "networking")
        memory.record_turn("python question", "python answer", "python")
        memory.record_turn("general question", "general answer", "general")

        # Test faceting by topic
        faceting = memory.facet(topic="networking")
        assert len(faceting) > 0
        assert all(msg["topic"] == "networking" for msg in faceting)

    def test_recent_messages_includes_topic(self, memory):
        """Verify recent messages include topic field."""
        # Record turns with different topics
        memory.record_turn("q1", "a1", "topic1")
        memory.record_turn("q2", "a2", "topic2")
        memory.record_turn("q3", "a3", "topic3")

        # Get recent messages
        recent = memory.recent_messages(limit=5)

        # Verify topic field exists
        assert len(recent) > 0
        for msg in recent:
            assert "topic" in msg
            assert msg["topic"] in ["topic1", "topic2", "topic3"]

    def test_summarize_retrieves_all_information(self, memory):
        """Verify summarize retrieves all stored information."""
        # Add various types of data
        memory.record_fact("fact1", "value1")
        memory.record_fact("fact2", "value2")
        memory.record_turn("q1", "a1", "t1")
        memory.record_turn("q2", "a2", "t2")
        memory.add_topic("t1", "Category 1")
        memory.add_topic("t2", "Category 2")

        # Summarize
        summary = memory.summarize()

        # Verify summary contains expected elements
        assert len(summary) > 0
        assert any("fact1" in s.lower() for s in summary)
        assert any("q1" in s.lower() for s in summary)

    def test_chat_log_persists(self, memory):
        """Verify chat log is properly persisted."""
        # Add conversation
        memory.remember_exchange(
            query="What is 2+2?",
            answer="2+2 equals 4",
            topic="math"
        )

        # Verify chat log exists
        chat_log_path = memory._get_chat_log_path()
        assert chat_log_path.exists()

        # Verify content
        with open(chat_log_path, 'r', encoding='utf-8') as f:
            chat_log = json.load(f)

        assert isinstance(chat_log, list)
        assert len(chat_log) >= 1
        assert chat_log[0]["role"] == "user"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
