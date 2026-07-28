"""
Topic Memory - Organizes knowledge by topic and sub-topics.

This module groups related facts into topic trees, allowing Aura to understand
concept hierarchies and provide structured answers.

Topic structure example:
    Python
      ├── Version
      ├── Release Date
      ├── New Features
      ├── Documentation
      └── Best Practices

Networking
  ├── OSPF
  │   ├── Area
  │   ├── LSA
  │   └── DR/BDR
  ├── BGP
  └── Routing Protocols

This helps Aura answer:
  - "What's new in Python 3.15?" → Uses Python/Version/3.15
  - "Explain OSPF Area 0" → Uses OSPF/Area/0
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .knowledge_db import KnowledgeFact, KnowledgeDB


@dataclass
class TopicNode:
    """
    A node in the topic tree structure.
    """
    name: str
    parent: Optional['TopicNode'] = None
    facts: List[KnowledgeFact] = field(default_factory=list)
    subtopics: Dict[str, 'TopicNode'] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_fact(self, fact: KnowledgeFact) -> None:
        """Add a fact to this topic node."""
        self.facts.append(fact)

    def add_subtopic(self, name: str, node: 'TopicNode' = None) -> 'TopicNode':
        """Add or get a subtopic by name."""
        if node is None:
            node = TopicNode(name=name, parent=self)
        self.subtopics[name] = node
        return node

    def get_fact(self, fact_text: str) -> Optional[KnowledgeFact]:
        """Get a specific fact by its text."""
        for fact in self.facts:
            if fact.fact.lower() == fact_text.lower():
                return fact
        return None

    def get_subtopic(self, name: str) -> Optional['TopicNode']:
        """Get a subtopic by name."""
        return self.subtopics.get(name)

    def get_all_facts(self) -> List[KnowledgeFact]:
        """Get all facts in this topic and all subtopics."""
        facts = self.facts.copy()
        for subtopic in self.subtopics.values():
            facts.extend(subtopic.get_all_facts())
        return facts

    def get_all_subtopic_names(self) -> List[str]:
        """Get all subtopic names (including nested)."""
        names = list(self.subtopics.keys())
        for subtopic in self.subtopics.values():
            names.extend(subtopic.get_all_subtopic_names())
        return names

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "facts": [f.to_dict() for f in self.facts],
            "subtopics": {name: subtopic.to_dict() for name, subtopic in self.subtopics.items()},
            "metadata": self.metadata
        }


class TopicMemory:
    """
    Organizes knowledge into topic trees.

    Features:
    - Group facts by topic and subtopics
    - Build hierarchical knowledge structures
    - Navigate by topic hierarchy
    - Track relationships between topics
    - Support dynamic topic creation
    """

    def __init__(self, knowledge_db: KnowledgeDB = None):
        """
        Initialize topic memory.

        Args:
            knowledge_db: KnowledgeDB instance (optional, will create if not provided)
        """
        self.knowledge_db = knowledge_db or KnowledgeDB()
        self.topic_tree: Dict[str, TopicNode] = {}
        self._initialize_from_db()

    def _initialize_from_db(self):
        """Load existing knowledge from database into topic tree."""
        topics = self.knowledge_db.get_topics()

        for topic in topics:
            self._build_topic_hierarchy(topic)

    def _build_topic_hierarchy(self, topic: str, path: List[str] = None) -> TopicNode:
        """
        Build a topic hierarchy tree.

        Args:
            topic: The topic name
            path: Path to this topic (for recursive calls)

        Returns:
            TopicNode representing this topic
        """
        if path is None:
            path = []

        current_path = path + [topic]

        # Create or get topic node
        if topic not in self.topic_tree:
            self.topic_tree[topic] = TopicNode(name=topic, parent=None)

        current_node = self.topic_tree[topic]

        # Add all facts for this topic
        facts = self.knowledge_db.get_facts_by_topic(topic)
        for fact in facts:
            # Try to infer subtopic from fact content
            subtopic = self._infer_subtopic(fact)
            if subtopic:
                subtopic_node = current_node.add_subtopic(subtopic)
                subtopic_node.add_fact(fact)
            else:
                current_node.add_fact(fact)

        # Recursively build subtopic hierarchies
        # Note: This is a simplified implementation
        # A more sophisticated version would parse fact content for structure

        return current_node

    def _infer_subtopic(self, fact: KnowledgeFact) -> Optional[str]:
        """
        Try to infer subtopic from fact content.

        Args:
            fact: KnowledgeFact to analyze

        Returns:
            Suggested subtopic name or None
        """
        fact_lower = fact.fact.lower()
        topic_lower = fact.topic.lower()

        # Common subtopic patterns
        patterns = {
            "version": ["version", "version"],
            "features": ["new", "feature", "release", "introduction"],
            "documentation": ["docs", "documentation", "guide", "tutorial"],
            "api": ["api", "function", "method", "class", "example"],
            "security": ["security", "vulnerability", "patch", "fix"],
            "performance": ["performance", "optimization", "speed"],
            "configuration": ["config", "configuration", "setup", "install"],
            "best practices": ["best practice", "guideline", "recommendation"],
        }

        for subtopic, keywords in patterns.items():
            if any(keyword in fact_lower for keyword in keywords):
                return subtopic

        return None

    def get_topic(self, topic: str) -> Optional[TopicNode]:
        """
        Get a topic node by name.

        Args:
            topic: Topic name

        Returns:
            TopicNode or None if not found
        """
        return self.topic_tree.get(topic)

    def get_facts(self, topic: str) -> List[KnowledgeFact]:
        """
        Get all facts for a topic.

        Args:
            topic: Topic name

        Returns:
            List of KnowledgeFact objects
        """
        topic_node = self.get_topic(topic)
        if topic_node:
            return topic_node.get_all_facts()
        return []

    def get_topic_facts(self, topic: str, subtopic: Optional[str] = None) -> List[KnowledgeFact]:
        """
        Get facts for a specific topic and optionally subtopic.

        Args:
            topic: Topic name
            subtopic: Subtopic name (optional)

        Returns:
            List of KnowledgeFact objects
        """
        topic_node = self.get_topic(topic)
        if not topic_node:
            return []

        if subtopic:
            subtopic_node = topic_node.get_subtopic(subtopic)
            if subtopic_node:
                return subtopic_node.get_all_facts()

        return topic_node.get_all_facts()

    def add_fact(self, fact: KnowledgeFact) -> None:
        """
        Add a fact to the topic memory.

        Args:
            fact: KnowledgeFact to add
        """
        # Store in database
        self.knowledge_db.add_fact(fact)

        # Update topic tree
        if fact.topic not in self.topic_tree:
            self.topic_tree[fact.topic] = TopicNode(name=fact.topic, parent=None)

        topic_node = self.topic_tree[fact.topic]

        # Try to infer subtopic
        subtopic = self._infer_subtopic(fact)
        if subtopic:
            subtopic_node = topic_node.add_subtopic(subtopic)
            subtopic_node.add_fact(fact)
        else:
            topic_node.add_fact(fact)

    def add_facts(self, facts: List[KnowledgeFact]) -> None:
        """Add multiple facts at once."""
        for fact in facts:
            self.add_fact(fact)

    def get_all_topics(self) -> List[str]:
        """
        Get all available topics.

        Returns:
            List of topic names
        """
        return list(self.topic_tree.keys())

    def get_subtopics(self, topic: str) -> List[str]:
        """
        Get all subtopics for a specific topic.

        Args:
            topic: Topic name

        Returns:
            List of subtopic names
        """
        topic_node = self.get_topic(topic)
        if not topic_node:
            return []

        return list(topic_node.subtopics.keys())

    def get_topic_hierarchy(self, topic: str, max_depth: int = 3) -> Dict[str, Any]:
        """
        Get hierarchical structure for a topic.

        Args:
            topic: Topic name
            max_depth: Maximum depth to traverse

        Returns:
            Dictionary representation of topic hierarchy
        """
        topic_node = self.get_topic(topic)
        if not topic_node:
            return {}

        def build_hierarchy(node: TopicNode, depth: int) -> Dict[str, Any]:
            if depth >= max_depth:
                return {
                    "name": node.name,
                    "fact_count": len(node.facts),
                    "subtopic_count": len(node.subtopics)
                }

            children = {}
            for subtopic_name, subtopic_node in node.subtopics.items():
                children[subtopic_name] = build_hierarchy(subtopic_node, depth + 1)

            return {
                "name": node.name,
                "fact_count": len(node.facts),
                "subtopic_count": len(node.subtopics),
                "subtopics": children
            }

        return build_hierarchy(topic_node, 0)

    def get_topic_stats(self, topic: str) -> Dict[str, Any]:
        """
        Get statistics about a topic.

        Args:
            topic: Topic name

        Returns:
            Dictionary with statistics
        """
        facts = self.get_facts(topic)

        subtopics_used = set()
        for fact in facts:
            subtopic = self._infer_subtopic(fact)
            if subtopic:
                subtopics_used.add(subtopic)

        return {
            "topic": topic,
            "total_facts": len(facts),
            "unique_subtopics": len(subtopics_used),
            "subtopics": list(subtopics_used)
        }

    def get_all_topic_stats(self) -> List[Dict[str, Any]]:
        """
        Get statistics for all topics.

        Returns:
            List of statistics dictionaries
        """
        stats = []
        for topic in self.get_all_topics():
            stats.append(self.get_topic_stats(topic))
        return sorted(stats, key=lambda x: x["total_facts"], reverse=True)

    def search_topics(self, query: str) -> List[str]:
        """
        Search for topics matching a query.

        Args:
            query: Search query

        Returns:
            List of matching topic names
        """
        query_lower = query.lower()
        matching_topics = []

        for topic in self.get_all_topics():
            if query_lower in topic.lower():
                matching_topics.append(topic)
            else:
                # Search in subtopics
                for subtopic in self.get_topic(topic).get_all_subtopic_names():
                    if query_lower in subtopic.lower():
                        matching_topics.append(topic)
                        break

        return matching_topics

    def merge_topic(self, old_topic: str, new_topic: str) -> bool:
        """
        Merge facts from one topic into another.

        Args:
            old_topic: Source topic
            new_topic: Target topic

        Returns:
            True if merged successfully
        """
        if old_topic not in self.topic_tree or new_topic not in self.topic_tree:
            return False

        source_node = self.topic_tree[old_topic]
        target_node = self.topic_tree[new_topic]

        # Move all facts
        for fact in source_node.facts:
            target_node.add_fact(fact)

        # Move subtopics
        for subtopic_name, subtopic_node in source_node.subtopics.items():
            subtopic_node.parent = target_node
            target_node.subtopics[subtopic_name] = subtopic_node

        # Delete old topic node
        del self.topic_tree[old_topic]

        return True

    def create_topic(self, topic_name: str) -> TopicNode:
        """
        Create a new topic node.

        Args:
            topic_name: Name of the topic

        Returns:
            Newly created TopicNode
        """
        if topic_name not in self.topic_tree:
            self.topic_tree[topic_name] = TopicNode(name=topic_name, parent=None)

        return self.topic_tree[topic_name]

    def add_subtopic(self, topic: str, subtopic_name: str) -> TopicNode:
        """
        Add a subtopic to a topic.

        Args:
            topic: Parent topic name
            subtopic_name: Name of the subtopic

        Returns:
            Created TopicNode
        """
        topic_node = self.create_topic(topic)
        return topic_node.add_subtopic(subtopic_name)
