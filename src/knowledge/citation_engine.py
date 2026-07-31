"""
Knowledge Citation Engine

Generates citations from knowledge chunks for LLM responses.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from .models import Citation, RetrievalResult, DocumentChunk, SourceType

logger = logging.getLogger(__name__)


class CitationEngine:
    """
    Engine for generating citations from knowledge chunks.
    """

    def __init__(self):
        """Initialize citation engine."""
        self.logger = logging.getLogger(__name__)

    def create_citation(
        self,
        chunk: DocumentChunk,
        retrieval_mode: str = "Semantic search",
        relevance_score: float = 0.0
    ) -> Citation:
        """
        Create a citation from a chunk.

        Args:
            chunk: Document chunk
            retrieval_mode: Mode of retrieval (Semantic, Keyword, Hybrid)
            relevance_score: Relevance score

        Returns:
            Citation object
        """
        return Citation(
            chunk_id=chunk.id,
            title=chunk.title,
            source=chunk.source_file,
            source_type=chunk.source_type.value,
            project=chunk.project,
            page=chunk.page,
            line=chunk.line,
            retrieval_date=datetime.now(),
            retrieval_mode=retrieval_mode,
            relevance_score=relevance_score
        )

    def generate_citations(
        self,
        results: List[RetrievalResult]
    ) -> List[Citation]:
        """
        Generate citations from retrieval results.

        Args:
            results: List of RetrievalResult objects

        Returns:
            List of Citation objects
        """
        citations = []

        for result in results:
            citation = self.create_citation(
                chunk=result.chunk,
                retrieval_mode="Hybrid search",
                relevance_score=result.score
            )
            result.citation = citation
            citations.append(citation)

        return citations

    def format_citation_simple(
        self,
        citation: Citation
    ) -> str:
        """
        Format citation in simple format.

        Args:
            citation: Citation object

        Returns:
            Formatted citation string
        """
        components = []

        if citation.title:
            components.append(f"{citation.title}")

        if citation.source:
            components.append(f"({citation.source})")

        if citation.page:
            components.append(f"p.{citation.page}")

        return ", ".join(components)

    def format_citation_detailed(
        self,
        citation: Citation,
        include_url: bool = False
    ) -> str:
        """
        Format citation in detailed format.

        Args:
            citation: Citation object
            include_url: Whether to include URL

        Returns:
            Formatted citation string
        """
        components = []

        if citation.title:
            components.append(f"{citation.title}")

        if citation.source:
            if include_url and citation.source.startswith("http"):
                components.append(f"[{citation.source}]")
            else:
                components.append(f"({citation.source})")

        if citation.project:
            components.append(f"Project: {citation.project}")

        if citation.page:
            components.append(f"p.{citation.page}")

        if citation.line:
            components.append(f"l.{citation.line}")

        # Format date
        if citation.retrieval_date:
            date_str = citation.retrieval_date.strftime("%Y-%m-%d")
            components.append(f"{date_str}")

        return ", ".join(components)

    def format_citation_camelcase(
        self,
        citation: Citation
    ) -> str:
        """
        Format citation in CamelCase format (e.g., "Chapter1 (Chapter:1.2)").

        Args:
            citation: Citation object

        Returns:
            Formatted citation string
        """
        components = []

        # Title to CamelCase
        if citation.title:
            title_camel = self._to_camel_case(citation.title)
            components.append(title_camel)

        # Source
        if citation.source:
            source_camel = self._to_camel_case(citation.source)
            components.append(f"({source_camel})")

        # Page
        if citation.page:
            components.append(f"p.{citation.page}")

        return ", ".join(components)

    def _to_camel_case(self, text: str) -> str:
        """
        Convert text to CamelCase.

        Args:
            text: Input text

        Returns:
            CamelCase string
        """
        words = text.split()

        # Capitalize first letter of each word, lowercase the rest
        camel_case = ''.join(word.capitalize() for word in words)

        # Convert to lowercase
        camel_case = camel_case[0].lower() + camel_case[1:] if camel_case else ""

        return camel_case

    def format_citation_bracket(
        self,
        citation: Citation,
        include_year: bool = True
    ) -> str:
        """
        Format citation in bracket format (e.g., "[Chapter1, 2024]")).

        Args:
            citation: Citation object
            include_year: Whether to include retrieval year

        Returns:
            Formatted citation string
        """
        components = []

        if citation.title:
            components.append(citation.title)

        if include_year and citation.retrieval_date:
            year = citation.retrieval_date.year
            components.append(str(year))

        return f"[{', '.join(components)}]"

    def create_bibliography(
        self,
        citations: List[Citation]
    ) -> str:
        """
        Create a bibliography from citations.

        Args:
            citations: List of Citation objects

        Returns:
            Formatted bibliography
        """
        bibliography = "## References\n\n"

        for i, citation in enumerate(citations, 1):
            if citation.title:
                bibliography += f"{i}. {citation.title}.\n"

                if citation.source:
                    bibliography += f"   Source: {citation.source}\n"

                if citation.project:
                    bibliography += f"   Project: {citation.project}\n"

                if citation.page:
                    bibliography += f"   Page: {citation.page}\n"

                bibliography += "\n"

        return bibliography

    def generate_citation_links(
        self,
        results: List[RetrievalResult]
    ) -> Dict[str, str]:
        """
        Generate citation links for results.

        Args:
            results: List of RetrievalResult objects

        Returns:
            Dictionary of chunk_id -> citation link
        """
        links = {}

        for result in results:
            citation = self.create_citation(
                chunk=result.chunk,
                retrieval_mode="Hybrid search",
                relevance_score=result.score
            )

            link = self._create_citation_link(citation)
            links[result.chunk.id] = link

        return links

    def _create_citation_link(
        self,
        citation: Citation
    ) -> str:
        """
        Create a citation link.

        Args:
            citation: Citation object

        Returns:
            Citation link string
        """
        # Create a simple link format
        parts = []

        if citation.title:
            parts.append(citation.title)

        if citation.source:
            parts.append(citation.source)

        return " → ".join(parts)

    def get_citation_summary(
        self,
        citations: List[Citation]
    ) -> str:
        """
        Get a summary of citations.

        Args:
            citations: List of Citation objects

        Returns:
            Summary string
        """
        if not citations:
            return "No citations available."

        # Count by source type
        by_source = {}
        for citation in citations:
            source_type = citation.source_type
            by_source[source_type] = by_source.get(source_type, 0) + 1

        # Count by project
        by_project = {}
        for citation in citations:
            project = citation.project
            if project:
                by_project[project] = by_project.get(project, 0) + 1

        summary_parts = []

        if by_source:
            summary_parts.append(f"Sources: {by_source}")

        if by_project:
            summary_parts.append(f"Projects: {by_project}")

        return ", ".join(summary_parts)

    def validate_citation(self, citation: Citation) -> Dict[str, Any]:
        """
        Validate a citation.

        Args:
            citation: Citation object

        Returns:
            Validation result with valid flag and errors
        """
        errors = []

        # Check required fields
        if not citation.chunk_id:
            errors.append("Missing chunk_id")

        if not citation.source:
            errors.append("Missing source")

        # Check source type validity
        if citation.source_type and citation.source_type not in [st.value for st in SourceType]:
            errors.append(f"Invalid source type: {citation.source_type}")

        # Check relevance score range
        if citation.relevance_score is not None:
            if not (0.0 <= citation.relevance_score <= 1.0):
                errors.append(
                    f"Relevance score out of range: {citation.relevance_score}"
                )

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    def deduplicate_citations(
        self,
        citations: List[Citation]
    ) -> List[Citation]:
        """
        Remove duplicate citations.

        Args:
            citations: List of Citation objects

        Returns:
            Deduplicated list of citations
        """
        seen = set()
        unique = []

        for citation in citations:
            # Create a key based on unique attributes
            key = (
                citation.chunk_id,
                citation.source,
                citation.source_type
            )

            if key not in seen:
                seen.add(key)
                unique.append(citation)

        removed = len(citations) - len(unique)
        self.logger.info(f"Removed {removed} duplicate citations")

        return unique

    def extract_citation_metadata(
        self,
        citation_text: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from citation text.

        Args:
            citation_text: Citation text to parse

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            'title': None,
            'source': None,
            'page': None,
            'line': None,
            'project': None
        }

        # Extract title (first capitalized word or phrase)
        match = re.search(r'^[A-Z][a-zA-Z\s]+', citation_text)
        if match:
            metadata['title'] = match.group(0).strip()

        # Extract source (in parentheses or brackets)
        source_match = re.search(r'[(\[](.*?)[)\]]', citation_text)
        if source_match:
            metadata['source'] = source_match.group(1).strip()

        # Extract page number
        page_match = re.search(r'p\.(\d+)', citation_text)
        if page_match:
            metadata['page'] = int(page_match.group(1))

        # Extract line number
        line_match = re.search(r'l\.(\d+)', citation_text)
        if line_match:
            metadata['line'] = int(line_match.group(1))

        # Extract project
        project_match = re.search(r'Project:\s*(\w+)', citation_text)
        if project_match:
            metadata['project'] = project_match.group(1)

        return metadata

    def format_citation_for_llm(
        self,
        results: List[RetrievalResult]
    ) -> str:
        """
        Format citations in a way that's friendly for LLM context.

        Args:
            results: List of RetrievalResult objects

        Returns:
            Formatted citation string
        """
        if not results:
            return ""

        citations = [r.citation for r in results if r.citation]

        if not citations:
            return ""

        # Create numbered list
        citation_list = []

        for i, citation in enumerate(citations, 1):
            formatted = self.format_citation_simple(citation)
            citation_list.append(f"{i}. {formatted}")

        return "\n".join(citation_list)
