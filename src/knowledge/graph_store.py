"""
Knowledge Graph Store

Manages knowledge graph with relationships between chunks.
"""

import logging
import json
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
from datetime import datetime

from .models import KnowledgeNode, KnowledgeEdge, DocumentChunk, SourceType, KnowledgeStats
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class GraphStore:
    """
    Manages knowledge graph with relationships between chunks.
    Supports both simple in-memory graph and more sophisticated graph databases.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        enable_node_creation: bool = True
    ):
        """
        Initialize graph store.

        Args:
            vector_store: Vector store instance
            enable_node_creation: Automatically create nodes when adding chunks
        """
        self.vector_store = vector_store

        # Nodes: dict of node_id -> KnowledgeNode
        self.nodes: Dict[str, KnowledgeNode] = {}

        # Edges: dict of (source_id, target_id, edge_type) -> KnowledgeEdge
        self.edges: Dict[Tuple[str, str, str], KnowledgeEdge] = {}

        # Node relationships for fast lookup
        self._outgoing_edges: Dict[str, List[KnowledgeEdge]] = defaultdict(list)
        self._incoming_edges: Dict[str, List[KnowledgeEdge]] = defaultdict(list)
        self._node_type_indices: Dict[str, List[str]] = defaultdict(list)
        self._source_indices: Dict[str, List[str]] = defaultdict(list)
        self._project_indices: Dict[str, List[str]] = defaultdict(list)

        self.enable_node_creation = enable_node_creation

        logger.info("Graph store initialized")

    def add_nodes_from_chunks(
        self,
        chunks: List[DocumentChunk]
    ) -> List[KnowledgeNode]:
        """
        Create nodes from document chunks.

        Args:
            chunks: List of document chunks

        Returns:
            List of created KnowledgeNode objects
        """
        created_nodes = []

        for chunk in chunks:
            # Check if node already exists
            if chunk.id in self.nodes:
                continue

            # Create node from chunk
            node = KnowledgeNode(
                id=chunk.id,
                content=chunk.content,
                title=chunk.title or f"Chunk {chunk.chunk_number}",
                summary=chunk.summary,
                chunk_type=chunk.chunk_type,
                source_type=chunk.source_type,
                source_file=chunk.source_file,
                project=chunk.project,
                language=chunk.language,
                tags=chunk.tags,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            self.nodes[chunk.id] = node

            # Update indices
            self._node_type_indices[node.chunk_type.value].append(node.id)
            self._source_indices[node.source_type.value].append(node.id)
            if node.project:
                self._project_indices[node.project].append(node.id)

            created_nodes.append(node)

        logger.info(f"Created {len(created_nodes)} new nodes from chunks")
        return created_nodes

    def add_edges_from_chunks(
        self,
        chunks: List[DocumentChunk],
        vector_store: VectorStore,
        similarity_threshold: float = 0.7,
        max_edges_per_node: int = 10
    ) -> int:
        """
        Create edges between chunks based on semantic similarity.

        Args:
            chunks: List of document chunks
            vector_store: Vector store for semantic similarity
            similarity_threshold: Minimum similarity to create edge
            max_edges_per_node: Maximum edges per node

        Returns:
            Number of edges created
        """
        if not self.enable_node_creation:
            return 0

        logger.info(f"Creating edges between {len(chunks)} chunks...")

        edge_count = 0

        for chunk in chunks:
            if chunk.id not in self.nodes:
                # Create node if it doesn't exist
                node = KnowledgeNode(
                    id=chunk.id,
                    content=chunk.content,
                    title=chunk.title or f"Chunk {chunk.chunk_number}",
                    summary=chunk.summary,
                    chunk_type=chunk.chunk_type,
                    source_type=chunk.source_type,
                    source_file=chunk.source_file,
                    project=chunk.project,
                    language=chunk.language,
                    tags=chunk.tags,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.nodes[chunk.id] = node

            # Find similar chunks
            similar_chunks = vector_store.semantic_search(
                chunk.content,
                top_k=max_edges_per_node + 1,  # +1 to exclude self
                min_similarity=similarity_threshold
            )

            for similar_chunk, score in similar_chunks:
                if similar_chunk.id == chunk.id:
                    continue

                # Create edge
                edge = KnowledgeEdge(
                    source_id=chunk.id,
                    target_id=similar_chunk.id,
                    edge_type=KnowledgeEdge.EdgeType.RELATED,
                    weight=score,
                    description=f"Semantic similarity: {score:.3f}",
                    created_at=datetime.now()
                )

                # Check if edge already exists
                edge_key = (edge.source_id, edge.target_id, edge.edge_type.value)
                if edge_key not in self.edges:
                    self.edges[edge_key] = edge

                    # Update adjacency lists
                    self._outgoing_edges[edge.source_id].append(edge)
                    self._incoming_edges[edge.target_id].append(edge)

                    edge_count += 1

        logger.info(f"Created {edge_count} edges")
        return edge_count

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Tuple[KnowledgeNode, KnowledgeEdge]]:
        """
        Get neighbors of a node.

        Args:
            node_id: Node ID
            edge_type: Optional edge type filter
            limit: Maximum number of neighbors

        Returns:
            List of (neighbor_node, edge) tuples
        """
        neighbors = []

        if node_id not in self.nodes:
            return neighbors

        for edge in self._outgoing_edges.get(node_id, []):
            if edge_type is None or edge.edge_type.value == edge_type:
                neighbor = self.nodes.get(edge.target_id)
                if neighbor:
                    neighbors.append((neighbor, edge))

        # Sort by edge weight (descending)
        neighbors.sort(key=lambda x: x[1].weight, reverse=True)

        return neighbors[:limit]

    def get_related_nodes(
        self,
        node_id: str,
        max_depth: int = 2
    ) -> Set[str]:
        """
        Get all nodes reachable from a node within max_depth hops.

        Args:
            node_id: Starting node ID
            max_depth: Maximum depth to traverse

        Returns:
            Set of reachable node IDs
        """
        reachable = set()
        queue = [(node_id, 0)]
        visited = {node_id}

        while queue:
            current_id, depth = queue.pop(0)

            if depth > max_depth:
                continue

            # Get neighbors
            neighbors = self.get_neighbors(current_id, limit=100)

            for neighbor, edge in neighbors:
                if neighbor.id not in visited:
                    visited.add(neighbor.id)
                    reachable.add(neighbor.id)
                    queue.append((neighbor.id, depth + 1))

        return reachable

    def get_nodes_by_type(
        self,
        chunk_type: str
    ) -> List[KnowledgeNode]:
        """
        Get nodes by chunk type.

        Args:
            chunk_type: Chunk type (SECTION, FUNCTION, CLASS, etc.)

        Returns:
            List of matching nodes
        """
        return [
            self.nodes[node_id]
            for node_id in self._node_type_indices.get(chunk_type, [])
        ]

    def get_nodes_by_source(
        self,
        source_type: str
    ) -> List[KnowledgeNode]:
        """
        Get nodes by source type.

        Args:
            source_type: Source type (PDF, MARKDOWN, PYTHON, etc.)

        Returns:
            List of matching nodes
        """
        return [
            self.nodes[node_id]
            for node_id in self._source_indices.get(source_type, [])
        ]

    def get_nodes_by_project(
        self,
        project: str
    ) -> List[KnowledgeNode]:
        """
        Get nodes by project.

        Args:
            project: Project name

        Returns:
            List of matching nodes
        """
        return [
            self.nodes[node_id]
            for node_id in self._project_indices.get(project, [])
        ]

    def get_nodes_by_tag(
        self,
        tag: str
    ) -> List[KnowledgeNode]:
        """
        Get nodes by tag.

        Args:
            tag: Tag value

        Returns:
            List of matching nodes
        """
        matching_nodes = []

        for node in self.nodes.values():
            if tag in node.tags:
                matching_nodes.append(node)

        return matching_nodes

    def search_graph(
        self,
        query: str,
        top_k: int = 10,
        include_neighbors: bool = True,
        max_depth: int = 2
    ) -> List[Tuple[KnowledgeNode, float, int]]:
        """
        Search graph using node content and neighbor information.

        Args:
            query: Search query
            top_k: Number of results to return
            include_neighbors: Include neighboring nodes
            max_depth: Maximum depth for neighbor search

        Returns:
            List of (node, score, depth) tuples
        """
        # Simple search using vector store
        results = []

        # This would integrate with a graph-aware search
        # For now, use simple node content search
        # TODO: Implement graph-aware search

        return results

    def get_statistics(self) -> KnowledgeStats:
        """
        Get graph statistics.

        Returns:
            KnowledgeStats object
        """
        # Count by source type
        by_source_type = {}
        for node in self.nodes.values():
            source_type = node.source_type.value
            by_source_type[source_type] = by_source_type.get(source_type, 0) + 1

        # Count by project
        by_project = {}
        for node in self.nodes.values():
            project = node.project
            if project:
                by_project[project] = by_project.get(project, 0) + 1

        # Count by chunk type
        by_chunk_type = {}
        for node in self.nodes.values():
            chunk_type = node.chunk_type.value
            by_chunk_type[chunk_type] = by_chunk_type.get(chunk_type, 0) + 1

        # Count by edge type
        by_edge_type = {}
        for edge in self.edges.values():
            edge_type = edge.edge_type.value
            by_edge_type[edge_type] = by_edge_type.get(edge_type, 0) + 1

        return KnowledgeStats(
            total_nodes=len(self.nodes),
            total_documents=len(set(node.source_file for node in self.nodes.values())),
            total_edges=len(self.edges),
            by_source_type=by_source_type,
            by_project=by_project,
            by_chunk_type=by_chunk_type
        )

    def get_node_by_id(self, node_id: str) -> Optional[KnowledgeNode]:
        """
        Get node by ID.

        Args:
            node_id: Node ID

        Returns:
            KnowledgeNode or None
        """
        return self.nodes.get(node_id)

    def get_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: Optional[str] = None
    ) -> Optional[KnowledgeEdge]:
        """
        Get edge between two nodes.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Edge type

        Returns:
            KnowledgeEdge or None
        """
        if edge_type:
            key = (source_id, target_id, edge_type)
        else:
            # Find any edge between the two nodes
            for key in self.edges.keys():
                if key[0] == source_id and key[1] == target_id:
                    return self.edges[key]

        return self.edges.get(key)

    def get_all_nodes(self) -> List[KnowledgeNode]:
        """
        Get all nodes.

        Returns:
            List of all nodes
        """
        return list(self.nodes.values())

    def get_all_edges(self) -> List[KnowledgeEdge]:
        """
        Get all edges.

        Returns:
            List of all edges
        """
        return list(self.edges.values())

    def clear(self):
        """Clear all data from graph store."""
        self.nodes.clear()
        self.edges.clear()
        self._outgoing_edges.clear()
        self._incoming_edges.clear()
        self._node_type_indices.clear()
        self._source_indices.clear()
        self._project_indices.clear()

        logger.info("Graph store cleared")

    def save_to_disk(self, path: str):
        """
        Save graph to disk.

        Args:
            path: Path to save graph
        """
        try:
            data = {
                'nodes': [node.to_dict() for node in self.nodes.values()],
                'edges': [edge.to_dict() for edge in self.edges.values()]
            }

            with open(path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Graph saved to {path}")

        except Exception as e:
            logger.error(f"Error saving graph: {e}")

    def load_from_disk(self, path: str):
        """
        Load graph from disk.

        Args:
            path: Path to load graph from
        """
        try:
            with open(path, 'r') as f:
                data = json.load(f)

            self.nodes.clear()
            self.edges.clear()

            # Load nodes
            for node_data in data.get('nodes', []):
                node = KnowledgeNode(
                    id=node_data['id'],
                    content=node_data['content'],
                    title=node_data['title'],
                    summary=node_data.get('summary'),
                    chunk_type=node_data['chunk_type'],
                    source_type=node_data['source_type'],
                    source_file=node_data.get('source_file'),
                    project=node_data.get('project'),
                    language=node_data.get('language'),
                    tags=node_data.get('tags', []),
                    created_at=datetime.fromisoformat(node_data['created_at']),
                    updated_at=datetime.fromisoformat(node_data['updated_at'])
                )
                self.nodes[node.id] = node

            # Load edges
            for edge_data in data.get('edges', []):
                edge = KnowledgeEdge(
                    source_id=edge_data['source_id'],
                    target_id=edge_data['target_id'],
                    edge_type=edge_data['edge_type'],
                    weight=edge_data['weight'],
                    description=edge_data.get('description'),
                    created_at=datetime.fromisoformat(edge_data['created_at'])
                )
                key = (edge.source_id, edge.target_id, edge.edge_type.value)
                self.edges[key] = edge

            # Recreate indices
            self._rebuild_indices()

            logger.info(f"Graph loaded from {path}")

        except Exception as e:
            logger.error(f"Error loading graph: {e}")

    def _rebuild_indices(self):
        """Rebuild all indices from nodes and edges."""
        self._outgoing_edges.clear()
        self._incoming_edges.clear()
        self._node_type_indices.clear()
        self._source_indices.clear()
        self._project_indices.clear()

        for node in self.nodes.values():
            self._node_type_indices[node.chunk_type.value].append(node.id)
            self._source_indices[node.source_type.value].append(node.id)
            if node.project:
                self._project_indices[node.project].append(node.id)

        for edge in self.edges.values():
            self._outgoing_edges[edge.source_id].append(edge)
            self._incoming_edges[edge.target_id].append(edge)
