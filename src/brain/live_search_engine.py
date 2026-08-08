from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import tavily
    from tavily.exceptions import TavilyError
except ImportError:
    tavily = None
    TavilyError = Exception

from brain.models import WebSearchResult


@dataclass
class SearchOptions:
    """Options for configuring the search."""

    max_results: int = 10
    search_depth: str = "basic"
    time_range: int | None = None  # 1 = last day, 7 = last week, 30 = last month
    include_domains: list[str] = None
    exclude_domains: list[str] = None
    include_answer: bool = False
    include_raw_content: bool = False
    include_images: bool = False
    include_image_descriptions: bool = False
    include_domains_page_score: bool = False


class LiveSearchEngine:
    """
    Live search engine using Tavily API.
    Provides high-quality search results with AI-optimized summaries.
    """

    SEARCH_DEPTHS = {
        "basic": "quick search using Tavily's search capabilities",
        "advanced": "deeper search with higher quality results",
    }

    def __init__(
        self,
        api_key: str | None = None,
        max_results: int = 10,
        timeout_seconds: float = 15.0,
    ):
        """
        Initialize the live search engine.

        Args:
            api_key: Tavily API key (set via TAVILY_API_KEY env var or constructor)
            max_results: Maximum number of results to return
            timeout_seconds: Timeout for search requests
        """
        self.api_key = api_key or self._get_api_key()
        self.max_results = max_results
        self.timeout_seconds = timeout_seconds

        if tavily is not None and self.api_key:
            self.client = tavily.Client(api_key=self.api_key)
        else:
            self.client = None

    def _get_api_key(self) -> str | None:
        """Get API key from environment variable."""
        import os

        return os.environ.get("TAVILY_API_KEY")

    def search(
        self,
        query: str,
        limit: int | None = None,
        routing_config: dict[str, Any] | None = None,
        search_depth: str = "basic",
    ) -> list[WebSearchResult]:
        """
        Perform a live web search using Tavily API.

        Args:
            query: Search query string
            limit: Maximum number of results (defaults to max_results)
            routing_config: Routing configuration from KnowledgeRouter
            search_depth: "basic" or "advanced" search

        Returns:
            List of WebSearchResult objects
        """
        if not self.client:
            raise ValueError(
                "Tavily API key is required. Set TAVILY_API_KEY environment variable "
                "or pass api_key to LiveSearchEngine constructor."
            )

        # Determine actual limit
        actual_limit = min(limit or self.max_results, 20)  # Max 20 results

        # Build search options
        options = SearchOptions(
            max_results=actual_limit,
            search_depth=search_depth,
            include_domains=routing_config.get("priority") if routing_config else None,
            exclude_domains=routing_config.get("exclude") if routing_config else None,
        )

        try:
            # Perform search
            results = self.client.search(
                query=query,
                max_results=actual_limit,
                search_depth=search_depth,
                include_domains=options.include_domains,
                exclude_domains=options.exclude_domains,
            )

            # Convert to WebSearchResult objects
            search_results: list[WebSearchResult] = []
            for result in results.get("results", []):
                title = result.get("title", "").strip()
                url = result.get("url", "").strip()
                snippet = result.get("answer") or result.get("snippet", "").strip()

                if title and url:
                    search_results.append(
                        WebSearchResult(title=title, url=url, snippet=snippet or "")
                    )

            return search_results

        except TavilyError as exc:
            # Handle specific Tavily errors
            if "rate limit" in str(exc).lower():
                raise ValueError("Tavily API rate limit exceeded. Try again later.")
            elif "invalid api key" in str(exc).lower():
                raise ValueError(
                    "Invalid Tavily API key. Please check your configuration."
                )
            else:
                raise ValueError(f"Search failed: {exc}")

        except Exception as exc:
            raise ValueError(f"Search error: {exc}")

    def search_with_context(
        self,
        query: str,
        context_results: list[dict[str, Any]],
        routing_config: dict[str, Any] | None = None,
    ) -> list[WebSearchResult]:
        """
        Perform a search that builds on existing context results.
        Useful for follow-up queries.

        Args:
            query: Follow-up search query
            context_results: Existing search results to use as context
            routing_config: Routing configuration

        Returns:
            List of WebSearchResult objects
        """
        # Extract domains from context for focused search
        include_domains = [
            r.get("url", "").split("/")[2] for r in context_results if r.get("url")
        ]

        # Deduplicate and filter
        include_domains = list(set(include_domains))

        # Build search options with domain focus
        options = SearchOptions(
            max_results=min(len(include_domains) + 5, 15),
            include_domains=include_domains,
        )

        try:
            results = self.client.search(
                query=query,
                max_results=options.max_results,
                search_depth="basic",
                include_domains=options.include_domains,
            )

            search_results: list[WebSearchResult] = []
            for result in results.get("results", []):
                title = result.get("title", "").strip()
                url = result.get("url", "").strip()
                snippet = result.get("answer") or result.get("snippet", "").strip()

                if title and url:
                    search_results.append(
                        WebSearchResult(title=title, url=url, snippet=snippet or "")
                    )

            return search_results

        except Exception as exc:
            raise ValueError(f"Context search failed: {exc}")

    def get_search_summary(self, results: list[WebSearchResult]) -> str:
        """
        Generate a brief summary of search results.

        Args:
            results: List of search results

        Returns:
            Human-readable summary
        """
        if not results:
            return "No search results found."

        return f"Found {len(results)} search results for your query."
