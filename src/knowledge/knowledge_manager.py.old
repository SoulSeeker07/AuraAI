"""
Knowledge Manager - Orchestrates the entire Knowledge Brain.

This is the main entry point for the knowledge brain system.
It combines all modules to provide a unified interface for Aura.

Architecture:
    User Query
      ↓
  Knowledge Brain
      ↓
┌─────────────────────────────────────────┐
│  Knowledge Manager (this module)        │
└─────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────┐
│  1. Check Cache                          │
│  2. Check Freshness                      │
│  3. Check Knowledge Base                 │
│  4. Perform Search (if needed)          │
│  5. Learn from Search                    │
│  6. Return Answer                        │
└─────────────────────────────────────────┘

Usage Example:
    manager = KnowledgeManager()

    # Get knowledge
    facts = manager.retrieve_facts("Python version")
    if not facts:
        # Perform search
        results = manager.search_web("Python version")
        # Learn from results
        manager.learn_from_results(results)

    # Refresh expired knowledge
    manager.refresh_expired_knowledge()

This makes Aura self-learning and intelligent!
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import threading

from .knowledge_db import KnowledgeDB, KnowledgeFact
from .topic_memory import TopicMemory
from .knowledge_graph import KnowledgeGraph
from .freshness_checker import FreshnessChecker, KnowledgeCategory
from .learning_engine import LearningEngine, LearnedFact
from .cache_manager import CacheManager


@dataclass
class KnowledgeRetrievalResult:
    """Result of knowledge retrieval."""
    facts: List[KnowledgeFact]
    retrieved_from: str  # "cache", "database", "search", "none"
    confidence: float
    needs_refresh: bool
    suggestions: List[str]


class KnowledgeManager:
    """
    Main orchestrator for the Knowledge Brain.

    Features:
    - Unified interface for all knowledge operations
    - Multi-level retrieval (cache → database → search)
    - Automatic freshness checking
    - Learning from web searches
    - Topic-aware organization
    - Relationship mapping
    - Statistics and monitoring

    Usage:
        manager = KnowledgeManager()

        # Retrieve facts
        result = manager.retrieve_facts("Python version")

        if result.needs_refresh:
            # Perform search
            manager.search_web("Python version")

        # Get related topics
        related = manager.get_related_topics("Python")

        # Learn from search results
        manager.learn_from_search_results(results)
    """

    def __init__(
        self,
        knowledge_db: KnowledgeDB = None,
        topic_memory: TopicMemory = None,
        knowledge_graph: KnowledgeGraph = None,
        freshness_checker: FreshnessChecker = None,
        learning_engine: LearningEngine = None,
        cache_manager: CacheManager = None
    ):
        """
        Initialize knowledge manager.

        Args:
            knowledge_db: KnowledgeDB instance
            topic_memory: TopicMemory instance
            knowledge_graph: KnowledgeGraph instance
            freshness_checker: FreshnessChecker instance
            learning_engine: LearningEngine instance
            cache_manager: CacheManager instance
        """
        self.knowledge_db = knowledge_db or KnowledgeDB()
        self.cache_manager = cache_manager or CacheManager()
        self.topic_memory = topic_memory or TopicMemory(self.knowledge_db)
        self.knowledge_graph = knowledge_graph or KnowledgeGraph(self.knowledge_db)
        self.freshness_checker = freshness_checker or FreshnessChecker(self.knowledge_db)
        self.learning_engine = learning_engine or LearningEngine(
            self.knowledge_db,
            self.topic_memory,
            self.knowledge_graph,
            self.freshness_checker,
            self.cache_manager
        )

        self._lock = threading.Lock()
        self._total_retrievals = 0
        self._total_learnings = 0

    def retrieve_facts(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 10
    ) -> KnowledgeRetrievalResult:
        """
        Retrieve facts for a query using multi-level retrieval.

        Retrieval strategy:
        1. Check cache first
        2. Check fresh knowledge base
        3. Return if found
        4. If not found, perform search
        5. Learn from search and return

        Args:
            query: Search query
            category: Category to search (optional)
            max_results: Maximum number of facts to return

        Returns:
            KnowledgeRetrievalResult with facts and metadata
        """
        with self._lock:
            self._total_retrievals += 1

            # Try to get from cache first
            cached = self.cache_manager.get_cached_result(query, category or "General")

            if cached:
                return self._create_result_from_facts(
                    cached,
                    retrieved_from="cache",
                    needs_refresh=False,
                    category=category
                )

            # Try to get from knowledge base
            topics = self.knowledge_db.get_topics()
            relevant_topics = []

            for topic in topics:
                if query.lower() in topic.lower():
                    relevant_topics.append(topic)
                else:
                    # Check facts in topic
                    facts = self.knowledge_db.get_facts_by_topic(topic, limit=100)
                    for fact in facts:
                        if query.lower() in fact.fact.lower() or query.lower() in fact.source.lower():
                            relevant_topics.append(topic)
                            break

            if relevant_topics:
                facts = []
                for topic in relevant_topics[:5]:  # Limit to 5 topics
                    facts.extend(self.knowledge_db.get_facts_by_topic(topic, limit=20))

                # Filter to max_results and sort by confidence
                facts = sorted(facts, key=lambda x: x.confidence, reverse=True)
                facts = facts[:max_results]

                return self._create_result_from_facts(
                    facts,
                    retrieved_from="database",
                    needs_refresh=False,
                    category=category
                )

            # Not found in cache or database - need to search
            return KnowledgeRetrievalResult(
                facts=[],
                retrieved_from="none",
                confidence=0.0,
                needs_refresh=True,
                suggestions=[f"Search for '{query}'", f"Learn about {query}"]
            )

    def _create_result_from_facts(
        self,
        facts: List[KnowledgeFact],
        retrieved_from: str,
        needs_refresh: bool,
        category: Optional[str]
    ) -> KnowledgeRetrievalResult:
        """
        Create a retrieval result from facts.

        Args:
            facts: List of facts
            retrieved_from: Where facts came from
            needs_refresh: Whether facts need refresh
            category: Category

        Returns:
            KnowledgeRetrievalResult
        """
        if not facts:
            return KnowledgeRetrievalResult(
                facts=[],
                retrieved_from=retrieved_from,
                confidence=0.0,
                needs_refresh=needs_refresh,
                suggestions=[]
            )

        # Check freshness
        all_fresh = all(self.freshness_checker.is_fresh(fact) for fact in facts)
        needs_refresh = not all_fresh

        # Calculate overall confidence
        avg_confidence = sum(f.confidence for f in facts) / len(facts)

        # Generate suggestions
        suggestions = []
        if needs_refresh:
            suggestions.append("Some knowledge may be outdated")

        return KnowledgeRetrievalResult(
            facts=facts[:10],  # Limit to 10 facts
            retrieved_from=retrieved_from,
            confidence=avg_confidence,
            needs_refresh=needs_refresh,
            suggestions=suggestions
        )

    def search_web(
        self,
        query: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search the web for a query.

        Note: This is a stub that should be implemented to connect to actual
        search engines (Tavily API, Google Custom Search, etc.).

        Args:
            query: Search query
            category: Category (affects cache expiry)

        Returns:
            List of search results
        """
        # TODO: Connect to actual search engine
        # This should call WebSearchClient or Tavily API
        return []

    def learn_from_search_results(
        self,
        search_results: List[Dict[str, Any]],
        query: str,
        category: Optional[str] = None
    ) -> List[LearnedFact]:
        """
        Learn important facts from search results.

        Args:
            search_results: List of search results
            query: Original query
            category: Category

        Returns:
            List of learned facts
        """
        # Extract topic from query
        topic = self._extract_topic(query)

        if not topic:
            # Default to category
            topic = category or "General"

        # Learn from search results
        learned_facts = self.learning_engine.learn_from_web_search(
            topic,
            search_results,
            query
        )

        self._total_learnings += len(learned_facts)

        return learned_facts

    def _extract_topic(self, query: str) -> Optional[str]:
        """
        Extract topic from query.

        Args:
            query: Query string

        Returns:
            Topic name or None
        """
        words = query.lower().split()
        all_topics = self.knowledge_db.get_topics()

        for word in words:
            for topic in all_topics:
                if word in topic.lower():
                    return topic

        return None

    def get_related_topics(self, topic: str, depth: int = 2) -> List[str]:
        """
        Get related topics for a given topic.

        Args:
            topic: Topic name
            depth: Depth of relationship search

        Returns:
            List of related topic names
        """
        return self.knowledge_graph.get_topic_neighbors(topic, depth)

    def get_topic_hierarchy(self, topic: str) -> Dict[str, Any]:
        """
        Get hierarchical structure for a topic.

        Args:
            topic: Topic name

        Returns:
            Dictionary with hierarchy
        """
        return self.topic_memory.get_topic_hierarchy(topic, max_depth=3)

    def get_all_topics(self) -> List[str]:
        """
        Get all available topics.

        Returns:
            List of topic names
        """
        return self.knowledge_db.get_topics()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall knowledge brain statistics.

        Returns:
            Dictionary with statistics
        """
        cache_stats = self.cache_manager.get_cache_stats()
        freshness_stats = self.freshness_checker.get_statistics()
        graph_stats = self.knowledge_graph.get_statistics()
        learning_stats = self.learning_engine.get_statistics()

        return {
            "total_retrievals": self._total_retrievals,
            "total_learnings": self._total_learnings,
            "knowledge_db": {
                "total_facts": self.knowledge_db.count_facts(),
                "total_topics": len(self.knowledge_db.get_topics()),
                "total_categories": len(self.knowledge_db.get_categories())
            },
            "cache": cache_stats,
            "freshness": freshness_stats,
            "knowledge_graph": graph_stats,
            "learning": learning_stats
        }

    def refresh_expired_knowledge(self) -> Dict[str, int]:
        """
        Refresh all expired knowledge.

        Returns:
            Dictionary with refresh statistics
        """
        with self._lock:
            topics = self.knowledge_db.get_topics()
            stats = {"refreshed": 0, "expired": 0}

            for topic in topics:
                facts = self.knowledge_db.get_facts_by_topic(topic, limit=100)
                for fact in facts:
                    if not self.freshness_checker.is_fresh(fact):
                        stats["expired"] += 1
                        # Invalidate cache for this topic
                        self.cache_manager.invalidate_query(topic, fact.category)

            return stats

    def get_facts_by_topic(self, topic: str, max_results: int = 50) -> List[KnowledgeFact]:
        """
        Get facts for a specific topic.

        Args:
            topic: Topic name
            max_results: Maximum number of facts

        Returns:
            List of facts
        """
        return self.knowledge_db.get_facts_by_topic(topic, limit=max_results)

    def get_facts_by_category(self, category: str, max_results: int = 50) -> List[KnowledgeFact]:
        """
        Get facts for a specific category.

        Args:
            category: Category name
            max_results: Maximum number of facts

        Returns:
            List of facts
        """
        return self.knowledge_db.get_facts_by_category(category, limit=max_results)

    def add_fact(
        self,
        topic: str,
        fact: str,
        source: str,
        confidence: float = 0.9,
        category: str = "General",
        source_url: Optional[str] = None
    ) -> bool:
        """
        Add a fact to the knowledge base.

        Args:
            topic: Topic name
            fact: Fact text
            source: Source name
            confidence: Confidence score (0.0-1.0)
            category: Category
            source_url: Source URL

        Returns:
            True if successful
        """
        from .knowledge_db import KnowledgeFact

        knowledge_fact = KnowledgeFact(
            topic=topic,
            fact=fact,
            source=source,
            source_url=source_url,
            confidence=confidence,
            category=category
        )

        self.knowledge_db.add_fact(knowledge_fact)
        self.topic_memory.add_fact(knowledge_fact)
        self.knowledge_graph.add_fact(knowledge_fact)

        return True

    def batch_add_facts(self, facts: List[Dict[str, Any]]) -> int:
        """
        Batch add multiple facts.

        Args:
            facts: List of fact dictionaries

        Returns:
            Number of facts added
        """
        added = 0

        for fact_data in facts:
            self.add_fact(
                topic=fact_data.get("topic", "General"),
                fact=fact_data.get("fact", ""),
                source=fact_data.get("source", "web"),
                confidence=fact_data.get("confidence", 0.9),
                category=fact_data.get("category", "General"),
                source_url=fact_data.get("source_url")
            )
            added += 1

        return added

    def cleanup_expired_knowledge(self) -> int:
        """
        Clean up expired facts from database.

        Returns:
            Number of facts removed
        """
        return self.knowledge_db.cleanup_expired_facts()

    def get_category_lifetimes(self) -> Dict[str, int]:
        """
        Get category lifetimes.

        Returns:
            Dictionary mapping categories to lifetimes in days
        """
        return self.freshness_checker.LIFETIME_MAP

    def update_category_lifetime(self, category: str, days: int) -> None:
        """
        Update a category's lifetime.

        Args:
            category: Category name
            days: Lifetime in days
        """
        self.freshness_checker.update_lifetime(category, days)

    def get_freshness_checker_stats(self) -> Dict[str, Any]:
        """
        Get freshness checker statistics.

        Returns:
            Dictionary with statistics
        """
        return self.freshness_checker.get_statistics()

    def get_cache_manager_stats(self) -> Dict[str, Any]:
        """
        Get cache manager statistics.

        Returns:
            Dictionary with statistics
        """
        return self.cache_manager.get_cache_stats()

    def get_knowledge_graph_stats(self) -> Dict[str, Any]:
        """
        Get knowledge graph statistics.

        Returns:
            Dictionary with statistics
        """
        return self.knowledge_graph.get_statistics()

    def get_learning_engine_stats(self) -> Dict[str, Any]:
        """
        Get learning engine statistics.

        Returns:
            Dictionary with statistics
        """
        return self.learning_engine.get_statistics()
