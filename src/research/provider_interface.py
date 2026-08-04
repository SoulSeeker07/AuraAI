"""
Research Provider Interface

Abstract base class for all research providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .models import SearchResult, Document, SearchQuery, SourceTrustLevel


class ResearchProvider(ABC):
    """
    Abstract base class for research providers.

    All research providers must implement this interface.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider.

        Args:
            config: Provider configuration
        """
        self.config = config
        self.name = self._get_name()

    @abstractmethod
    def _get_name(self) -> str:
        """
        Get the provider name.

        Returns:
            Provider name
        """
        pass

    @abstractmethod
    def _get_trust_level(self) -> str:
        """
        Get the trust level of this provider.

        Returns:
            Trust level (official, government, github, news, etc.)
        """
        pass

    @abstractmethod
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """
        Perform a search query.

        Args:
            query: Search query
            max_results: Maximum number of results
            **kwargs: Additional provider-specific parameters

        Returns:
            List of search results
        """
        pass

    def fetch_document(self, url: str) -> Optional[Document]:
        """
        Fetch and parse a document from a URL.

        Args:
            url: Document URL

        Returns:
            Parsed document or None if failed
        """
        pass

    def is_available(self) -> bool:
        """
        Check if the provider is available and configured.

        Returns:
            True if available
        """
        return True

    def get_capabilities(self) -> List[str]:
        """
        Get provider capabilities.

        Returns:
            List of capability strings
        """
        return ["search", "document_fetch"]

    def validate_config(self) -> bool:
        """
        Validate provider configuration.

        Returns:
            True if configuration is valid
        """
        return True


class BaseResearchProvider(ResearchProvider):
    """
    Base implementation for research providers.

    Provides common functionality like trust level mapping.
    """

    TRUST_LEVEL_MAP = {
        "official": 5,
        "government": 5,
        "github": 4,
        "news": 4,
        "stackoverflow": 4,
        "wikipedia": 3,
        "reddit": 3,
        "blog": 2,
        "unknown": 1
    }

    def __init__(self, config: Dict[str, Any], name: str, trust_level: str):
        """
        Initialize the base provider.

        Args:
            config: Provider configuration
            name: Provider name
            trust_level: Trust level
        """
        # Set private attributes BEFORE calling super().__init__()
        # This is necessary because super().__init__() calls _get_name()
        # and _get_trust_level(), which rely on these private attributes
        self._name = name
        self._trust_level_str = trust_level
        self._trust_level = self.TRUST_LEVEL_MAP.get(trust_level, 1)
        # Public attribute expected by subclasses (e.g. WikipediaProvider) when
        # constructing SearchResult objects directly
        try:
            self.trust_level = SourceTrustLevel(trust_level)
        except ValueError:
            self.trust_level = SourceTrustLevel.UNKNOWN

        # Now call parent init, which will call _get_name() and _get_trust_level()
        super().__init__(config)

    def _get_name(self) -> str:
        """Get the provider name."""
        return self._name

    def _get_trust_level(self) -> str:
        """Get the trust level of this provider."""
        return self._trust_level_str

    def get_trust_score(self) -> int:
        """
        Get trust score for this provider.

        Returns:
            Trust score (1-5)
        """
        return self.trust_level

    def _parse_search_result(self, raw_data: Dict[str, Any]) -> SearchResult:
        """
        Parse a raw search result.

        Args:
            raw_data: Raw data from search API

        Returns:
            Parsed search result
        """
        return SearchResult(
            url=raw_data.get("url", ""),
            title=raw_data.get("title", ""),
            snippet=raw_data.get("snippet", raw_data.get("description", "")),
            source=self.name,
            score=raw_data.get("score", 50),
            trust_level=self._map_trust_level(raw_data.get("trust_level", self.trust_level_str)),
            raw_data=raw_data
        )

    def _map_trust_level(self, level: str) -> str:
        """
        Map trust level string to enum value.

        Args:
            level: Trust level string

        Returns:
            Trust level enum value
        """
        # Try to find in map, otherwise use default
        for key, value in self.TRUST_LEVEL_MAP.items():
            if level.lower() == key.lower():
                return key
        return "unknown"

    def _extract_relevant_facts(self, text: str, query: str) -> List[str]:
        """
        Extract relevant facts from text.

        Args:
            text: Text to extract facts from
            query: Query for context

        Returns:
            List of relevant facts
        """
        # Simple implementation - can be enhanced with NLP
        words = query.lower().split()
        facts = []
        
        for word in words:
            if word in text.lower():
                # Extract sentence containing the word
                sentences = text.split('.')
                for sentence in sentences:
                    if word in sentence.lower() and len(sentence.strip()) > 20:
                        facts.append(sentence.strip())
                        break
        
        return facts[:5]  # Limit to top 5 facts

    def _create_document_from_html(self, url: str, html: str, title: str = "") -> Document:
        """
        Create a document from HTML content.

        Args:
            url: Document URL
            html: HTML content
            title: Document title

        Returns:
            Parsed document
        """
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract text content
            text = soup.get_text(separator='\n')
            text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
            
            # Extract author if available
            author = soup.find('meta', attrs={'name': 'author'})
            author = author['content'] if author else None
            
            # Extract date if available
            date_meta = soup.find('meta', attrs={'name': 'date'})
            date = date_meta['content'] if date_meta else None
            
            # Extract metadata
            metadata = {}
            for meta in soup.find_all('meta'):
                name = meta.get('name', '')
                content = meta.get('content', '')
                if name and content:
                    metadata[name] = content
            
            document = Document(
                url=url,
                title=title or soup.title.string if soup.title else url,
                content=text[:10000],  # Limit to first 10k chars
                author=author,
                raw_html=html[:5000],  # Limit HTML for storage
                metadata=metadata
            )
            
            # Generate summary
            document.summary = text[:300] + "..." if len(text) > 300 else text
            
            return document
            
        except Exception as e:
            from core import logger
            logger.warning(f"Failed to parse HTML from {url}: {e}")
            return Document(
                url=url,
                title=title or url,
                content=""
            )
