"""
Regression tests for Context subsystem.

These tests ensure that Context building and management doesn't break during refactors.
Run this suite before any major refactors to prevent regressions.
"""

import pytest
from core.memory.memory_manager import MemoryManager


class TestContextRegression:
    """Test suite for Context subsystem regression prevention."""

    @pytest.fixture
    def memory_manager(self):
        """Create a MemoryManager instance for testing."""
        from core.memory.memory_manager import MemoryManager
        from core.memory.memory import Memory

        # Create a temporary memory instance
        temp_db = "test_context_memory.db"
        memory = Memory(db_path=temp_db, init_schema=True)

        return MemoryManager(memory=memory)

    def test_context_building_includes_conversation(self, memory_manager):
        """Verify context includes conversation history."""
        # Add conversation
        memory_manager.remember_exchange(
            query="Hello",
            answer="Hi there!",
            topic="general"
        )
        memory_manager.remember_exchange(
            query="How are you?",
            answer="I'm doing great!",
            topic="general"
        )

        # Build context
        context = memory_manager.build_context(
            user_input="What was our first conversation?",
            topic="general"
        )

        # Verify context contains conversation
        context_str = " ".join(context)
        assert "Hello" in context_str or "Hi there" in context_str

    def test_context_building_includes_facts(self, memory_manager):
        """Verify context includes stored facts."""
        # Add facts
        memory_manager.remember_fact("name", "Sreekanta")
        memory_manager.remember_fact("role", "Developer")

        # Build context
        context = memory_manager.build_context(
            user_input="Who are you?",
            topic="personal"
        )

        # Verify context contains facts
        context_str = " ".join(context)
        assert "Sreekanta" in context_str or "Developer" in context_str

    def test_context_building_includes_topic(self, memory_manager):
        """Verify context includes current topic."""
        # Build context with specific topic
        context = memory_manager.build_context(
            user_input="Tell me about Python",
            topic="python"
        )

        # Verify context contains topic information
        context_str = " ".join(context)
        assert "python" in context_str.lower()

    def test_recent_messages_includes_topic_field(self, memory_manager):
        """Verify recent messages include topic field."""
        # Add conversation with different topics
        memory_manager.remember_exchange(
            query="Network question",
            answer="Network answer",
            topic="networking"
        )
        memory_manager.remember_exchange(
            query="Python question",
            answer="Python answer",
            topic="python"
        )

        # Get recent messages
        messages = memory_manager.get_recent_messages(limit=10)

        # Verify topic field exists
        assert len(messages) >= 2
        for msg in messages:
            assert "topic" in msg
            assert "role" in msg
            assert "content" in msg

    def test_context_size_limit(self, memory_manager):
        """Verify context respects size limits."""
        # Add many messages
        for i in range(20):
            memory_manager.remember_exchange(
                query=f"Question {i}",
                answer=f"Answer {i}",
                topic="general"
            )

        # Build context with limit
        context = memory_manager.build_context(
            user_input="Hello",
            topic="general"
        )

        # Verify context size is reasonable
        assert 100 >= len(context) >= 0

    def test_facts_are_not_halucinated(self, memory_manager):
        """Verify stored facts are retrieved accurately."""
        # Store a specific fact
        test_fact = "test_fact_key"
        test_value = "test_fact_value"
        memory_manager.remember_fact(test_fact, test_value)

        # Retrieve fact
        retrieved = memory_manager.get_fact(test_fact)

        # Verify accuracy
        assert retrieved == test_value

    def test_context_cleans_up_old_messages(self, memory_manager):
        """Verify old messages don't pollute context."""
        # Add many old messages
        for i in range(100):
            memory_manager.remember_exchange(
                query=f"Old question {i}",
                answer=f"Old answer {i}",
                topic="general"
            )

        # Build context with limit
        context = memory_manager.build_context(
            user_input="Current question",
            topic="general"
        )

        # Verify context is limited
        assert len(context) <= 200  # Reasonable limit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
