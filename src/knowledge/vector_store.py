"""
Knowledge Vector Store

Manages document embeddings in vector database.
"""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pickle

from .models import DocumentChunk, EmbeddingProvider, SourceType, KnowledgeStats
from .embedding_manager import EmbeddingManager

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Manages embeddings in vector database.
    Supports both local and cloud-based vector stores.
    """

    def __init__(
        self,
        store_path: str = "data/knowledge_store",
        embedding_manager: Optional[EmbeddingManager] = None
    ):
        """
        Initialize vector store.

        Args:
            store_path: Path to store embeddings and metadata
            embedding_manager: Embedding manager instance
        """
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        self.embedding_manager = embedding_manager or EmbeddingManager()

        # Load existing store if available
        self.embeddings: List[List[float]] = []
        self.chunks: List[DocumentChunk] = []
        self.metadata: List[Dict[str, Any]] = []
        self._load_store()

        logger.info(f"Vector store initialized at {self.store_path}")

    def add_chunks(
        self,
        chunks: List[DocumentChunk],
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Add chunks to store with embeddings.

        Args:
            chunks: List of document chunks
            batch_size: Batch size for embeddings

        Returns:
            Statistics dictionary
        """
        logger.info(f"Adding {len(chunks)} chunks to vector store")

        new_embeddings = []
        new_chunks = []
        new_metadata = []

        # Create embeddings
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_texts = [chunk.content for chunk in batch]

            try:
                embeddings = self.embedding_manager.get_embeddings(batch_texts)
            except Exception as e:
                logger.error(f"Error creating embeddings: {e}")
                continue

            new_embeddings.extend(embeddings)
            new_chunks.extend(batch)
            new_metadata.extend([chunk.to_dict() for chunk in batch])

        # Save to store
        self.embeddings.extend(new_embeddings)
        self.chunks.extend(new_chunks)
        self.metadata.extend(new_metadata)

        self._save_store()

        stats = {
            'total_chunks': len(self.chunks),
            'new_chunks_added': len(new_chunks),
            'embeddings_generated': len(new_embeddings)
        }

        logger.info(f"Added {len(new_chunks)} chunks. Total: {len(self.chunks)}")
        return stats

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for similar chunks.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters (project, source_type, etc.)

        Returns:
            List of (chunk, score) tuples
        """
        if not self.embeddings:
            logger.warning("Vector store is empty")
            return []

        # Get query embedding
        query_embedding = self.embedding_manager.get_embedding(query)

        # Filter chunks if filters provided
        if filters:
            filtered_indices = self._apply_filters(filters)
        else:
            filtered_indices = list(range(len(self.chunks)))

        if not filtered_indices:
            return []

        # Compute similarity scores
        scores = []
        for idx in filtered_indices:
            similarity = self._cosine_similarity(query_embedding, self.embeddings[idx])
            scores.append((idx, similarity))

        # Sort by score and get top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        top_results = scores[:top_k]

        # Return chunks with scores
        results = []
        for idx, score in top_results:
            results.append((self.chunks[idx], score))

        return results

    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[DocumentChunk]:
        """
        Semantic search (filter by minimum similarity).

        Args:
            query: Search query
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity

        Returns:
            List of matching chunks
        """
        results = self.search(query, top_k, None)
        return [chunk for chunk, score in results if score >= min_similarity]

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        keyword_weight: float = 0.3
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Hybrid search (semantic + keyword).

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters
            keyword_weight: Weight for keyword matching

        Returns:
            List of (chunk, score) tuples
        """
        # Semantic search
        semantic_results = self.search(query, top_k * 2, filters)

        # Keyword search
        keyword_results = self._keyword_search(query, top_k * 2, filters)

        # Combine and re-rank
        combined = {}
        for chunk, score in semantic_results:
            chunk_id = chunk.id
            combined[chunk_id] = {
                'chunk': chunk,
                'semantic_score': score,
                'keyword_scores': {}
            }

        for chunk, score in keyword_results:
            chunk_id = chunk.id
            if chunk_id in combined:
                combined[chunk_id]['keyword_scores'][chunk] = score

        # Combine scores
        final_results = []
        for chunk_id, data in combined.items():
            semantic_score = data['semantic_score']
            keyword_scores = data['keyword_scores']

            # Weighted combination
            if keyword_scores:
                max_keyword = max(keyword_scores.values())
                combined_score = (semantic_score * (1 - keyword_weight) +
                                max_keyword * keyword_weight)
            else:
                combined_score = semantic_score

            final_results.append((data['chunk'], combined_score))

        # Sort and return top_k
        final_results.sort(key=lambda x: x[1], reverse=True)
        return final_results[:top_k]

    def _keyword_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Keyword-based search.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters

        Returns:
            List of (chunk, score) tuples
        """
        # Simple token matching
        query_tokens = set(query.lower().split())
        results = []

        for idx, chunk in enumerate(self.chunks):
            # Apply filters
            if filters:
                if not self._chunk_matches_filters(chunk, filters):
                    continue

            # Token matching
            chunk_tokens = set(chunk.content.lower().split())
            intersection = query_tokens & chunk_tokens
            score = len(intersection) / max(len(query_tokens), 1)

            if score > 0:
                results.append((chunk, score))

        # Sort and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _apply_filters(
        self,
        filters: Dict[str, Any]
    ) -> List[int]:
        """
        Apply filters to get matching indices.

        Args:
            filters: Filter dictionary

        Returns:
            List of matching indices
        """
        matching_indices = []

        for idx, chunk in enumerate(self.chunks):
            if self._chunk_matches_filters(chunk, filters):
                matching_indices.append(idx)

        return matching_indices

    def _chunk_matches_filters(
        self,
        chunk: DocumentChunk,
        filters: Dict[str, Any]
    ) -> bool:
        """
        Check if chunk matches filters.

        Args:
            chunk: Document chunk
            filters: Filter dictionary

        Returns:
            True if chunk matches
        """
        for key, value in filters.items():
            if hasattr(chunk, key):
                chunk_value = getattr(chunk, key)
                if chunk_value != value:
                    return False
        return True

    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity
        """
        import math

        if len(vec1) != len(vec2):
            logger.warning(f"Vector lengths differ: {len(vec1)} vs {len(vec2)}")
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _save_store(self):
        """Save store to disk."""
        try:
            data = {
                'embeddings': self.embeddings,
                'metadata': self.metadata
            }

            # Save chunks separately (they're objects, not dicts)
            chunks_path = self.store_path / 'chunks.pkl'
            with open(chunks_path, 'wb') as f:
                pickle.dump(self.chunks, f)

            # Save embeddings and metadata
            embeddings_path = self.store_path / 'embeddings.json'
            with open(embeddings_path, 'w') as f:
                json.dump(data, f)

        except Exception as e:
            logger.error(f"Error saving vector store: {e}")

    def _load_store(self):
        """Load store from disk."""
        try:
            chunks_path = self.store_path / 'chunks.pkl'
            if chunks_path.exists():
                with open(chunks_path, 'rb') as f:
                    self.chunks = pickle.load(f)

            embeddings_path = self.store_path / 'embeddings.json'
            if embeddings_path.exists():
                with open(embeddings_path, 'r') as f:
                    data = json.load(f)
                    self.embeddings = data.get('embeddings', [])
                    self.metadata = data.get('metadata', [])

            logger.info(f"Loaded {len(self.chunks)} chunks from store")

        except Exception as e:
            logger.error(f"Error loading vector store: {e}")

    def delete_chunks(self, chunk_ids: List[str]):
        """
        Delete chunks from store.

        Args:
            chunk_ids: List of chunk IDs to delete
        """
        indices_to_delete = []

        for i, chunk in enumerate(self.chunks):
            if chunk.id in chunk_ids:
                indices_to_delete.append(i)

        # Delete from end to start to avoid index shifting
        for idx in sorted(indices_to_delete, reverse=True):
            del self.chunks[idx]
            del self.embeddings[idx]
            del self.metadata[idx]

        self._save_store()
        logger.info(f"Deleted {len(indices_to_delete)} chunks")

    def get_stats(self) -> KnowledgeStats:
        """
        Get store statistics.

        Returns:
            KnowledgeStats object
        """
        # Count by source type
        by_source_type = {}
        for chunk in self.chunks:
            source_type = chunk.source_type.value
            by_source_type[source_type] = by_source_type.get(source_type, 0) + 1

        # Count by project
        by_project = {}
        for chunk in self.chunks:
            project = chunk.project
            if project:
                by_project[project] = by_project.get(project, 0) + 1

        # Count by chunk type
        by_chunk_type = {}
        for chunk in self.chunks:
            chunk_type = chunk.chunk_type.value
            by_chunk_type[chunk_type] = by_chunk_type.get(chunk_type, 0) + 1

        return KnowledgeStats(
            total_chunks=len(self.chunks),
            total_documents=len(set(chunk.source_file for chunk in self.chunks)),
            total_nodes=len(self.chunks),  # Simplified for now
            total_edges=0,  # Simplified for now
            by_source_type=by_source_type,
            by_project=by_project,
            by_chunk_type=by_chunk_type
        )

    def clear(self):
        """Clear all data from store."""
        self.embeddings = []
        self.chunks = []
        self.metadata = []
        self._save_store()
        logger.info("Vector store cleared")
