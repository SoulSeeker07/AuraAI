from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Citation:
    """A citation for a source."""

    title: str
    url: str
    score: float
    rank: int


class CitationBuilder:
    """
    Builds citation lists from search results.
    Formats sources in a clear, readable way.
    """

    def __init__(self):
        pass

    def build_citations(
        self,
        ranked_results: list[Any],
        include_reasoning: bool = True,
        max_citations: int = 5,
    ) -> Any:
        """
        Build citation list from ranked results.

        Args:
            ranked_results: Ranked search results
            include_reasoning: Include reasoning in citations
            max_citations: Maximum number of citations

        Returns:
            List of Citation objects or markdown string
        """
        if not ranked_results:
            return ""

        # If passed a list of raw citation dicts (e.g. from unit tests), format as markdown string
        if isinstance(ranked_results[0], dict) and "source" in ranked_results[0]:
            lines = []
            for r in ranked_results[:max_citations]:
                title = r.get("title", "Untitled")
                url = r.get("url", "")
                source = r.get("source", self._extract_domain(url))
                reason = r.get("reason", "")
                line = f"- [{title}]({url}) ({source})"
                if reason:
                    line += f" - *{reason}*"
                lines.append(line)
            return "\n".join(lines)

        citations = []
        for i, result in enumerate(ranked_results[:max_citations]):
            if hasattr(result, "result"):
                res_data = result.result
                title = res_data.get("title", "Untitled") if isinstance(res_data, dict) else getattr(res_data, "title", "Untitled")
                url = res_data.get("url", "") if isinstance(res_data, dict) else getattr(res_data, "url", "")
                score = getattr(result, "score", 1.0)
                rank = getattr(result, "rank", i + 1)
            elif isinstance(result, dict):
                title = result.get("title", "Untitled")
                url = result.get("url", "")
                score = result.get("score", 1.0)
                rank = result.get("rank", i + 1)
            else:
                title = getattr(result, "title", "Untitled")
                url = getattr(result, "url", "")
                score = getattr(result, "score", 1.0)
                rank = getattr(result, "rank", i + 1)

            citations.append(Citation(title=title, url=url, score=score, rank=rank))

        return citations

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: URL string

        Returns:
            Domain name
        """
        if not url:
            return "Unknown"

        # Remove protocol
        url = url.replace("https://", "").replace("http://", "")

        # Split on first slash
        domain = url.split("/")[0]

        # Extract just the domain name (remove subdomains if present)
        parts = domain.split(".")

        if len(parts) >= 2:
            # If there are more than 2 parts, take the last 2
            if len(parts) > 2:
                return f"{parts[-2]}.{parts[-1]}"
            return domain

        return domain

    def _format_citation(
        self,
        title: str,
        url: str,
        domain: str,
        rank: int,
        reasoning: list[str] | None = None,
        score: float = 0.0,
    ) -> str:
        """
        Format a citation entry.

        Args:
            title: Title of the source
            url: URL of the source
            domain: Domain name
            rank: Rank of the source
            reasoning: List of reasons for the rank
            score: Score for the source

        Returns:
            Formatted citation string
        """
        # Build the citation with markdown
        citation = f"**{rank}. {title}**\n"
        citation += f"Source: [{domain}]({url})\n"

        if reasoning:
            # Add reasoning if provided
            reasons_text = ", ".join(reasoning)
            citation += f"*Reasoning: {reasons_text}*\n"

        if score > 0:
            citation += f"*Confidence: {score:.2f}*\n"

        return citation

    def build_citations_section(
        self, citations: list[Citation], heading: str = "Sources"
    ) -> str:
        """
        Build a complete citations section for the answer.

        Args:
            citations: List of citations
            heading: Heading for the section

        Returns:
            Markdown formatted citations section
        """
        if not citations:
            return ""

        # Add citation heading
        section = f"\n### {heading}\n\n"

        # Add each citation
        for citation in citations:
            section += self._format_citation(
                title=citation.title,
                url=citation.url,
                domain=self._extract_domain(citation.url),
                rank=citation.rank,
            )
            section += "\n"

        return section

    def build_simple_citations(
        self, citations: list[Citation], include_urls: bool = True
    ) -> list[str]:
        """
        Build simple citation list (just titles with optional URLs).

        Args:
            citations: List of citations
            include_urls: Include URLs in the list

        Returns:
            List of citation strings
        """
        simple_citations = []

        for citation in citations:
            citation_str = f"{citation.rank}. {citation.title}"

            if include_urls:
                domain = self._extract_domain(citation.url)
                citation_str += f" ([{domain}]({citation.url}))"

            simple_citations.append(citation_str)

        return simple_citations

    def extract_domain_info(self, url: str) -> dict[str, str]:
        """
        Extract domain information from URL.

        Args:
            url: URL string

        Returns:
            Dictionary with domain information
        """
        if not url:
            return {"domain": "Unknown", "tld": ""}

        # Remove protocol
        url = url.replace("https://", "").replace("http://", "")

        # Split on first slash
        domain = url.split("/")[0]

        # Extract top-level domain
        parts = domain.split(".")
        tld = parts[-1] if parts else ""

        # Extract domain name (second to last)
        domain_name = parts[-2] if len(parts) >= 2 else ""

        return {
            "domain": domain_name,
            "tld": tld,
            "full_domain": domain,
        }
