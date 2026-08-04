"""
Search Manager

Manages multiple search providers and merges their results.
"""

import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

from .models import SearchResult, SearchQuery, SourceTrustLevel, SourceRanking
from .provider_interface import ResearchProvider

logger = logging.getLogger(__name__)


class SearchManager:
    """
    Manages multiple research providers and merges their results.

    Coordinates searches across multiple providers to provide comprehensive results.
    """

    def __init__(self, providers: List[ResearchProvider]):
        """
        Initialize the search manager.

        Args:
            providers: List of research providers
        """
        self.providers = providers
        self.enabled_providers = [p for p in providers if p.is_available()]
        logger.info(f"SearchManager initialized with {len(self.enabled_providers)} providers")

    def search_all(
        self,
        query: str,
        query_obj: Optional[SearchQuery] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search across all enabled providers.

        Args:
            query: Search query
            query_obj: SearchQuery object with additional parameters
            **kwargs: Additional search parameters

        Returns:
            Merged and ranked search results
        """
        if query_obj is None:
            query_obj = SearchQuery(query_text=query, **kwargs)

        logger.info(f"Starting research for: {query}")
        logger.info(f"Search mode: {query_obj.mode.value}, Max results: {query_obj.max_results}")

        # Distribute queries among providers based on mode
        results = []
        
        # For quick mode, use fewer providers
        if query_obj.mode.value == "quick":
            providers_to_use = self._select_providers_for_mode("quick")
        else:
            providers_to_use = self.enabled_providers

        # Execute searches in parallel
        with ThreadPoolExecutor(max_workers=max(1, len(providers_to_use))) as executor:
            future_to_provider = {}
            
            for provider in providers_to_use:
                future = executor.submit(
                    self._search_provider,
                    provider,
                    query,
                    query_obj.max_results
                )
                future_to_provider[future] = provider
            
            # Collect results
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    provider_results = future.result()
                    results.extend(provider_results)
                    logger.info(f"{provider.name} returned {len(provider_results)} results")
                except Exception as e:
                    logger.error(f"Error searching with {provider.name}: {e}")

        # Sort and merge results
        results = self._rank_and_merge(results, query)

        # Apply filters
        results = self._apply_filters(results, query_obj)

        logger.info(f"Research complete: {len(results)} results returned")
        return results

    def _select_providers_for_mode(self, mode: str) -> List[ResearchProvider]:
        """
        Select providers based on search mode.

        Args:
            mode: Search mode (quick, standard, deep)

        Returns:
            List of selected providers
        """
        if mode == "quick":
            # Quick mode: use top 2 providers
            return self.enabled_providers[:2]
        elif mode == "deep":
            # Deep mode: use all providers
            return self.enabled_providers
        else:
            # Standard mode: use top 3 providers
            return self.enabled_providers[:3]

    def _search_provider(
        self,
        provider: ResearchProvider,
        query: str,
        max_results: int
    ) -> List[SearchResult]:
        """
        Search using a single provider.

        Args:
            provider: Research provider
            query: Search query
            max_results: Maximum results

        Returns:
            Search results
        """
        try:
            logger.debug(f"Searching {provider.name} with query: {query}")
            results = provider.search(query, max_results=max_results)

            # Apply provider-level scoring
            for result in results:
                result.source = provider.name
                trust_level_str = provider._get_trust_level()
                result.trust_level = SourceTrustLevel(trust_level_str)
                logger.info(f"[SearchManager] {provider.name} trust_level set: {result.trust_level}, value: {result.trust_level.value}")

            return results
        except Exception as e:
            logger.error(f"Provider {provider.name} search failed: {e}")
            return []

    def _rank_and_merge(
        self,
        results: List[SearchResult],
        query: str
    ) -> List[SearchResult]:
        """
        Rank and merge results from all providers.

        Args:
            results: Unsorted results from all providers
            query: Original query

        Returns:
            Ranked and merged results
        """
        if not results:
            return []

        # Combine all results and remove duplicates
        seen_urls = set()
        unique_results = []
        
        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        # Sort by trust weight, then by relevance score
        unique_results.sort(
            key=lambda r: (r.score * SourceRanking.ALL_WEIGHTS.get(r.trust_level, 1.0), r.score),
            reverse=True
        )

        return unique_results[:50]  # Limit to top 50 results

    def _apply_filters(
        self,
        results: List[SearchResult],
        query_obj: SearchQuery
    ) -> List[SearchResult]:
        """
        Apply filters to results.

        Args:
            results: Results to filter
            query_obj: Query with filter parameters

        Returns:
            Filtered results
        """
        filtered = results

        # Filter by trust score
        if query_obj.min_trust_score > 1:
            filtered = [r for r in filtered if r.score >= query_obj.min_trust_score]

        # Filter by language
        # This would require content analysis, simple implementation here
        # if query_obj.language:
        #     filtered = [r for r in filtered if self._has_language(r, query_obj.language)]

        return filtered

    def _has_language(self, result: SearchResult, language: str) -> bool:
        """
        Check if result has the specified language.

        Args:
            result: Search result
            language: Language code

        Returns:
            True if result appears to be in the specified language
        """
        # Simplified language detection
        # In production, use NLP libraries like langdetect
        if result.snippet:
            snippet = result.snippet.lower()
            return any(lang in snippet for lang in [language, language.upper()])
        return True

    def get_provider_stats(self) -> Dict[str, Any]:
        """
        Get statistics about enabled providers.

        Returns:
            Dictionary with provider statistics
        """
        stats = {
            "total_providers": len(self.enabled_providers),
            "providers": []
        }

        for provider in self.enabled_providers:
            provider_stats = {
                "name": provider.name,
                "capabilities": provider.get_capabilities(),
                "is_available": provider.is_available()
            }
            stats["providers"].append(provider_stats)

        return stats

    def add_provider(self, provider: ResearchProvider) -> None:
        """
        Add a provider to the search manager.

        Args:
            provider: Research provider to add
        """
        if provider.is_available():
            self.enabled_providers.append(provider)
            logger.info(f"Added provider: {provider.name}")

    def remove_provider(self, provider_name: str) -> bool:
        """
        Remove a provider from the search manager.

        Args:
            provider_name: Name of provider to remove

        Returns:
            True if provider was removed
        """
        self.enabled_providers = [
            p for p in self.enabled_providers if p.name != provider_name
        ]
        logger.info(f"Removed provider: {provider_name}")
        return True

    def get_enabled_provider_names(self) -> List[str]:
        """
        Get names of all enabled providers.

        Returns:
            List of provider names
        """
        return [p.name for p in self.enabled_providers]

    def get_best_source(self, results: List[SearchResult]) -> Optional[SearchResult]:
        """
        Get the best source from results.

        Args:
            results: Search results

        Returns:
            Best result or None
        """
        if not results:
            return None
        return results[0]

    def get_top_sources(self, results: List[SearchResult], count: int = 5) -> List[SearchResult]:
        """
        Get top sources from results.

        Args:
            results: Search results
            count: Number of top sources to return

        Returns:
            Top sources
        """
        return results[:count]
