"""
Citation Formatter

This module provides formatting capabilities for citations.
Supports multiple citation styles: APA, MLA, Chicago, IEEE, Numerical.

The formatter ONLY formats existing Citation objects.
The builder ONLY creates Citation objects.
"""

from typing import List, Optional
from datetime import datetime
import re
import logging
from .citation_builder import Citation

logger = logging.getLogger(__name__)


class CitationFormatter:
    """
    Citation Formatter
    
    Supports multiple citation styles:
    - APA (American Psychological Association)
    - MLA (Modern Language Association)
    - Chicago (Author-Date)
    - IEEE (Institute of Electrical and Electronics Engineers)
    - Numerical (Numbered in order)
    """
    
    # Style mappings
    STYLES = {
        "apa": "APA",
        "mla": "MLA",
        "chicago": "Chicago",
        "ieee": "IEEE",
        "numerical": "Numerical"
    }
    
    def __init__(self, style: str = "apa"):
        """
        Initialize the citation formatter.
        
        Args:
            style: Citation style (apa, mla, chicago, ieee, numerical)
        """
        self.style = style.lower()
        
        if self.style not in self.STYLES:
            raise ValueError(
                f"Unsupported citation style: {style}. "
                f"Supported styles: {', '.join(self.STYLES.keys())}"
            )
    
    def format_citations(self, citations: List[Citation], **kwargs) -> str:
        """
        Format citations according to the specified style.
        
        Args:
            citations: List of Citation objects
            **kwargs: Additional formatting options
            
        Returns:
            Formatted citation string
        """
        if not citations:
            return ""
        
        formatted_citations = []
        
        for i, citation in enumerate(citations):
            formatted = self._format_single_citation(citation, i)
            formatted_citations.append(formatted)
        
        return "\n".join(formatted_citations)
    
    def format_in_text(
        self,
        citations: List[Citation],
        **kwargs
    ) -> str:
        """
        Format citations for in-text citation (parenthetical).
        
        Args:
            citations: List of Citation objects
            **kwargs: Additional formatting options
            
        Returns:
            Formatted in-text citation string
        """
        if not citations:
            return ""
        
        formatted = []
        
        for citation in citations:
            formatted.append(self._format_in_text_single(citation))
        
        return ", ".join(formatted)
    
    def _format_single_citation(
        self,
        citation: Citation,
        index: Optional[int] = None
    ) -> str:
        """
        Format a single citation.
        
        Args:
            citation: Citation to format
            index: Index for numerical styles
            
        Returns:
            Formatted citation string
        """
        if self.style == "apa":
            return self._format_apa(citation)
        elif self.style == "mla":
            return self._format_mla(citation)
        elif self.style == "chicago":
            return self._format_chicago(citation)
        elif self.style == "ieee":
            return self._format_ieee(citation, index)
        elif self.style == "numerical":
            return self._format_numerical(citation, index)
        else:
            return str(citation)
    
    def _format_in_text_single(self, citation: Citation) -> str:
        """
        Format a single citation for in-text use.
        
        Args:
            citation: Citation to format
            
        Returns:
            Formatted in-text citation string
        """
        if self.style == "apa":
            return self._format_apa_in_text(citation)
        elif self.style == "mla":
            return self._format_mla_in_text(citation)
        elif self.style == "chicago":
            return self._format_chicago_in_text(citation)
        elif self.style == "ieee":
            return self._format_ieee_in_text(citation)
        elif self.style == "numerical":
            return self._format_numerical_in_text(citation)
        else:
            return str(citation)
    
    # APA Formatting
    def _format_apa(self, citation: Citation) -> str:
        """Format citation in APA style."""
        # Author: Last, A. A.
        author = self._extract_author_apa(citation.author)
        
        # Year
        year = self._extract_year(citation.date)
        
        # Title of work
        title = citation.title if citation.title else citation.url
        
        # Format: Author (Year). Title. Source.
        return f"{author} ({year}). {title}. {citation.url}"
    
    def _format_apa_in_text(self, citation: Citation) -> str:
        """Format in-text citation in APA style."""
        author = self._extract_author_apa(citation.author)
        year = self._extract_year(citation.date)
        
        return f"({author} {year})"
    
    # MLA Formatting
    def _format_mla(self, citation: Citation) -> str:
        """Format citation in MLA style."""
        # Author
        author = self._extract_author_mla(citation.author)
        
        # Title of work
        title = citation.title if citation.title else citation.url

        # Source
        source = citation.url
        # Format: Author. "Title." Source.
        return f'{author}. "{title}". {source}'
    
    def _format_mla_in_text(self, citation: Citation) -> str:
        """Format in-text citation in MLA style."""
        author = self._extract_author_mla(citation.author)
        
        return f"({author})"
    
    # Chicago Formatting
    def _format_chicago(self, citation: Citation) -> str:
        """Format citation in Chicago style."""
        # Author
        author = self._extract_author_chicago(citation.author)
        
        # Year
        year = self._extract_year(citation.date)

        # Title of work
        title = citation.title if citation.title else citation.url

        # Source
        source = citation.url
        # Format: Author, Title. Source, Year.
        return f"{author}, {title}. {source}, {year}"
    
    def _format_chicago_in_text(self, citation: Citation) -> str:
        """Format in-text citation in Chicago style."""
        author = self._extract_author_chicago(citation.author)
        
        return f"({author})"
    
    # IEEE Formatting
    def _format_ieee(self, citation: Citation, index: Optional[int] = None) -> str:
        """Format citation in IEEE style."""
        if index is None:
            raise ValueError("Index required for IEEE formatting")
        
        # Author list
        authors = self._extract_authors_ieee(citation.author)
        
        # Year
        year = self._extract_year(citation.date)

        # Title
        title = citation.title if citation.title else citation.url

        # Source
        source = citation.url
        # Format: [1] A. Author, "Title," Source, Year.
        return f"[{index}] {authors}, \"{title}\", {source}, {year}"
    
    def _format_ieee_in_text(self, citation: Citation) -> str:
        """Format in-text citation in IEEE style."""
        return "[1]"  # Simplified for IEEE
    
    # Numerical Formatting
    def _format_numerical(self, citation: Citation, index: Optional[int] = None) -> str:
        """Format citation in numerical style."""
        if index is None:
            raise ValueError("Index required for numerical formatting")
        
        # Format: [1] Title
        title = citation.title if citation.title else citation.url
        
        return f"[{index}] {title}"
    
    # Author extraction helpers
    def _extract_author_apa(self, author: str) -> str:
        """Extract author name in APA format (Last, A. A.)."""
        if not author:
            return "Anonymous"
        
        # Split by commas
        parts = [part.strip() for part in author.split(",")]
        
        if len(parts) >= 2:
            # Last name, First name Middle initial
            return f"{parts[0]}, {parts[1][0]}."
        elif len(parts) == 1:
            # First name Last name
            return parts[0]
        else:
            return author
    
    def _extract_author_mla(self, author: str) -> str:
        """Extract author name in MLA format (First Last)."""
        if not author:
            return "Anonymous"
        
        return author.strip()
    
    def _extract_author_chicago(self, author: str) -> str:
        """Extract author name in Chicago format (Last, First)."""
        if not author:
            return "Anonymous"
        
        return author.strip()
    
    def _extract_authors_ieee(self, author: str) -> str:
        """Extract authors in IEEE format (A. B., C. D., et al.)."""
        if not author:
            return "Anonymous"
        
        # Handle multiple authors
        authors = [a.strip() for a in author.split(",")]
        
        if len(authors) > 2:
            # A. B., C. D., et al.
            return f"{authors[0]}, {authors[1][0]}., et al."
        elif len(authors) == 2:
            # A. B., C. D.
            return f"{authors[0]}, {authors[1][0]}."
        else:
            return authors[0]
    
    # Year extraction helper
    def _extract_year(self, timestamp) -> Optional[int]:
        """
        Extract year from timestamp.
        
        Args:
            timestamp: Can be datetime object, timestamp in seconds, or None
            
        Returns:
            Year as integer, or "n.d." if unavailable
        """
        if timestamp is None:
            return "n.d."
        
        # If it's a datetime object
        if isinstance(timestamp, datetime):
            return timestamp.year
        
        # If it's a timestamp in seconds
        if isinstance(timestamp, (int, float)):
            return int(timestamp)
        
        return "n.d."
    
    # Style conversion methods
    @classmethod
    def get_available_styles(cls) -> List[str]:
        """Get list of available citation styles."""
        return list(cls.STYLES.keys())
    
    @classmethod
    def get_style_name(cls, style: str) -> str:
        """Get the full name of a citation style."""
        return cls.STYLES.get(style.lower(), style.capitalize())
