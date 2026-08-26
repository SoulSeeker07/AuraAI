"""
Knowledge Retrieval Engine

Combines vector search, keyword search, and graph search for intelligent knowledge retrieval.
"""

import logging
from datetime import datetime
from typing import Any

from .chunker import Chunker
from .graph_store import GraphStore
from .models import Citation, RetrievalMode, RetrievalResult, SourceType
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """
    Main retrieval engine for Aura's knowledge base.
    Combines semantic, keyword, and graph search strategies.
    """

    def __init__(
        self, vector_store: VectorStore, graph_store: GraphStore, chunker: Chunker
    ):
        """
        Initialize retrieval engine.

        Args:
            vector_store: Vector store instance
            graph_store: Graph store instance
            chunker: Chunker instance
        """
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.chunker = chunker

        logger.info("Retrieval engine initialized")

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        mode: RetrievalMode = RetrievalMode.HYBRID,
        filters: dict[str, Any] | None = None,
        include_citations: bool = True,
    ) -> list[RetrievalResult]:
        """
        Retrieve knowledge chunks based on query.

        Args:
            query: Search query
            top_k: Number of results to return
            mode: Retrieval mode (SEMANTIC, KEYWORD, HYBRID, GRAPH)
            filters: Optional filters (project, source_type, etc.)
            include_citations: Whether to include citations

        Returns:
            List of RetrievalResult objects
        """
        logger.info(f"Retrieving {top_k} results for query: {query}")

        results = []

        if mode == RetrievalMode.SEMANTIC:
            results = self._semantic_retrieval(query, top_k, filters)
        elif mode == RetrievalMode.KEYWORD:
            results = self._keyword_retrieval(query, top_k, filters)
        elif mode == RetrievalMode.HYBRID:
            results = self._hybrid_retrieval(query, top_k, filters)
        elif mode == RetrievalMode.GRAPH:
            results = self._graph_retrieval(query, top_k, filters)

        # Add citations if requested
        if include_citations:
            results = self._add_citations(results)

        logger.info(f"Retrieved {len(results)} results")
        return results

    def _semantic_retrieval(
        self, query: str, top_k: int, filters: dict[str, Any] | None
    ) -> list[RetrievalResult]:
        """
        Semantic search using vector similarity.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of RetrievalResult objects
        """
        results = self.vector_store.search(query, top_k, filters)

        return [
            RetrievalResult(
                chunk=chunk, score=score, sources=["Semantic similarity"], rank=i + 1
            )
            for i, (chunk, score) in enumerate(results)
        ]

    def _keyword_retrieval(
        self, query: str, top_k: int, filters: dict[str, Any] | None
    ) -> list[RetrievalResult]:
        """
        Keyword search using token matching.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of RetrievalResult objects
        """
        results = self.vector_store._keyword_search(query, top_k, filters)

        return [
            RetrievalResult(
                chunk=chunk, score=score, sources=["Keyword matching"], rank=i + 1
            )
            for i, (chunk, score) in enumerate(results)
        ]

    def _hybrid_retrieval(
        self, query: str, top_k: int, filters: dict[str, Any] | None
    ) -> list[RetrievalResult]:
        """
        Hybrid search combining semantic and keyword.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of RetrievalResult objects
        """
        # Get results from both methods
        semantic_results = self.vector_store.hybrid_search(
            query, top_k * 2, filters, keyword_weight=0.3
        )

        keyword_results = self.vector_store._keyword_search(query, top_k * 2, filters)

        # Combine results
        combined = {}
        for chunk, score in semantic_results:
            if chunk.id not in combined:
                combined[chunk.id] = {
                    "chunk": chunk,
                    "semantic_score": score,
                    "keyword_score": 0.0,
                }

        for chunk, score in keyword_results:
            if chunk.id in combined:
                combined[chunk.id]["keyword_score"] = score
            else:
                combined[chunk.id] = {
                    "chunk": chunk,
                    "semantic_score": 0.0,
                    "keyword_score": score,
                }

        # Weighted combination of scores
        final_results = []
        for chunk_id, data in combined.items():
            semantic_score = data["semantic_score"]
            keyword_score = data["keyword_score"]
            combined_score = semantic_score * 0.7 + keyword_score * 0.3
            final_results.append((data["chunk"], combined_score))

        # Sort and return top_k
        final_results.sort(key=lambda x: x[1], reverse=True)

        return [
            RetrievalResult(
                chunk=chunk, score=score, sources=["Hybrid search"], rank=i + 1
            )
            for i, (chunk, score) in enumerate(final_results[:top_k])
        ]

    def _graph_retrieval(
        self, query: str, top_k: int, filters: dict[str, Any] | None
    ) -> list[RetrievalResult]:
        """
        Graph-aware search using knowledge graph.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of RetrievalResult objects
        """
        # Get initial semantic results
        semantic_results = self.vector_store.search(query, top_k * 2, filters)

        # Expand results using graph
        expanded_results = set()

        for chunk, score in semantic_results:
            # Get related nodes
            related_ids = self.graph_store.get_related_nodes(chunk.id, max_depth=2)

            # Add related nodes
            for related_id in related_ids:
                if related_id in self.graph_store.nodes:
                    expanded_results.add((self.graph_store.nodes[related_id], score))

        # Convert to results
        results = list(expanded_results)

        return [
            RetrievalResult(
                chunk=chunk, score=score, sources=["Graph expansion"], rank=i + 1
            )
            for i, (chunk, score) in enumerate(results[:top_k])
        ]

    def _add_citations(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """
        Add citations to results.

        Args:
            results: List of RetrievalResult objects

        Returns:
            List of RetrievalResult objects with citations
        """
        for result in results:
            # Create citation
            citation = Citation(
                chunk_id=result.chunk.id,
                title=result.chunk.title,
                source=result.chunk.source_file,
                source_type=result.chunk.source_type.value,
                project=result.chunk.project,
                page=result.chunk.page,
                line=result.chunk.line,
                retrieval_date=datetime.now(),
            )

            result.citation = citation
            result.citations = [citation]

        return results

    def retrieve_with_context(
        self,
        query: str,
        top_k: int = 10,
        mode: RetrievalMode = RetrievalMode.HYBRID,
        filters: dict[str, Any] | None = None,
        include_neighbors: bool = True,
    ) -> dict[str, Any]:
        """
        Retrieve knowledge chunks with additional context.

        Args:
            query: Search query
            top_k: Number of results
            mode: Retrieval mode
            filters: Optional filters
            include_neighbors: Include neighbor information

        Returns:
            Dictionary with chunks and context
        """
        # Get base results
        chunks = self.retrieve(query, top_k, mode, filters)

        # Add neighbor information if requested
        if include_neighbors:
            for chunk in chunks:
                neighbors = self.graph_store.get_neighbors(chunk.chunk.id, limit=3)

                chunk.neighbors = [
                    {
                        "id": neighbor[0].id,
                        "title": neighbor[0].title,
                        "content": neighbor[0].content[:200] + "...",
                        "score": neighbor[1].weight,
                    }
                    for neighbor in neighbors
                ]

        return {"query": query, "results": chunks, "total_results": len(chunks)}

    def retrieve_by_project(
        self,
        query: str,
        project: str,
        top_k: int = 10,
        mode: RetrievalMode = RetrievalMode.HYBRID,
    ) -> list[RetrievalResult]:
        """
        Retrieve results filtered by project.

        Args:
            query: Search query
            project: Project name
            top_k: Number of results
            mode: Retrieval mode

        Returns:
            List of RetrievalResult objects
        """
        filters = {"project": project}
        return self.retrieve(query, top_k, mode, filters)

    def retrieve_by_source(
        self,
        query: str,
        source_type: SourceType,
        top_k: int = 10,
        mode: RetrievalMode = RetrievalMode.HYBRID,
    ) -> list[RetrievalResult]:
        """
        Retrieve results filtered by source type.

        Args:
            query: Search query
            source_type: Source type (PDF, MARKDOWN, PYTHON, etc.)
            top_k: Number of results
            mode: Retrieval mode

        Returns:
            List of RetrievalResult objects
        """
        filters = {"source_type": source_type.value}
        return self.retrieve(query, top_k, mode, filters)

    def retrieve_conversation_context(
        self, query: str, conversation_history: list[str], top_k: int = 10
    ) -> dict[str, Any]:
        """
        Retrieve knowledge for conversation context.

        Args:
            query: Current query
            conversation_history: Past conversation messages
            top_k: Number of results

        Returns:
            Dictionary with retrieved context
        """
        # Combine query with conversation history
        combined_query = " ".join(conversation_history[-5:] + [query])

        results = self.retrieve(combined_query, top_k, RetrievalMode.HYBRID)

        return {"query": query, "context": results}

    def get_retrieval_stats(
        self, query: str, top_k: int = 10, mode: RetrievalMode = RetrievalMode.HYBRID
    ) -> dict[str, Any]:
        """
        Get statistics about retrieval results.

        Args:
            query: Search query
            top_k: Number of results
            mode: Retrieval mode

        Returns:
            Dictionary with retrieval statistics
        """
        results = self.retrieve(query, top_k, mode)

        if not results:
            return {"query": query, "results_found": 0}

        # Calculate statistics
        total_score = sum(r.score for r in results)
        avg_score = total_score / len(results)

        # Count by source type
        by_source = {}
        for result in results:
            source = result.chunk.source_type.value
            by_source[source] = by_source.get(source, 0) + 1

        # Count by project
        by_project = {}
        for result in results:
            project = result.chunk.project
            if project:
                by_project[project] = by_project.get(project, 0) + 1

        return {
            "query": query,
            "results_found": len(results),
            "avg_score": avg_score,
            "total_score": total_score,
            "by_source": by_source,
            "by_project": by_project,
        }

    def prune_results(
        self, results: list[RetrievalResult], min_score: float = 0.5
    ) -> list[RetrievalResult]:
        """
        Prune results below minimum score threshold.

        Args:
            results: List of RetrievalResult objects
            min_score: Minimum score threshold

        Returns:
            Pruned list of results
        """
        pruned = [r for r in results if r.score >= min_score]
        logger.info(
            f"Pruned {len(results) - len(pruned)} results below score {min_score}"
        )
        return pruned

    def enrich_results(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """
        Enrich results with additional information.

        Args:
            results: List of RetrievalResult objects

        Returns:
            Enriched list of results
        """
        for result in results:
            # Add neighbors
            neighbors = self.graph_store.get_neighbors(result.chunk.id, limit=2)
            result.neighbors = [
                {"id": n[0].id, "title": n[0].title, "score": n[1].weight}
                for n in neighbors
            ]

            # Add source information
            result.source_info = {
                "file": result.chunk.source_file,
                "type": result.chunk.source_type.value,
                "project": result.chunk.project,
                "line": result.chunk.line,
                "page": result.chunk.page,
            }

        return results

    def get_similar_queries(self, query: str, top_k: int = 5) -> list[str]:
        """
        Get similar queries based on retrieved chunks.

        Args:
            query: Original query
            top_k: Number of similar queries

        Returns:
            List of similar queries
        """
        # Get top results
        results = self.retrieve(query, top_k * 3)

        # Extract unique phrases from retrieved chunks
        phrases = set()

        for result in results:
            # Extract words and phrases from content
            words = result.chunk.content.split()
            for i in range(len(words) - 1):
                phrase = " ".join(words[i : i + 3])
                phrases.add(phrase)

        # Return unique phrases
        return list(phrases)[:top_k]
