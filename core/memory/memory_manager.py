"""
Memory Manager

Manages memory operations for Aura.
Provides fact storage, retrieval, and context building.

This is a facade over Memory.py (SQLite backend).
Fact extraction and content-based operations are handled by Memory.py.
"""

from __future__ import annotations

import logging

# Import Memory.py (SQLite backend)
from Memory import Memory, MemoryFact

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Manages memory operations.

    This is a facade over Memory.py (SQLite backend).

    Responsibilities:
        - Store and retrieve memory facts
        - Build memory context
        - Handle conversation history
        - Build comprehensive context for LLM
    """

    def __init__(self, memory: Memory | None = None):
        """
        Initialize Memory Manager.

        Args:
            memory: Memory.py instance (SQLite backend)
                    If None, creates a new one with default paths
        """
        self.memory = memory or Memory()
        logger.info("Memory Manager initialized (using Memory.py backend)")

    def remember(self, category: str, key: str, value: str) -> MemoryFact:
        """
        Store a memory fact using Memory.py backend.

        Args:
            category: Category of the fact
            key: Unique key
            value: Value to store

        Returns:
            The stored fact
        """
        # Store using Memory.py
        self.memory.upsert_fact(category, key, value)

        # Return fact from Memory.py
        fact = self.memory.fact_value(category, key)
        if fact:
            return MemoryFact(category=category, key=key, value=fact)
        else:
            # Fallback to MemoryFact
            return MemoryFact(category=category, key=key, value=value)

        logger.debug(f"Stored fact: {category}/{key}={value}")
        return fact

    def retrieve(self, category: str, key: str) -> MemoryFact | None:
        """
        Retrieve a specific fact using Memory.py backend.

        Args:
            category: Category of the fact
            key: Key to retrieve

        Returns:
            Fact or None
        """
        value = self.memory.fact_value(category, key)
        if value:
            return MemoryFact(category=category, key=key, value=value)
        return None

        # Note: This retrieves facts directly from Memory.py (SQLite)
        # No need to copy or transform
        logger.debug(f"Retrieved fact: {category}/{key}")

    def remember_exchange(self, query: str, answer: str, topic: str) -> dict:
        """
        Store a conversation exchange using Memory.py backend.

        Args:
            query: User query
            answer: AI response
            topic: Topic of the conversation

        Returns:
            Dictionary containing the exchange data
        """
        # Store using Memory.py
        self.memory.remember_exchange(query, answer, topic)

        # Return the stored exchange
        messages = self.memory.recent_messages(limit=1)
        if messages and len(messages) > 0:
            return messages[0]
        else:
            # Fallback to manual dictionary
            return {"question": query, "answer": answer, "topic": topic}

        logger.debug(f"Stored exchange for topic: {topic}")

    def get_facts_by_category(self, category: str) -> list[MemoryFact]:
        """
        Get facts by category using Memory.py backend.

        Args:
            category: Category to filter by

        Returns:
            List of facts in category
        """
        return self.memory.values_for_category(category)

    def get_context(self) -> str:
        """
        Build memory context string using Memory.py backend.

        Returns:
            Formatted context string
        """
        context = self.memory.get_context()

        if not context:
            logger.warning("No context available in Memory.py")
            return "No memory facts stored yet."

        logger.debug(f"Built context with {len(self.memory.facts())} facts")
        return context

    def get_recent_messages(self, limit: int = 10) -> list[dict]:
        """
        Get recent messages from Memory.py backend.

        Args:
            limit: Maximum number of messages

        Returns:
            List of recent messages
        """
        messages = self.memory.recent_messages(limit=limit)

        if not messages:
            logger.warning("No recent messages found in Memory.py")
            return []

        logger.debug(f"Retrieved {len(messages)} recent messages from Memory.py")
        return messages

    def get_all_categories(self) -> list[str]:
        """
        Get all memory categories using Memory.py backend.

        Returns:
            List of category names
        """
        # Use Memory.py's values_for_category to get all unique values
        categories = set()
        for fact in self.memory.facts():
            categories.add(fact.category)
        return sorted(list(categories))
