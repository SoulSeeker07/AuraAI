"""
Learning Engine - Auto-updates knowledge from web searches.

This module handles automatic knowledge acquisition and updates:
    1. User asks a question
    2. Aura searches the web
    3. Learning Engine extracts important facts
    4. Facts are scored by confidence
    5. High-confidence facts are stored in KnowledgeDB
    6. Topic memory and knowledge graph are updated

Example:
    User asks: "Latest Groq models"

    Aura searches:
      - Groq official site
      - AI news sites
      - GitHub repositories

    Learning Engine extracts:
      - "Groq has released Groq-1, a fast inference model"
      - "Groq pricing starts at $0.59 per million tokens"
      - "Groq supports LLaMA 3 and other models"

    High-confidence facts stored:
      - Topic: Groq
      - Confidence: 0.95+
      - Category: AI

    Next time user asks about Groq, Aura already knows!
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .cache_manager import CacheManager
from .freshness_checker import FreshnessChecker
from .knowledge_db import KnowledgeDB
from .knowledge_graph import KnowledgeGraph
from .topic_memory import TopicMemory


@dataclass
class LearnedFact:
    """
    A fact learned from a web search result.
    """

    topic: str
    fact: str
    source: str
    source_url: str | None = None
    confidence: float = 0.8  # 0.0 to 1.0
    category: str = "General"
    related_topics: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    learned_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    processing_time: float = 0.0


class LearningEngine:
    """
    Automatic knowledge learning and updating engine.

    Features:
    - Extract important facts from web search results
    - Score facts by confidence
    - Update knowledge database automatically
    - Build topic memory and knowledge graphs
    - Handle knowledge conflicts
    - Track learning statistics
    - Batch processing support
    """

    def __init__(
        self,
        knowledge_db: KnowledgeDB = None,
        topic_memory: TopicMemory = None,
        knowledge_graph: KnowledgeGraph = None,
        freshness_checker: FreshnessChecker = None,
        cache_manager: CacheManager = None,
    ):
        """
        Initialize learning engine.

        Args:
            knowledge_db: KnowledgeDB instance
            topic_memory: TopicMemory instance
            knowledge_graph: KnowledgeGraph instance
            freshness_checker: FreshnessChecker instance
            cache_manager: CacheManager instance
        """
        self.knowledge_db = knowledge_db or KnowledgeDB()
        self.topic_memory = topic_memory or TopicMemory(self.knowledge_db)
        self.knowledge_graph = knowledge_graph or KnowledgeGraph(self.knowledge_db)
        self.freshness_checker = freshness_checker or FreshnessChecker(
            self.knowledge_db
        )
        self.cache_manager = cache_manager or CacheManager()

        self._lock = threading.Lock()
        self._learning_stats = {
            "total_learned": 0,
            "topics_learned": 0,
            "average_confidence": 0.0,
            "learning_time": 0.0,
        }

    def learn_from_web_search(
        self, topic: str, search_results: list[dict[str, Any]], user_query: str = ""
    ) -> list[LearnedFact]:
        """
        Learn important facts from web search results.

        Args:
            topic: Topic name
            search_results: List of search result dictionaries
            user_query: Original user query (for context)

        Returns:
            List of learned facts
        """
        import time

        start_time = time.time()

        with self._lock:
            learned_facts = []
            topics_involved = set()

            for result in search_results:
                fact = self._extract_fact_from_result(result, topic, user_query)
                if fact:
                    learned_facts.append(fact)
                    topics_involved.add(fact.topic)

            # Store learned facts
            for fact in learned_facts:
                self.knowledge_db.add_fact(self._fact_to_knowledge_fact(fact))
                self.topic_memory.add_fact(self._fact_to_knowledge_fact(fact))
                self.knowledge_graph.add_fact(self._fact_to_knowledge_fact(fact))
                self.cache_manager.cache_search_result(topic, result)

            # Update statistics
            self._update_stats(len(learned_facts), topics_involved)

            processing_time = time.time() - start_time

            return learned_facts

    def _extract_fact_from_result(
        self, result: dict[str, Any], topic: str, user_query: str
    ) -> LearnedFact | None:
        """
        Extract a fact from a search result.

        Args:
            result: Search result dictionary
            topic: Topic name
            user_query: User query for context

        Returns:
            LearnedFact or None
        """
        try:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            url = result.get("url", "")
            source = result.get("source", "web")

            if not title and not snippet:
                return None

            # Extract main content (combine title and snippet)
            content = f"{title}. {snippet}"

            # Determine category
            category = self._determine_category(content, topic)

            # Extract keywords for related topics
            keywords = self._extract_keywords(content)
            related_topics = self._find_related_topics(keywords, topic)

            # Calculate confidence based on source
            confidence = self._calculate_confidence(source)

            # Create LearnedFact
            learned_fact = LearnedFact(
                topic=topic,
                fact=content[:500],  # Limit length
                source=source,
                source_url=url,
                confidence=confidence,
                category=category,
                related_topics=related_topics,
            )

            return learned_fact

        except Exception as e:
            print(f"[LearningEngine] Error extracting fact: {e}")
            return None

    def _fact_to_knowledge_fact(self, learned_fact: LearnedFact) -> Any:
        """
        Convert LearnedFact to KnowledgeFact.

        Args:
            learned_fact: LearnedFact to convert

        Returns:
            KnowledgeFact object
        """
        from .knowledge_db import KnowledgeFact

        return KnowledgeFact(
            topic=learned_fact.topic,
            fact=learned_fact.fact,
            source=learned_fact.source,
            source_url=learned_fact.source_url,
            confidence=learned_fact.confidence,
            category=learned_fact.category,
            related_topics=learned_fact.related_topics,
        )

    def _determine_category(self, content: str, topic: str) -> str:
        """
        Determine knowledge category based on content and topic.

        Args:
            content: Content to analyze
            topic: Topic name

        Returns:
            Category name
        """
        # Simple category mapping based on topic
        topic_lower = topic.lower()
        content_lower = content.lower()

        if any(
            x in topic_lower
            for x in ["python", "java", "javascript", "programming", "code"]
        ):
            return "Programming"
        elif any(
            x in topic_lower for x in ["network", "routing", "ospf", "bgp", "firewall"]
        ):
            return "Networking"
        elif any(
            x in topic_lower
            for x in ["security", "vulnerability", "patch", "cybersecurity"]
        ):
            return "Cybersecurity"
        elif any(x in topic_lower for x in ["ai", "machine learning", "llm", "model"]):
            return "AI"
        elif any(x in topic_lower for x in ["windows", "mac", "linux", "os"]):
            return "Operating Systems"
        elif any(x in topic_lower for x in ["news", "release", "version"]):
            return "Technology"
        elif any(x in topic_lower for x in ["weather", "temperature"]):
            return "Weather"
        else:
            return "General"

    def _extract_keywords(self, content: str) -> set[str]:
        """
        Extract keywords from content.

        Args:
            content: Content to extract keywords from

        Returns:
            Set of keywords
        """
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
            "of",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
            "from",
            "as",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "they",
            "them",
            "their",
            "we",
            "our",
            "you",
            "your",
            "what",
            "which",
            "who",
            "whom",
            "where",
            "when",
            "why",
            "how",
            "new",
            "version",
            "latest",
            "update",
            "release",
            "feature",
        }

        words = content.lower().split()
        keywords = set()

        for word in words:
            if word not in stop_words and len(word) > 2 and len(word) < 20:
                keywords.add(word)

        return keywords

    def _find_related_topics(self, keywords: set[str], current_topic: str) -> list[str]:
        """
        Find related topics based on keywords.

        Args:
            keywords: Set of keywords
            current_topic: Current topic name

        Returns:
            List of related topic names
        """
        related_topics = []

        # Try to find topics that match keywords
        all_topics = self.knowledge_db.get_topics()

        for keyword in keywords:
            for topic in all_topics:
                if keyword.lower() in topic.lower() and topic != current_topic:
                    if topic not in related_topics:
                        related_topics.append(topic)

        return related_topics[:5]  # Limit to 5 related topics

    def _calculate_confidence(self, source: str) -> float:
        """
        Calculate confidence score based on source.

        Args:
            source: Source name

        Returns:
            Confidence score (0.0 to 1.0)
        """
        source_lower = source.lower()

        if "official" in source_lower or source_lower in [
            "python.org",
            "microsoft.com",
            "github.com",
            "cisco.com",
        ]:
            return 0.95
        elif "news" in source_lower or "blog" in source_lower:
            return 0.75
        elif "reddit" in source_lower or "forum" in source_lower:
            return 0.6
        else:
            return 0.8

    def _update_stats(self, fact_count: int, topics: set[str]) -> None:
        """
        Update learning statistics.

        Args:
            fact_count: Number of facts learned
            topics: Set of topics involved
        """
        self._learning_stats["total_learned"] += fact_count
        self._learning_stats["topics_learned"] = len(topics)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get learning engine statistics.

        Returns:
            Dictionary with statistics
        """
        return self._learning_stats.copy()

    def get_known_topics(self) -> list[str]:
        """
        Get all topics that have been learned.

        Returns:
            List of topic names
        """
        topics = self.knowledge_db.get_topics()
        return sorted(topics)

    def get_topic_facts(self, topic: str) -> list[LearnedFact]:
        """
        Get all facts for a topic.

        Args:
            topic: Topic name

        Returns:
            List of LearnedFact objects
        """
        facts = self.knowledge_db.get_facts_by_topic(topic)
        learned_facts = []

        for fact in facts:
            learned_facts.append(
                LearnedFact(
                    topic=fact.topic,
                    fact=fact.fact,
                    source=fact.source,
                    source_url=fact.source_url,
                    confidence=fact.confidence,
                    category=fact.category,
                    related_topics=fact.related_topics or [],
                )
            )

        return learned_facts

    def batch_learn(
        self, learnings: list[dict[str, Any]], topic: str
    ) -> list[LearnedFact]:
        """
        Batch process multiple learnings.

        Args:
            learnings: List of learning dictionaries
            topic: Topic name

        Returns:
            List of learned facts
        """
        learned_facts = []

        for learning in learnings:
            # Extract fact
            fact_data = {
                "title": learning.get("title", ""),
                "snippet": learning.get("snippet", ""),
                "url": learning.get("url", ""),
                "source": learning.get("source", "web"),
            }

            learned_fact = self._extract_fact_from_result(fact_data, topic, "")
            if learned_fact:
                learned_facts.append(learned_fact)

                # Store in knowledge base
                from .knowledge_db import KnowledgeFact

                self.knowledge_db.add_fact(
                    KnowledgeFact(
                        topic=learned_fact.topic,
                        fact=learned_fact.fact,
                        source=learned_fact.source,
                        source_url=learned_fact.source_url,
                        confidence=learned_fact.confidence,
                        category=learned_fact.category,
                        related_topics=learned_fact.related_topics,
                    )
                )
                self.topic_memory.add_fact(
                    KnowledgeFact(
                        topic=learned_fact.topic,
                        fact=learned_fact.fact,
                        source=learned_fact.source,
                        source_url=learned_fact.source_url,
                        confidence=learned_fact.confidence,
                        category=learned_fact.category,
                        related_topics=learned_fact.related_topics,
                    )
                )
                self.knowledge_graph.add_fact(
                    KnowledgeFact(
                        topic=learned_fact.topic,
                        fact=learned_fact.fact,
                        source=learned_fact.source,
                        source_url=learned_fact.source_url,
                        confidence=learned_fact.confidence,
                        category=learned_fact.category,
                        related_topics=learned_fact.related_topics,
                    )
                )

        return learned_facts

    async def auto_learn_from_conversation(
        self, user_query: str, ai_response: str, search_results: list[dict[str, Any]]
    ) -> list[LearnedFact]:
        """
        Automatically learn from conversation context.

        Args:
            user_query: User's query
            ai_response: Aura's response
            search_results: Search results used

        Returns:
            List of learned facts
        """
        # Extract topic from query
        topic = self._extract_topic_from_query(user_query)

        if not topic:
            return []

        # Learn from search results
        learned_facts = self.learn_from_web_search(topic, search_results, user_query)

        return learned_facts

    def _extract_topic_from_query(self, query: str) -> str | None:
        """
        Extract topic from user query.

        Args:
            query: User query

        Returns:
            Topic name or None
        """
        # Simple extraction: first capitalized word or word before "about" or "explain"
        words = query.lower().split()

        # Try to find topic in keywords
        all_topics = self.knowledge_db.get_topics()

        for word in words:
            for topic in all_topics:
                if word in topic.lower():
                    return topic

        # Return first word if it's a valid topic
        first_word = words[0].capitalize() if words else None
        if first_word and first_word in all_topics:
            return first_word

        return None

    def clear_learning_history(self) -> None:
        """Clear learning statistics."""
        self._learning_stats = {
            "total_learned": 0,
            "topics_learned": 0,
            "average_confidence": 0.0,
            "learning_time": 0.0,
        }
