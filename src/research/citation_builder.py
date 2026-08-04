"""
Citation Builder

Builds citations from evidence and research results.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from .models import Evidence, SourceTrustLevel, normalize_trust_level

logger = logging.getLogger(__name__)


class CitationStyle(Enum):
    """Citation formatting styles."""
    APA = "apa"
    MLA = "mla"
    Chicago = "chicago"
    IEEE = "ieee"
    Numerical = "numerical"


@dataclass
class Citation:
    """
    A citation to a source.
    
    Example:
        Citation(
            source="python.org",
            url="https://python.org",
            title="Python 3.14",
            confidence=0.95,
            evidence_ids=[1,4,6]
        )
    """
    id: int  # Unique citation ID
    source: str  # Source name (e.g., "python.org", "github.com")
    title: Optional[str] = None  # Title of the document
    url: str = ""  # URL to source
    trust_level: str = "unknown"  # Trust level of source
    confidence: float = 0.5  # Confidence in this citation
    evidence_ids: List[int] = None  # IDs of evidence items this citation supports
    citation_style: CitationStyle = CitationStyle.APA  # Formatting style for this citation

    def __post_init__(self):
        if self.evidence_ids is None:
            self.evidence_ids = []


class CitationBuilder:
    """
    Builds citations from evidence and research results.
    
    Creates structured citations that can be used in reports and responses.
    """
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize citation builder.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.style = CitationStyle(self.config.get('style', 'apa'))
        self.next_id = 1

    def build_citations(self, evidence_list: List[Evidence]) -> List[Citation]:
        """
        Build citations from evidence list.

        Args:
            evidence_list: List of evidence objects

        Returns:
            List of Citation objects
        """
        citations = []

        for evidence in evidence_list:
            citation = self._create_citation_from_evidence(evidence)
            if citation:
                citations.append(citation)

        self.next_id = 1  # Reset ID counter
        return citations

    def _create_citation_from_evidence(self, evidence: Evidence) -> Optional[Citation]:
        """
        Create a citation from an evidence object.

        Args:
            evidence: Evidence object

        Returns:
            Citation object or None
        """
        # Extract domain from URL
        domain = self._extract_domain(evidence.url)

        # Create citation
        citation = Citation(
            id=self.next_id,
            source=domain,
            title=None,
            url=evidence.url,
            trust_level=evidence.trust_level,
            confidence=self._calculate_evidence_confidence(evidence),
            evidence_ids=[self.next_id],  # ID of the fact
            citation_style=self.style,  # Use the builder's configured style
        )

        self.next_id += 1
        return citation

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: URL

        Returns:
            Domain name
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain
        except:
            return url

    def _calculate_evidence_confidence(self, evidence: Evidence) -> float:
        """
        Calculate confidence for an evidence object.

        Args:
            evidence: Evidence object

        Returns:
            Confidence score (0-1)
        """
        # Base confidence on trust level
        trust_scores = {
            'official': 0.95,
            'government': 0.95,
            'github': 0.90,
            'stackoverflow': 0.85,
            'wikipedia': 0.75,
            'reddit': 0.70,
            'blog': 0.60,
            'unknown': 0.50
        }

        # Get trust level as lowercase string for matching
        trust_level_str = normalize_trust_level(evidence.trust_level)
        confidence = trust_scores.get(trust_level_str, 0.50)

        # Adjust by source score
        if evidence.score >= 3:
            confidence += 0.05
        elif evidence.score >= 5:
            confidence += 0.10

        return min(confidence, 1.0)

    def format_citation(self, citation: Citation) -> str:
        """
        Format citation in the configured style.

        Args:
            citation: Citation object

        Returns:
            Formatted citation string
        """
        if self.style == CitationStyle.APA:
            return self._format_apa(citation)
        elif self.style == CitationStyle.MLA:
            return self._format_mla(citation)
        elif self.style == CitationStyle.Chicago:
            return self._format_chicago(citation)
        elif self.style == CitationStyle.IEEE:
            return self._format_ieee(citation)
        else:
            return self._format_numerical(citation)

    def _format_apa(self, citation: Citation) -> str:
        """
        Format citation in APA style.

        Args:
            citation: Citation object

        Returns:
            APA formatted citation
        """
        if citation.title:
            return f"({citation.id}) {citation.source}, *{citation.title}*"
        return f"({citation.id}) {citation.source}"

    def _format_mla(self, citation: Citation) -> str:
        """
        Format citation in MLA style.

        MLA style: Author. "Title." Source, Publication Date.

        Args:
            citation: Citation to format

        Returns:
            MLA formatted citation
        """
        # Handle case where title is None
        if citation.title is None:
            return citation.url

        author = self._extract_author(citation.title)
        title = citation.title

        if author:
            return f"{author}. {title}. {citation.url}"
        else:
            return f"{title}. {citation.url}"

    def _format_chicago(self, citation: Citation) -> str:
        """
        Format citation in Chicago style.

        Chicago style: Author. "Title." Source, Publication Date.

        Args:
            citation: Citation to format

        Returns:
            Chicago formatted citation
        """
        # Handle case where title is None
        if citation.title is None:
            return citation.url

        author = self._extract_author(citation.title)
        title = citation.title

        if author:
            return f"{author}. {title}. {citation.url}"
        else:
            return f"{title}. {citation.url}"

    def _format_ieee(self, citation: Citation) -> str:
        """
        Format citation in IEEE style.

        IEEE style: [1] Author, "Title," Source.

        Args:
            citation: Citation to format

        Returns:
            IEEE formatted citation
        """
        # IEEE uses numbered references
        return f"[{citation.id}] {citation.url}"

    def _format_numerical(self, citation: Citation) -> str:
        """
        Format citation in numerical style.

        Args:
            citation: Citation object

        Returns:
            Numerically formatted citation
        """
        return f"[{citation.id}] {citation.source}"

    def format_citations(self, citations: List[Citation]) -> str:
        """
        Format all citations.

        Args:
            citations: List of citation objects

        Returns:
            Formatted citations string
        """
        if not citations:
            return ""

        lines = []
        for citation in citations:
            lines.append(self.format_citation(citation))

        return "\n".join(lines)

    def generate_citation_list(self, citations: List[Citation]) -> str:
        """
        Generate a formatted citation list.

        Args:
            citations: List of citation objects

        Returns:
            Formatted citation list
        """
        formatted = self.format_citations(citations)

        return formatted if formatted else "No sources available."

    def create_bibliography(self, citations: List[Citation]) -> str:
        """
        Create a full bibliography section.

        Args:
            citations: List of citation objects

        Returns:
            Full bibliography
        """
        lines = ["**Bibliography**", ""]
        lines.append(self.generate_citation_list(citations))
        return "\n".join(lines)

    def add_footnote(self, citation: Citation, context: str = None) -> str:
        """
        Add a footnote-style citation.

        Args:
            citation: Citation object
            context: Optional context for footnote

        Returns:
            Footnote string
        """
        citation_text = self.format_citation(citation)

        if context:
            return f"[{citation.id}] {context}: {citation_text}"
        return citation_text

    def get_citation_by_id(self, citations: List[Citation], citation_id: int) -> Optional[Citation]:
        """
        Get a citation by its ID.

        Args:
            citations: List of citation objects
            citation_id: Citation ID to find

        Returns:
            Citation object or None
        """
        for citation in citations:
            if citation.id == citation_id:
                return citation
        return None

    def get_citations_by_source(self, citations: List[Citation], source: str) -> List[Citation]:
        """
        Get all citations from a specific source.

        Args:
            citations: List of citation objects
            source: Source name

        Returns:
            List of citation objects
        """
        return [c for c in citations if c.source == source]

    def filter_by_trust_level(self, citations: List[Citation], trust_level: str) -> List[Citation]:
        """
        Filter citations by trust level.

        Args:
            citations: List of citation objects
            trust_level: Trust level to filter by

        Returns:
            Filtered list of citation objects
        """
        return [c for c in citations if c.trust_level == trust_level]

    def _extract_author(self, title: str) -> Optional[str]:
        """
        Extract author from title string.

        Args:
            title: Title string

        Returns:
            Author name or None
        """
        # Try to extract author using common patterns
        # e.g., "Author, A. A. - Title"
        if " - " in title:
            parts = title.split(" - ")
            return parts[0].strip()
        
        # e.g., "by Author"
        if " by " in title.lower():
            parts = title.lower().split(" by ")
            return parts[1].strip()
        
        # e.g., "Author (Year)"
        import re
        match = re.search(r'^(.+?)\s*\((\d{4})\)', title)
        if match:
            return match.group(1).strip()
        
        return None

    def _extract_year(self, url: str) -> Optional[str]:
        """
        Extract publication year from URL.

        Args:
            url: URL to parse

        Returns:
            Year string or None
        """
        import re
        
        # Look for year patterns in URL
        year_patterns = [
            r'/(\d{4})/',
            r'-(\d{4})',
            r'/(\d{4})/.*',
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None

    def create_footnotes(self, citations: List[Citation]) -> List[str]:
        """
        Create footnotes with full citations.

        Args:
            citations: Citations

        Returns:
            List of footnote strings
        """
        footnotes = []
        
        for citation in citations:
            footnote = f"[{citation.id}] {citation.url}"
            if citation.title:
                footnote += f" {citation.title}"
            footnotes.append(footnote)
        
        return footnotes

    def validate_citations(self, citations: List[Citation]) -> Dict[str, Any]:
        """
        Validate citations.

        Args:
            citations: Citations to validate

        Returns:
            Validation results
        """
        issues = []
        
        for citation in citations:
            if not citation.url:
                issues.append(f"Citation {citation.id}: Missing URL")
            if not citation.title:
                issues.append(f"Citation {citation.id}: Missing title")
            if citation.confidence < 0.2:
                issues.append(f"Citation {citation.id}: Low confidence")
        
        return {
            "total_citations": len(citations),
            "valid": len(issues) == 0,
            "issues": issues
        }

    def build_citation(self, evidence: Evidence) -> Citation:
        """
        Build a single citation from evidence.

        Args:
            evidence: Evidence object

        Returns:
            Citation object
        """
        return self.build_citations([evidence])[0]