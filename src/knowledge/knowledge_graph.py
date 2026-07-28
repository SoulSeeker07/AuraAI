"""
Knowledge Graph - Builds relationships between concepts.

This module creates a graph structure of interconnected knowledge,
allowing Aura to understand semantic relationships between concepts.

Example graph:
    Python
      ├── Version
      ├── FastAPI
      │   └── ASGI
      │   └── Uvicorn
      ├── Documentation
      ├── Release Date
      └── Best Practices
    Networking
      ├── OSPF
      │   ├── Area
      │   ├── LSA
      │   └── DR/BDR
      ├── BGP
      └── Routing Protocols

Now asking "Explain Area 0" will naturally lead to OSPF.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import networkx as nx
from dataclasses import dataclass, field

from .knowledge_db import KnowledgeFact, KnowledgeDB


@dataclass
class KnowledgeNode:
    """
    A node in the knowledge graph.
    """
    id: str
    name: str
    topic: str
    facts: List[KnowledgeFact] = field(default_factory=list)
    connections: List[str] = field(default_factory=list)
    category: str = "General"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "topic": self.topic,
            "category": self.category,
            "fact_count": len(self.facts),
            "connections": self.connections,
            "metadata": self.metadata
        }


class KnowledgeGraph:
    """
    Builds and manages knowledge graphs.

    Features:
    - Create nodes for concepts
    - Connect related concepts
    - Find related concepts
    - Navigate semantic relationships
    - Graph visualization support
    - Entity extraction and linking
    """

    def __init__(self, knowledge_db: KnowledgeDB = None):
        """
        Initialize knowledge graph.

        Args:
            knowledge_db: KnowledgeDB instance
        """
        self.knowledge_db = knowledge_db or KnowledgeDB()
        self.graph: nx.DiGraph = nx.DiGraph()
        self.nodes: Dict[str, KnowledgeNode] = {}
        self._initialize_graph()

    def _initialize_graph(self):
        """Initialize graph from knowledge base."""
        # Load all facts into the graph
        topics = self.knowledge_db.get_topics()

        for topic in topics:
            facts = self.knowledge_db.get_facts_by_topic(topic)
            self._add_topic_to_graph(topic, facts)

    def _add_topic_to_graph(self, topic: str, facts: List[KnowledgeFact]) -> None:
        """
        Add a topic and its facts to the graph.

        Args:
            topic: Topic name
            facts: List of facts for this topic
        """
        # Create topic node
        node_id = f"topic:{topic}"
        if node_id not in self.nodes:
            self.nodes[node_id] = KnowledgeNode(
                id=node_id,
                name=topic,
                topic=topic,
                category="Topic"
            )
            self.graph.add_node(node_id, **self.nodes[node_id].to_dict())

        topic_node = self.nodes[node_id]

        # Add facts as sub-nodes
        for fact in facts:
            fact_node_id = f"fact:{fact.id}"
            if fact_node_id not in self.nodes:
                self.nodes[fact_node_id] = KnowledgeNode(
                    id=fact_node_id,
                    name=fact.fact[:50] + "..." if len(fact.fact) > 50 else fact.fact,
                    topic=topic,
                    category=fact.category,
                    metadata={"source": fact.source, "confidence": fact.confidence}
                )
                self.graph.add_node(fact_node_id, **self.nodes[fact_node_id].to_dict())

            fact_node = self.nodes[fact_node_id]

            # Connect fact to topic
            self.graph.add_edge(node_id, fact_node_id)
            topic_node.connections.append(fact_node_id)

            # Infer connections based on fact content
            connections = self._infer_connections(fact)
            for connected_id in connections:
                self.graph.add_edge(fact_node_id, connected_id)
                fact_node.connections.append(connected_id)

        # Connect topic to related topics
        self._connect_related_topics(topic)

    def _infer_connections(self, fact: KnowledgeFact) -> List[str]:
        """
        Infer connections based on fact content.

        Args:
            fact: KnowledgeFact to analyze

        Returns:
            List of connected node IDs
        """
        connections = []

        fact_lower = fact.fact.lower()
        topic_lower = fact.topic.lower()

        # Try to find related topics based on content
        related_topics = self.knowledge_db.search_topics(fact.fact[:50])

        for related_topic in related_topics:
            if related_topic.lower() != topic_lower:
                connected_id = f"topic:{related_topic}"
                if connected_id not in self.graph:
                    # Create node for related topic
                    self.nodes[connected_id] = KnowledgeNode(
                        id=connected_id,
                        name=related_topic,
                        topic=related_topic,
                        category="Topic"
                    )
                    self.graph.add_node(connected_id, **self.nodes[connected_id].to_dict())
                connections.append(connected_id)

        return connections

    def _connect_related_topics(self, topic: str) -> None:
        """
        Connect a topic to related topics based on shared concepts.

        Args:
            topic: Topic name to connect
        """
        topic_node_id = f"topic:{topic}"
        if topic_node_id not in self.nodes:
            return

        topic_facts = self.knowledge_db.get_facts_by_topic(topic)

        # Collect all keywords from topic facts
        keywords = set()
        for fact in topic_facts:
            keywords.update(self._extract_keywords(fact.fact))

        # Find related topics with shared keywords
        all_topics = self.knowledge_db.get_topics()

        for related_topic in all_topics:
            if related_topic == topic:
                continue

            related_facts = self.knowledge_db.get_facts_by_topic(related_topic)
            related_keywords = set()

            for fact in related_facts:
                related_keywords.update(self._extract_keywords(fact.fact))

            # Calculate similarity
            shared = keywords & related_keywords
            if len(shared) >= 2:  # At least 2 shared keywords
                related_node_id = f"topic:{related_topic}"
                self.graph.add_edge(topic_node_id, related_node_id)

    def _extract_keywords(self, text: str) -> Set[str]:
        """
        Extract keywords from text.

        Args:
            text: Text to extract keywords from

        Returns:
            Set of keywords
        """
        keywords = set()

        # Remove common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "of", "in", "on", "at", "to",
            "for", "with", "by", "from", "as", "this", "that", "these", "those",
            "it", "its", "they", "them", "their", "we", "our", "you", "your",
            "what", "which", "who", "whom", "where", "when", "why", "how",
            "new", "version", "latest", "update", "release", "feature", "update"
        }

        words = text.lower().split()
        for word in words:
            if word not in stop_words and len(word) > 2:
                keywords.add(word)

        return keywords

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """
        Get a node by ID.

        Args:
            node_id: Node ID

        Returns:
            KnowledgeNode or None
        """
        return self.nodes.get(node_id)

    def get_related_nodes(
        self,
        node_id: str,
        depth: int = 2
    ) -> List[KnowledgeNode]:
        """
        Get related nodes at a certain depth.

        Args:
            node_id: Starting node ID
            depth: Maximum depth to traverse

        Returns:
            List of related KnowledgeNode objects
        """
        if node_id not in self.graph:
            return []

        # Get neighbors at specified depth
        neighbors = set()

        def traverse(current_id: str, current_depth: int):
            if current_depth > depth:
                return

            for neighbor in self.graph.neighbors(current_id):
                if neighbor not in neighbors:
                    neighbors.add(neighbor)
                    traverse(neighbor, current_depth + 1)

        traverse(node_id, 1)

        return [self.nodes[nid] for nid in neighbors if nid in self.nodes]

    def get_topic_neighbors(self, topic: str, depth: int = 2) -> List[str]:
        """
        Get related topics for a given topic.

        Args:
            topic: Topic name
            depth: Maximum depth to traverse

        Returns:
            List of related topic names
        """
        topic_node_id = f"topic:{topic}"

        neighbors = self.get_related_nodes(topic_node_id, depth=depth)

        related_topics = []
        for node in neighbors:
            if node.id.startswith("topic:"):
                related_topics.append(node.name)

        return list(set(related_topics))

    def find_path(
        self,
        start_topic: str,
        end_topic: str,
        max_depth: int = 5
    ) -> List[str]:
        """
        Find the shortest path between two topics.

        Args:
            start_topic: Starting topic
            end_topic: Target topic
            max_depth: Maximum path depth

        Returns:
            List of topic names in path
        """
        start_id = f"topic:{start_topic}"
        end_id = f"topic:{end_topic}"

        if start_id not in self.graph or end_id not in self.graph:
            return []

        try:
            path = nx.shortest_path(self.graph, start_id, end_id)
            return [node.replace("topic:", "") for node in path]
        except nx.NetworkXNoPath:
            return []

    def get_knowledge_summary(self, topic: str) -> Dict[str, Any]:
        """
        Get a summary of knowledge for a topic.

        Args:
            topic: Topic name

        Returns:
            Dictionary with topic summary
        """
        if topic not in self.knowledge_db.get_topics():
            return {
                "topic": topic,
                "exists": False,
                "fact_count": 0,
                "related_topics": []
            }

        # Get topic facts
        facts = self.knowledge_db.get_facts_by_topic(topic)

        # Get related topics
        related_topics = self.get_topic_neighbors(topic, depth=2)

        # Calculate statistics
        categories = set()
        for fact in facts:
            categories.add(fact.category)

        return {
            "topic": topic,
            "exists": True,
            "fact_count": len(facts),
            "categories": list(categories),
            "related_topics": related_topics,
            "connections": len(self.graph.edges(f"topic:{topic}"))
        }

    def add_fact(self, fact: KnowledgeFact) -> None:
        """
        Add a fact to the graph.

        Args:
            fact: KnowledgeFact to add
        """
        # Store in database
        self.knowledge_db.add_fact(fact)

        # Add to graph
        topic_facts = self.knowledge_db.get_facts_by_topic(fact.topic)
        self._add_topic_to_graph(fact.topic, topic_facts)

    def add_facts(self, facts: List[KnowledgeFact]) -> None:
        """Add multiple facts at once."""
        for fact in facts:
            self.add_fact(fact)

    def get_concept_hierarchy(self, topic: str, max_depth: int = 3) -> Dict[str, Any]:
        """
        Get hierarchical structure of concepts for a topic.

        Args:
            topic: Topic name
            max_depth: Maximum depth to traverse

        Returns:
            Dictionary with hierarchical structure
        """
        if topic not in self.knowledge_db.get_topics():
            return {}

        def build_hierarchy(node_id: str, depth: int) -> Dict[str, Any]:
            if depth >= max_depth:
                node = self.nodes.get(node_id, KnowledgeNode(id=node_id, name=node_id))
                return {
                    "name": node.name,
                    "type": node.id.split(":")[0],
                    "fact_count": len(node.facts)
                }

            children = {}
            for neighbor_id in self.graph.neighbors(node_id):
                child_node = self.nodes.get(neighbor_id)
                if child_node:
                    children[child_node.name] = build_hierarchy(neighbor_id, depth + 1)

            node = self.nodes.get(node_id, KnowledgeNode(id=node_id, name=node_id))
            return {
                "name": node.name,
                "type": node.id.split(":")[0],
                "fact_count": len(node.facts),
                "children": children
            }

        return build_hierarchy(f"topic:{topic}", 0)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get graph statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.graph.edges()),
            "total_topics": len([n for n in self.nodes if n.startswith("topic:")]),
            "connected_components": nx.number_connected_components(self.graph),
            "density": nx.density(self.graph)
        }

    def visualize(self, output_file: str = "knowledge_graph.html") -> None:
        """
        Generate a visualization of the knowledge graph.

        Args:
            output_file: Output file path
        """
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend

        plt.figure(figsize=(20, 15))

        # Use spring layout
        pos = nx.spring_layout(self.graph, k=0.5, iterations=50)

        # Draw nodes
        nx.draw_networkx_nodes(
            self.graph, pos,
            node_size=500,
            node_color='lightblue',
            alpha=0.7
        )

        # Draw edges
        nx.draw_networkx_edges(
            self.graph, pos,
            width=1.0,
            alpha=0.5,
            edge_color='gray'
        )

        # Draw labels for topic nodes
        topic_nodes = [n for n in self.nodes if n.startswith("topic:")]
        topic_labels = {n: self.nodes[n].name for n in topic_nodes}

        nx.draw_networkx_labels(
            self.graph, pos,
            labels=topic_labels,
            font_size=8
        )

        plt.title("Aura Knowledge Graph", fontsize=16)
        plt.axis('off')
        plt.tight_layout()

        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"Knowledge graph visualization saved to {output_file}")
