"""
Aura AI Web Search System - Integration Module

This module integrates all the new web search components:
- IntentAnalyzer
- KnowledgeRouter
- LiveSearchEngine
- SearchCache
- SourceRanker
- CitationBuilder
- ResearchAgent
- PageReader
"""

from __future__ import annotations

from typing import Any

from ai.provider_manager import ProviderManager
from brain.citation_builder import CitationBuilder
from brain.live_search_engine import LiveSearchEngine
from brain.models_extended import (
    IntentAnalysis,
    PageContent,
    WebSearchResult,
)
from brain.page_reader import PageReader
from brain.research_agent import ResearchAgent, ResearchPlan
from brain.search_cache import SearchCache
from brain.source_ranker import SourceRanker


class AuraSearchSystem:
    """
    Integrated web search system for Aura AI.
    This is the main entry point that orchestrates all search components.
    """

    def __init__(
        self,
        provider_manager: ProviderManager,
        tavily_api_key: str | None = None,
        max_results: int = 10,
        cache_dir: str = None,
    ):
        """
        Initialize the Aura search system.

        Args:
            provider_manager: AI provider manager
            tavily_api_key: Tavily API key (optional, can use environment variable)
            max_results: Maximum search results
            cache_dir: Directory for search cache
        """
        self.provider_manager = provider_manager

        # Initialize search engine
        self.live_search = LiveSearchEngine(
            api_key=tavily_api_key, max_results=max_results
        )

        # Initialize other components
        self.intent_analyzer = None  # Will be initialized lazily
        self.knowledge_router = None
        self.cache = SearchCache(cache_dir=cache_dir)
        self.ranker = SourceRanker()
        self.citation_builder = CitationBuilder()
        self.research_agent = ResearchAgent(provider_manager)
        self.page_reader = PageReader()

    def initialize_intent_analyzer(self, model: str = "llama3-70b-8192"):
        """
        Initialize the intent analyzer (lazy initialization).

        Args:
            model: Model to use for intent analysis
        """
        if self.intent_analyzer is None:
            self.intent_analyzer = self._create_intent_analyzer(model)

    def _create_intent_analyzer(self, model: str) -> Any:
        """Create intent analyzer instance."""
        # This would import the actual intent analyzer
        # For now, return None as we haven't created it yet
        return None

    def analyze_intent(self, user_input: str) -> IntentAnalysis:
        """
        Analyze user intent for a query.

        Args:
            user_input: User query

        Returns:
            IntentAnalysis result
        """
        self.initialize_intent_analyzer()

        if self.intent_analyzer:
            return self.intent_analyzer.analyze(user_input)
        else:
            # Fallback to simple analysis
            return self._simple_intent_analysis(user_input)

    def _simple_intent_analysis(self, user_input: str) -> IntentAnalysis:
        """Simple fallback intent analysis."""
        input_lower = user_input.lower()

        # Check for news/weather keywords
        if any(word in input_lower for word in ["weather", "score", "stock", "news"]):
            return IntentAnalysis(
                intent="LIVE_INFORMATION",
                confidence=0.8,
                category="live",
                needs_web_search=True,
            )

        # Check for programming keywords
        if any(
            word in input_lower for word in ["python", "javascript", "react", "code"]
        ):
            return IntentAnalysis(
                intent="PROGRAMMING",
                confidence=0.9,
                category="programming",
                needs_web_search=True,
                specialized_sources=["github.com", "stackoverflow.com"],
            )

        # Default
        return IntentAnalysis(
            intent="GENERAL_CHAT",
            confidence=0.5,
            category="general",
            needs_web_search=False,
        )

    def search(
        self,
        query: str,
        intent_analysis: IntentAnalysis | None = None,
        use_cache: bool = True,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        """
        Perform a web search using the integrated system.

        Args:
            query: Search query
            intent_analysis: Intent analysis result (for routing)
            use_cache: Use cache if available
            max_results: Maximum number of results

        Returns:
            List of WebSearchResult objects
        """
        # Check cache first
        if use_cache and intent_analysis:
            cached_results = self.cache.get(
                query=query, category=intent_analysis.category or "default"
            )
            if cached_results:
                # Convert to WebSearchResult objects
                return [
                    WebSearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("snippet", ""),
                        score=r.get("score", 0.0),
                        source_rank=r.get("source_rank", 0),
                    )
                    for r in cached_results
                ]

        # Perform live search
        if intent_analysis:
            routing_config = self.knowledge_router.get_routing_config(
                intent=intent_analysis.intent,
                specialized_sources=intent_analysis.specialized_sources,
            )
        else:
            routing_config = None

        search_results = self.live_search.search(
            query=query,
            limit=max_results,
            routing_config=routing_config,
        )

        # Rank results
        ranked_results = self.rank_results(
            results=[r.__dict__ for r in search_results],
            query=query,
            specialized_sources=(
                intent_analysis.specialized_sources if intent_analysis else None
            ),
        )

        # Store in cache
        if use_cache and intent_analysis:
            self.cache.set(
                query=query,
                results=[r.result for r in ranked_results],
                category=intent_analysis.category or "default",
            )

        # Return ranked results as WebSearchResult objects
        return [
            WebSearchResult(
                title=r.result.get("title", ""),
                url=r.result.get("url", ""),
                snippet=r.result.get("snippet", ""),
                score=r.score,
                source_rank=r.rank,
            )
            for r in ranked_results
        ]

    def rank_results(
        self,
        results: list[dict[str, Any]],
        query: str,
        specialized_sources: list[str] | None = None,
    ) -> list[Any]:
        """
        Rank search results by authority and relevance.

        Args:
            results: List of search result dicts
            query: Original search query
            specialized_sources: User-specified special domains

        Returns:
            List of ranked results
        """
        return self.ranker.rank_results(
            results=results,
            query=query,
            specialized_sources=specialized_sources,
        )

    def read_page(self, url: str) -> PageContent:
        """
        Read and extract content from a webpage.

        Args:
            url: URL to read

        Returns:
            PageContent object
        """
        return self.page_reader.read_page(url)

    def create_research_plan(self, query: str) -> ResearchPlan:
        """
        Create a research plan for a complex query.

        Args:
            query: Research query

        Returns:
            ResearchPlan object
        """
        return self.research_agent.create_plan(query)

    def execute_research(
        self,
        query: str,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """
        Execute research on a query (plans + searches).

        Args:
            query: Research query
            use_cache: Use cache if available

        Returns:
            Research results
        """
        # Check if complex query
        if self.research_agent.is_complex_query(query):
            # Create and execute research plan
            plan = self.create_research_plan(query)
            return self.research_agent.execute_plan(plan)
        else:
            # Simple search
            intent_analysis = self.analyze_intent(query)
            search_results = self.search(
                query=query,
                intent_analysis=intent_analysis,
                use_cache=use_cache,
            )

            return {
                "query": query,
                "type": "simple",
                "results": search_results,
                "citations": self.citation_builder.build_citations(search_results),
            }

    def get_citations(
        self,
        results: list[WebSearchResult],
        max_citations: int = 5,
    ) -> list[Any]:
        """
        Build citation list from search results.

        Args:
            results: Search results
            max_citations: Maximum number of citations

        Returns:
            List of citations
        """
        # Convert WebSearchResult to ranked result format
        ranked_results = [
            type(
                "RankedResult",
                (),
                {
                    "result": {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                    },
                    "score": r.score,
                    "rank": r.source_rank,
                    "reasons": ["ranked_result"],
                },
            )()
            for r in results
        ]

        return self.citation_builder.build_citations(
            ranked_results, max_citations=max_citations
        )

    def get_search_summary(self, results: list[WebSearchResult]) -> str:
        """
        Generate a brief summary of search results.

        Args:
            results: Search results

        Returns:
            Summary string
        """
        if not results:
            return "No search results found."

        return f"Found {len(results)} search results for your query."

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics dict
        """
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the search cache."""
        self.cache.clear_all()
