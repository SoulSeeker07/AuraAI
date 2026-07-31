"""
Knowledge Context Builder

Builds structured context for LLM from knowledge retrieval results.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .models import RetrievalResult, RetrievalMode, SourceType
from .citation_engine import CitationEngine

logger = logging.getLogger(__name__)


class KnowledgeContext:
    """
    Builds structured context for LLM from knowledge retrieval.
    """

    def __init__(self):
        """Initialize knowledge context builder."""
        self.citation_engine = CitationEngine()

    def build_context(
        self,
        results: List[RetrievalResult],
        mode: RetrievalMode = RetrievalMode.HYBRID,
        include_citations: bool = True,
        include_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Build LLM context from retrieval results.

        Args:
            results: Retrieval results
            mode: Retrieval mode
            include_citations: Whether to include citations
            include_summary: Whether to include summary

        Returns:
            Dictionary with structured context
        """
        context = {
            'mode': mode.value,
            'timestamp': datetime.now().isoformat(),
            'total_results': len(results),
            'results': []
        }

        # Build summary
        if include_summary:
            context['summary'] = self._build_summary(results)

        # Build results with citations
        if include_citations:
            for result in results:
                result_dict = {
                    'id': result.chunk.id,
                    'title': result.chunk.title,
                    'content': result.chunk.content[:1000] + "..." if len(result.chunk.content) > 1000 else result.chunk.content,
                    'summary': result.chunk.summary,
                    'score': result.score,
                    'rank': result.rank,
                    'source': {
                        'file': result.chunk.source_file,
                        'type': result.chunk.source_type.value,
                        'project': result.chunk.project,
                        'page': result.chunk.page,
                        'line': result.chunk.line
                    }
                }

                if result.citation:
                    result_dict['citation'] = self._format_citation(result.citation)

                context['results'].append(result_dict)

            # Add citations
            context['citations'] = self._format_citations(results)

        return context

    def build_conversation_context(
        self,
        query: str,
        results: List[RetrievalResult],
        conversation_history: List[str],
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Build context for conversation.

        Args:
            query: Current user query
            results: Retrieval results
            conversation_history: Past conversation messages
            top_k: Number of top results to include

        Returns:
            Dictionary with conversation context
        """
        # Build standard context
        context = self.build_context(
            results,
            mode=RetrievalMode.HYBRID,
            include_citations=True,
            include_summary=True
        )

        # Add conversation-specific elements
        context['query'] = query
        context['conversation_length'] = len(conversation_history)
        context['recent_conversation'] = conversation_history[-3:]

        # Add reasoning
        context['reasoning'] = self._build_reasoning(query, results)

        return context

    def build_workspace_context(
        self,
        query: str,
        project: str,
        results: List[RetrievalResult],
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Build context filtered by project.

        Args:
            query: Current query
            project: Project name
            results: Retrieval results
            top_k: Number of top results

        Returns:
            Dictionary with workspace context
        """
        # Filter results by project
        project_results = [r for r in results if r.chunk.project == project]

        # Build context
        context = self.build_context(
            project_results,
            mode=RetrievalMode.HYBRID,
            include_citations=True,
            include_summary=True
        )

        context['query'] = query
        context['project'] = project
        context['filtered_results'] = len(project_results)

        return context

    def build_specialized_context(
        self,
        query: str,
        context_type: str,
        results: List[RetrievalResult],
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Build specialized context (code, documentation, etc.).

        Args:
            query: Current query
            context_type: Type of context (CODE, DOCUMENTATION, etc.)
            results: Retrieval results
            top_k: Number of top results

        Returns:
            Dictionary with specialized context
        """
        # Build context
        context = self.build_context(
            results,
            mode=RetrievalMode.HYBRID,
            include_citations=True,
            include_summary=True
        )

        context['query'] = query
        context['context_type'] = context_type

        # Filter by source type based on context type
        if context_type == 'CODE':
            context['source_type'] = SourceType.PYTHON.value
        elif context_type == 'DOCUMENTATION':
            context['source_type'] = SourceType.MARKDOWN.value
        elif context_type == 'NOTICES':
            context['source_type'] = SourceType.PDF.value
        elif context_type == 'WELCOME':
            context['source_type'] = SourceType.MARKDOWN.value
        elif context_type == 'ERROR':
            context['source_type'] = SourceType.MARKDOWN.value

        return context

    def build_chunk_context(
        self,
        results: List[RetrievalResult],
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Build context focused on content chunks.

        Args:
            results: Retrieval results
            top_k: Number of top results

        Returns:
            Dictionary with chunk-focused context
        """
        context = {
            'mode': 'hybrid',
            'timestamp': datetime.now().isoformat(),
            'total_results': len(results),
            'chunks': []
        }

        for result in results[:top_k]:
            chunk_context = {
                'id': result.chunk.id,
                'title': result.chunk.title,
                'content': result.chunk.content,
                'summary': result.chunk.summary,
                'score': result.score,
                'rank': result.rank,
                'source': {
                    'file': result.chunk.source_file,
                    'type': result.chunk.source_type.value,
                    'project': result.chunk.project,
                    'page': result.chunk.page,
                    'line': result.chunk.line
                },
                'tags': result.chunk.tags
            }

            context['chunks'].append(chunk_context)

        return context

    def _build_summary(self, results: List[RetrievalResult]) -> str:
        """
        Build a text summary of results.

        Args:
            results: Retrieval results

        Returns:
            Summary string
        """
        if not results:
            return "No relevant information found."

        # Build summary
        summary_parts = []

        # Top result
        top = results[0]
        if top.chunk.title:
            summary_parts.append(f"Most relevant: {top.chunk.title}")

        # Count by source type
        by_source = {}
        for r in results:
            source = r.chunk.source_type.value
            by_source[source] = by_source.get(source, 0) + 1

        source_str = ", ".join(f"{k}: {v}" for k, v in by_source.items())
        summary_parts.append(f"Sources: {source_str}")

        # Average score
        avg_score = sum(r.score for r in results) / len(results) if results else 0
        summary_parts.append(f"Average relevance: {avg_score:.2f}")

        return "; ".join(summary_parts)

    def _build_reasoning(self, query: str, results: List[RetrievalResult]) -> str:
        """
        Build reasoning about retrieval.

        Args:
            query: User query
            results: Retrieval results

        Returns:
            Reasoning string
        """
        reasoning_parts = []

        reasoning_parts.append(f"Retrieved {len(results)} results for query: '{query}'")

        if results:
            # Top score
            top_score = results[0].score
            reasoning_parts.append(f"Top result relevance: {top_score:.3f}")

            # Source types
            by_source = {}
            for r in results:
                source = r.chunk.source_type.value
                by_source[source] = by_source.get(source, 0) + 1

            reasoning_parts.append(f"Sources: {by_source}")

            # Projects
            by_project = {}
            for r in results:
                project = r.chunk.project
                if project:
                    by_project[project] = by_project.get(project, 0) + 1

            if by_project:
                reasoning_parts.append(f"Projects: {by_project}")

        return "; ".join(reasoning_parts)

    def _format_citation(self, citation) -> str:
        """
        Format a citation for context.

        Args:
            citation: Citation object

        Returns:
            Formatted citation string
        """
        return self.citation_engine.format_citation_simple(citation)

    def _format_citations(self, results: List[RetrievalResult]) -> List[str]:
        """
        Format all citations.

        Args:
            results: Retrieval results

        Returns:
            List of formatted citations
        """
        citations = [r.citation for r in results if r.citation]

        if not citations:
            return []

        return [self._format_citation(c) for c in citations]

    def format_for_llm(
        self,
        results: List[RetrievalResult],
        include_citations: bool = True,
        format: str = "structured"
    ) -> str:
        """
        Format results for LLM input.

        Args:
            results: Retrieval results
            include_citations: Whether to include citations
            format: Format type (structured, conversational, simple)

        Returns:
            Formatted string for LLM
        """
        if format == "structured":
            return self._format_structured(results, include_citations)
        elif format == "conversational":
            return self._format_conversational(results, include_citations)
        elif format == "simple":
            return self._format_simple(results)
        else:
            return self._format_structured(results, include_citations)

    def _format_structured(
        self,
        results: List[RetrievalResult],
        include_citations: bool
    ) -> str:
        """
        Format results in structured format.

        Args:
            results: Retrieval results
            include_citations: Whether to include citations

        Returns:
            Structured format string
        """
        if not results:
            return ""

        output = "## Retrieved Information\n\n"

        for i, result in enumerate(results, 1):
            output += f"### {i}. {result.chunk.title or 'Untitled'}\n\n"
            output += f"Content: {result.chunk.content}\n\n"

            if include_citations and result.citation:
                output += f"Citation: {self._format_citation(result.citation)}\n\n"

        return output

    def _format_conversational(
        self,
        results: List[RetrievalResult],
        include_citations: bool
    ) -> str:
        """
        Format results in conversational format.

        Args:
            results: Retrieval results
            include_citations: Whether to include citations

        Returns:
            Conversational format string
        """
        if not results:
            return ""

        output = []

        for i, result in enumerate(results, 1):
            output.append(f"[{i}] {result.chunk.content}")

            if include_citations and result.citation:
                output.append(f"(Source: {self._format_citation(result.citation)})")

            output.append("")  # Empty line

        return "\n".join(output)

    def _format_simple(self, results: List[RetrievalResult]) -> str:
        """
        Format results in simple format.

        Args:
            results: Retrieval results

        Returns:
            Simple format string
        """
        if not results:
            return ""

        return "\n".join([r.chunk.content for r in results])

    def get_context_stats(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics about the built context.

        Args:
            context: Built context dictionary

        Returns:
            Statistics dictionary
        """
        return {
            'total_results': context.get('total_results', 0),
            'total_chunks': len(context.get('results', [])),
            'total_citations': len(context.get('citations', [])),
            'mode': context.get('mode'),
            'timestamp': context.get('timestamp')
        }

    def extract_sources(self, context: Dict[str, Any]) -> List[str]:
        """
        Extract unique sources from context.

        Args:
            context: Built context dictionary

        Returns:
            List of unique sources
        """
        sources = set()

        for result in context.get('results', []):
            source = result.get('source', {})
            sources.add(source.get('file'))

        return sorted(list(sources))

    def filter_by_threshold(
        self,
        results: List[RetrievalResult],
        min_score: float = 0.5
    ) -> List[RetrievalResult]:
        """
        Filter results below score threshold.

        Args:
            results: Retrieval results
            min_score: Minimum score threshold

        Returns:
            Filtered results
        """
        filtered = [r for r in results if r.score >= min_score]

        logger.info(f"Filtered {len(results) - len(filtered)} results below score {min_score}")

        return filtered
