"""
Knowledge Database - Stores factual knowledge separately from chat history.

This module implements a persistent knowledge store that Aura uses to remember
facts, their sources, confidence levels, and freshness.

Knowledge structure:
{
    "topic": "Python",
    "fact": "Latest stable version is 3.15",
    "source": "python.org",
    "confidence": 0.99,
    "updated": "2026-07-28",
    "expires": "2026-08-28",
    "category": "Programming",
    "related_topics": ["Programming", "Python", "Software"],
    "source_type": "official",
    "metadata": {}
}
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

try:
    from brain.models import IntentName
except (ImportError, ModuleNotFoundError):
    IntentName = str  # Fallback: use string as type hint


@dataclass
class KnowledgeFact:
    """A single piece of factual knowledge."""

    topic: str
    fact: str
    source: str
    source_url: str | None = None
    confidence: float = 0.9  # 0.0 to 1.0
    updated: str = ""
    expires: str = ""
    category: str = "General"
    related_topics: list[str] = None
    source_type: str = "web"
    metadata: dict[str, Any] = None
    id: int | None = None  # Database row ID

    def __post_init__(self):
        if self.related_topics is None:
            self.related_topics = []
        if self.metadata is None:
            self.metadata = {}

        # Set defaults if not provided
        if not self.updated:
            self.updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.expires:
            # Default: 30 days for programming docs, 7 days for news, etc.
            self.expires = self._calculate_expiry()
        if not self.confidence:
            self.confidence = 0.9

    def _calculate_expiry(self) -> str:
        """Calculate expiry date based on category."""
        category_map = {
            "Programming": "30 days",
            "Networking": "30 days",
            "Cybersecurity": "30 days",
            "AI": "60 days",
            "Operating Systems": "30 days",
            "Finance": "7 days",
            "Technology": "14 days",
            "Science": "30 days",
            "Personal Memory": "90 days",
            "Conversation History": "7 days",
        }
        days = category_map.get(self.category, 30)
        # Handle both int and string values
        if isinstance(days, int):
            days_str = str(days)
        else:
            days_str = days
        expiry_date = datetime.now() + timedelta(days=int(days_str.split()[0]))
        return expiry_date.strftime("%Y-%m-%d %H:%M:%S")

    def is_fresh(self) -> bool:
        """Check if this fact is still fresh (not expired)."""
        try:
            expiry = datetime.strptime(self.expires, "%Y-%m-%d %H:%M:%S")
            return datetime.now() < expiry
        except (ValueError, AttributeError):
            return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeFact:
        """Create from dictionary."""
        return cls(**data)


class KnowledgeDB:
    """
    Knowledge Database - Persistent storage for factual knowledge.

    Features:
    - Store facts with metadata, confidence, and freshness
    - Query by topic, category, confidence
    - Track knowledge lifecycle
    - Thread-safe operations
    - Knowledge categorization
    """

    # Default categories
    DEFAULT_CATEGORIES = [
        "Programming",
        "Networking",
        "Cybersecurity",
        "AI",
        "Operating Systems",
        "Finance",
        "Technology",
        "Science",
        "Personal Memory",
        "Conversation History",
    ]

    def __init__(self, db_path: str = "knowledge.db"):
        """
        Initialize knowledge database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database schema."""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            # Create knowledge table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_url TEXT,
                    confidence REAL DEFAULT 0.9,
                    updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires TEXT DEFAULT '30 days',
                    category TEXT DEFAULT 'General',
                    related_topics TEXT,
                    source_type TEXT DEFAULT 'web',
                    metadata TEXT
                )
            """)

            # Create indexes for fast queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_topic ON knowledge(topic)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON knowledge(category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_confidence ON knowledge(confidence)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_updated ON knowledge(updated)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_topic_category ON knowledge(topic, category)
            """)

            conn.commit()
            conn.close()

    def add_fact(self, fact: KnowledgeFact) -> int:
        """
        Add a new fact to the knowledge base.

        Args:
            fact: KnowledgeFact object to add

        Returns:
            Row ID of the inserted fact
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO knowledge (
                    topic, fact, source, source_url, confidence, updated,
                    expires, category, related_topics, source_type, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    fact.topic,
                    fact.fact,
                    fact.source,
                    fact.source_url,
                    fact.confidence,
                    fact.updated,
                    fact.expires,
                    fact.category,
                    json.dumps(fact.related_topics) if fact.related_topics else None,
                    fact.source_type,
                    json.dumps(fact.metadata) if fact.metadata else None,
                ),
            )

            row_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return row_id

    def add_facts(self, facts: list[KnowledgeFact]) -> list[int]:
        """
        Add multiple facts at once.

        Args:
            facts: List of KnowledgeFact objects

        Returns:
            List of row IDs
        """
        row_ids = []
        for fact in facts:
            row_ids.append(self.add_fact(fact))
        return row_ids

    def get_facts(
        self,
        topic: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
        limit: int = 100,
    ) -> list[KnowledgeFact]:
        """
        Retrieve facts from the knowledge base.

        Args:
            topic: Filter by topic (optional)
            category: Filter by category (optional)
            confidence: Filter by confidence threshold (optional)
            limit: Maximum number of results

        Returns:
            List of KnowledgeFact objects
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            query = "SELECT * FROM knowledge WHERE 1=1"
            params = []

            if topic:
                query += " AND topic = ?"
                params.append(topic)

            if category:
                query += " AND category = ?"
                params.append(category)

            if confidence is not None:
                query += " AND confidence >= ?"
                params.append(confidence)

            query += " ORDER BY confidence DESC, updated DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            facts = []
            for row in rows:
                fact = KnowledgeFact(
                    id=row[0],
                    topic=row[1],
                    fact=row[2],
                    source=row[3],
                    source_url=row[4],
                    confidence=row[5],
                    updated=row[6],
                    expires=row[7],
                    category=row[8],
                    related_topics=json.loads(row[9]) if row[9] else [],
                    source_type=row[10],
                    metadata=json.loads(row[11]) if row[11] else {},
                )
                facts.append(fact)

            conn.close()
            return facts

    def get_fresh_facts(
        self, category: str | None = None, limit: int = 100
    ) -> list[KnowledgeFact]:
        """
        Get only fresh facts (not expired).

        Args:
            category: Filter by category (optional)
            limit: Maximum number of results

        Returns:
            List of fresh KnowledgeFact objects
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            query = "SELECT * FROM knowledge WHERE 1=1"
            params = []

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " ORDER BY confidence DESC, updated DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            facts = []
            for row in rows:
                fact = KnowledgeFact(
                    id=row[0],
                    topic=row[1],
                    fact=row[2],
                    source=row[3],
                    source_url=row[4],
                    confidence=row[5],
                    updated=row[6],
                    expires=row[7],
                    category=row[8],
                    related_topics=json.loads(row[9]) if row[9] else [],
                    source_type=row[10],
                    metadata=json.loads(row[11]) if row[11] else {},
                )
                # Only add if fresh
                if fact.is_fresh():
                    facts.append(fact)

            conn.close()
            return facts

    def get_facts_by_topic(self, topic: str, limit: int = 50) -> list[KnowledgeFact]:
        """
        Get all facts for a specific topic.

        Args:
            topic: The topic to query
            limit: Maximum number of results

        Returns:
            List of KnowledgeFact objects
        """
        return self.get_facts(topic=topic, limit=limit)

    def get_facts_by_category(
        self, category: str, limit: int = 50
    ) -> list[KnowledgeFact]:
        """
        Get all facts for a specific category.

        Args:
            category: The category to query
            limit: Maximum number of results

        Returns:
            List of KnowledgeFact objects
        """
        return self.get_facts(category=category, limit=limit)

    def update_fact(self, fact_id: int, updated_fact: KnowledgeFact) -> bool:
        """
        Update an existing fact.

        Args:
            fact_id: ID of the fact to update
            updated_fact: Updated KnowledgeFact object

        Returns:
            True if updated, False if not found
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE knowledge
                SET topic=?, fact=?, source=?, source_url=?, confidence=?,
                    updated=CURRENT_TIMESTAMP, expires=?, category=?,
                    related_topics=?, source_type=?, metadata=?
                WHERE id=?
            """,
                (
                    updated_fact.topic,
                    updated_fact.fact,
                    updated_fact.source,
                    updated_fact.source_url,
                    updated_fact.confidence,
                    updated_fact.expires,
                    updated_fact.category,
                    (
                        json.dumps(updated_fact.related_topics)
                        if updated_fact.related_topics
                        else None
                    ),
                    updated_fact.source_type,
                    (
                        json.dumps(updated_fact.metadata)
                        if updated_fact.metadata
                        else None
                    ),
                    fact_id,
                ),
            )

            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()

            return rows_affected > 0

    def delete_fact(self, fact_id: int) -> bool:
        """
        Delete a fact from the knowledge base.

        Args:
            fact_id: ID of the fact to delete

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM knowledge WHERE id=?", (fact_id,))

            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()

            return rows_affected > 0

    def get_topics(self) -> set[str]:
        """
        Get all unique topics in the knowledge base.

        Returns:
            Set of topic names
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute("SELECT DISTINCT topic FROM knowledge")
            topics = {row[0] for row in cursor.fetchall()}

            conn.close()
            return topics

    def get_categories(self) -> list[str]:
        """
        Get all unique categories in the knowledge base.

        Returns:
            List of category names
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute("SELECT DISTINCT category FROM knowledge")
            categories = [row[0] for row in cursor.fetchall()]

            conn.close()
            return categories

    def cleanup_expired_facts(self) -> int:
        """
        Remove expired facts from the database.

        Returns:
            Number of facts removed
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM knowledge WHERE expires < CURRENT_TIMESTAMP")
            removed = cursor.rowcount

            conn.commit()
            conn.close()

            return removed

    def count_facts(self, category: str | None = None) -> int:
        """
        Count total facts in the database.

        Args:
            category: Filter by category (optional)

        Returns:
            Count of facts
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            if category:
                cursor.execute(
                    "SELECT COUNT(*) FROM knowledge WHERE category=?", (category,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM knowledge")

            count = cursor.fetchone()[0]
            conn.close()

            return count

    def search_facts(self, query: str, limit: int = 20) -> list[KnowledgeFact]:
        """
        Search facts using full-text search.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching KnowledgeFact objects
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            # Simple search implementation
            # For production, consider implementing FTS5 full-text search
            search_pattern = f"%{query}%"
            cursor.execute(
                """
                SELECT * FROM knowledge
                WHERE topic LIKE ? OR fact LIKE ? OR source LIKE ?
                ORDER BY confidence DESC
                LIMIT ?
            """,
                (search_pattern, search_pattern, search_pattern, limit),
            )

            rows = cursor.fetchall()

            facts = []
            for row in rows:
                fact = KnowledgeFact(
                    id=row[0],
                    topic=row[1],
                    fact=row[2],
                    source=row[3],
                    source_url=row[4],
                    confidence=row[5],
                    updated=row[6],
                    expires=row[7],
                    category=row[8],
                    related_topics=json.loads(row[9]) if row[9] else [],
                    source_type=row[10],
                    metadata=json.loads(row[11]) if row[11] else {},
                )
                facts.append(fact)

            conn.close()
            return facts

    def search_topics(self, query: str, limit: int = 20) -> list[str]:
        """
        Search topics by keyword.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching topic names
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            # Simple search implementation
            search_pattern = f"%{query}%"
            cursor.execute(
                """
                SELECT DISTINCT topic FROM knowledge
                WHERE topic LIKE ?
                ORDER BY topic
                LIMIT ?
            """,
                (search_pattern, limit),
            )

            topics = [row[0] for row in cursor.fetchall()]
            conn.close()

            return topics
