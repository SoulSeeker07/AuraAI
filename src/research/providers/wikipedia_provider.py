"""
Wikipedia Research Provider

Provides research capabilities from Wikipedia.
"""

import logging
from typing import Any

import wikipedia
from wikipedia import WikipediaPage
from wikipedia import search as wiki_search
from wikipedia.exceptions import DisambiguationError, PageError

from ..content_fetcher import ContentFetcher
from ..models import SearchResult
from ..provider_interface import BaseResearchProvider

logger = logging.getLogger(__name__)

# Wikipedia's API blocks/soft-fails requests without a descriptive User-Agent,
# which otherwise surfaces as a confusing JSONDecodeError deep inside the
# wikipedia package ("Expecting value: line 1 column 1 (char 0)").
wikipedia.set_user_agent(
    "AuraAI-JarvisAssistant/1.0 (research provider; contact: you@example.com)"
)


class WikipediaProvider(BaseResearchProvider):
    """
    Wikipedia API research provider.

    Provides structured information from Wikipedia articles.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Wikipedia provider.

        Args:
            config: Provider configuration
        """
        super().__init__(config, name="wikipedia", trust_level="wikipedia")
        self.content_fetcher = ContentFetcher()

    def search(self, query: str, max_results: int = 10, **kwargs) -> list[SearchResult]:
        """
        Search Wikipedia.

        Args:
            query: Search query
            max_results: Maximum number of results
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        results = []
        query = query.strip()

        try:
            # Perform Wikipedia search
            search_results = wiki_search(query, results=2 * max_results)

            # Fetch pages for each result
            for title in search_results[:max_results]:
                try:
                    result = self._fetch_wikipedia_page(title)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"Failed to fetch Wikipedia page {title}: {e}")

            logger.info(f"Wikipedia search returned {len(results)} results")
            return results

        except DisambiguationError:
            # Handle disambiguation pages
            logger.debug(f"Wikipedia disambiguation for {query}")
            return results
        except Exception as e:
            logger.error(f"Wikipedia search error: {e}")
            return []

    def _fetch_wikipedia_page(self, title: str) -> SearchResult | None:
        """
        Fetch a Wikipedia page.

        Args:
            title: Page title

        Returns:
            Search result or None
        """
        try:
            page = WikipediaPage(title)

            # Create a document for fetching
            doc = self.content_fetcher.fetch(page.url)

            return SearchResult(
                url=page.url,
                title=page.title,
                snippet=page.summary[:300],
                source=self.name,
                score=95,  # Wikipedia is generally trusted
                trust_level=self.trust_level,
                document=doc,
                raw_data={
                    "url": page.url,
                    "title": page.title,
                    "summary": page.summary,
                    "content_length": len(page.content),
                    "categories": page.categories,
                },
            )

        except PageError:
            logger.debug(f"Wikipedia page not found: {title}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch Wikipedia page {title}: {e}")
            return None

    def get_page(self, title: str) -> dict[str, Any] | None:
        """
        Get detailed information about a Wikipedia page.

        Args:
            title: Page title

        Returns:
            Page information or None
        """
        try:
            page = WikipediaPage(title)

            return {
                "title": page.title,
                "url": page.url,
                "summary": page.summary,
                "content": page.content,
                "categories": page.categories,
                "infobox": page.infobox,
                "references": page.references,
                "images": page.images,
            }

        except PageError:
            logger.warning(f"Wikipedia page not found: {title}")
            return None
        except Exception as e:
            logger.error(f"Failed to get Wikipedia page {title}: {e}")
            return None

    def search_with_categories(self, query: str) -> list[dict[str, Any]]:
        """
        Search Wikipedia with category filtering.

        Args:
            query: Search query

        Returns:
            List of results with categories
        """
        results = []

        try:
            search_results = wiki_search(query, results=20)

            for title in search_results:
                info = self.get_page(title)
                if info:
                    results.append(info)

        except Exception as e:
            logger.error(f"Wikipedia search with categories error: {e}")

        return results

    def get_category(self, category: str, limit: int = 20) -> list[str]:
        """
        Get pages in a category.

        Args:
            category: Category name
            limit: Number of pages to return

        Returns:
            List of page titles
        """
        try:
            from wikipedia import page

            cat_page = page(category)

            # Get links from the category page
            links = cat_page.links[:limit]

            logger.info(f"Found {len(links)} pages in category {category}")
            return links

        except Exception as e:
            logger.error(f"Failed to get category {category}: {e}")
            return []

    def get_capabilities(self) -> list[str]:
        """Get provider capabilities."""
        return ["search", "page_info", "categories"]

    def validate_config(self) -> bool:
        """Validate provider configuration."""
        # Wikipedia doesn't require API keys
        return True
