"""
Tavily Research Provider

Uses Tavily API for web searches.
"""

import logging
from typing import Any

import requests

from ..content_fetcher import ContentFetcher
from ..models import SearchResult
from ..provider_interface import BaseResearchProvider

logger = logging.getLogger(__name__)


class TavilyProvider(BaseResearchProvider):
    """
    Tavily API research provider.

    Provides web search capabilities through Tavily API.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Tavily provider.

        Args:
            config: Provider configuration
        """
        api_key = config.get("api_key")
        super().__init__(config, name="tavily", trust_level="official")
        self.api_key = api_key
        self.content_fetcher = ContentFetcher()

    def is_available(self) -> bool:
        """Check if Tavily API is available and configured."""
        return bool(self.api_key)

    def search(self, query: str, max_results: int = 10, **kwargs) -> list[SearchResult]:
        """
        Perform search using Tavily API.

        Args:
            query: Search query
            max_results: Maximum number of results
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        if not self.is_available():
            logger.warning("Tavily API key not configured")
            return []

        try:
            # Build API request
            url = "https://api.tavily.com/search"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            params = {
                "api_key": self.api_key,
                "q": query,
                "max_results": min(max_results, 20),  # Tavily limit
                "include_images": False,
                "include_answer": True,
                "include_raw_content": False,
                "include_domains": kwargs.get("include_domains"),
                "exclude_domains": kwargs.get("exclude_domains"),
                "search_depth": kwargs.get("search_depth", "basic"),
                "topic": kwargs.get("topic", "general"),
            }

            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            logger.debug(f"Tavily search: {query}")

            # Make API request
            response = requests.post(url, headers=headers, json=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse results
            results = []
            for item in data.get("results", []):
                result = self._parse_result(item)
                results.append(result)

            logger.info(f"Tavily returned {len(results)} results")
            return results

        except requests.RequestException as e:
            logger.error(f"Tavily API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []

    def _parse_result(self, raw_data: dict[str, Any]) -> SearchResult:
        """
        Parse a raw Tavily result.

        Args:
            raw_data: Raw result from Tavily API

        Returns:
            Parsed search result
        """
        # Tavily provides title, url, and content
        # We can use the answer field if available
        answer = raw_data.get("answer")

        return SearchResult(
            url=raw_data.get("url", ""),
            title=raw_data.get("title", ""),
            snippet=raw_data.get("content", raw_data.get("answer", "")),
            source=self.name,
            score=raw_data.get("score", 50),
            trust_level=self.trust_level,
            raw_data=raw_data,
        )

    def fetch_document(self, url: str) -> Any | None:
        """
        Fetch document using content fetcher.

        Args:
            url: Document URL

        Returns:
            Document or None
        """
        return self.content_fetcher.fetch(url)

    def get_capabilities(self) -> list[str]:
        """Get provider capabilities."""
        return ["search", "document_fetch"]

    def validate_config(self) -> bool:
        """Validate provider configuration."""
        if not self.api_key:
            logger.warning("Tavily API key not set")
            return False
        return True
