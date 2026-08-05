from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from ai.provider_manager import ProviderManager
from brain.citation_builder import Citation, CitationBuilder
from brain.models import ConversationContext
from brain.page_reader import PageContent, PageReader
from brain.research_agent import ResearchAgent, ResearchPlan
from brain.source_ranker import RankedResult, SourceRanker


@dataclass
class ResearchResult:
    """Complete deep research result with all extracted information."""

    query: str
    main_results: list[dict[str, Any]] = field(default_factory=list)
    top_sources: list[RankedResult] = field(default_factory=list)
    page_contents: list[PageContent] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    comparison_data: dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    processing_time: float = 0.0


class DeepResearchManager:
    """
    Orchestrates deep research operations including:
    - Research planning for complex queries
    - Parallel web searches
    - Source ranking
    - Page content extraction
    - Multi-source verification
    - Citation generation
    """

    def __init__(
        self,
        provider_manager: ProviderManager,
        max_workers: int = 5,
        enable_parallel_research: bool = True,
    ):
        """
        Initialize the deep research manager.

        Args:
            provider_manager: AI provider manager for planning
            max_workers: Maximum number of parallel workers for research
            enable_parallel_research: Whether to enable parallel research
        """
        self.provider_manager = provider_manager
        self.max_workers = max_workers
        self.enable_parallel_research = enable_parallel_research

        # Initialize modules
        self.research_agent = ResearchAgent(provider_manager)
        self.source_ranker = SourceRanker()
        self.page_reader = PageReader()
        self.citation_builder = CitationBuilder()

        # Thread pool for parallel operations
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def is_complex_query(self, query: str) -> bool:
        """
        Determine if a query requires deep research.

        Args:
            query: User query

        Returns:
            True if query should use deep research
        """
        # Complex query patterns
        complex_patterns = [
            "compare",
            "versus",
            "vs",
            "difference between",
            "which is better",
            "pros and cons",
            "advantages and disadvantages",
            "research",
            "analyze",
            "summarize",
            "explain",
            "latest",
            "newest",
            "comparison",
        ]

        query_lower = query.lower()

        # Check for complex patterns
        for pattern in complex_patterns:
            if pattern in query_lower:
                return True

        # Also use deep research for queries asking for specific information types
        information_patterns = [
            "latest version",
            "recent news",
            "new feature",
            "security vulnerability",
            "documentation",
            "tutorial",
            "guide",
            "how to",
        ]

        for pattern in information_patterns:
            if pattern in query_lower:
                return True

        return False

    async def perform_research(
        self,
        query: str,
        context: ConversationContext | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> ResearchResult:
        """
        Perform deep research on a query.

        Args:
            query: Research query
            context: Optional conversation context
            on_progress: Optional callback for progress updates

        Returns:
            ResearchResult with all findings
        """
        start_time = asyncio.get_event_loop().time()

        # Check if we need a research plan
        if self.is_complex_query(query):
            if on_progress:
                on_progress("🔍 Analyzing query complexity...")

            plan = self.research_agent.create_plan(query)

            if on_progress:
                on_progress(f"📋 Creating research plan ({plan.total_steps} steps)...")

            if on_progress:
                on_progress(f"🧠 Researching: {plan.main_query}")

            # Execute research plan
            results = await self._execute_research_plan(
                plan,
                context,
                on_progress,
            )
        else:
            # Simple search for non-complex queries
            if on_progress:
                on_progress("🔍 Searching web...")

            results = await self._simple_research(
                query,
                context,
                on_progress,
            )

        # Rank sources
        if results.main_results:
            if on_progress:
                on_progress("📊 Ranking sources...")

            results.top_sources = self.source_ranker.rank_results(
                results.main_results,
                query,
            )

        # Extract page content from top sources
        if results.top_sources and len(results.top_sources) > 0:
            if on_progress:
                on_progress("📄 Reading top sources...")

            results.page_contents = await self._read_top_pages(
                results.top_sources,
                context,
                on_progress,
            )

        # Generate citations
        if results.top_sources:
            if on_progress:
                on_progress("📝 Building citations...")

            results.citations = self.citation_builder.build_citations(
                results.top_sources,
                include_reasoning=True,
                max_citations=5,
            )

        # Calculate confidence score
        results.confidence_score = self._calculate_confidence(results)
        results.processing_time = asyncio.get_event_loop().time() - start_time

        return results

    async def _execute_research_plan(
        self,
        plan: ResearchPlan,
        context: ConversationContext | None,
        on_progress: Callable[[str], None] | None,
    ) -> ResearchResult:
        """
        Execute a research plan with parallel searches.

        Args:
            plan: Research plan to execute
            context: Optional conversation context
            on_progress: Optional callback for progress updates

        Returns:
            ResearchResult with combined findings
        """
        # Group steps by execution order (simple heuristic: steps with lower numbers first)
        steps = sorted(plan.steps, key=lambda s: s.step_number)

        all_results = []
        main_query = plan.main_query

        # For comparison queries, handle specially
        is_comparison_query = (
            "compare" in main_query.lower()
            or "versus" in main_query.lower()
            or "vs" in main_query.lower()
        )

        if is_comparison_query and len(steps) >= 2:
            # Execute first query (Subject 1)
            if on_progress:
                on_progress(f"🔍 {steps[0].description}")

            step1_results = await self._perform_search(
                steps[0].query,
                context,
                on_progress,
            )
            all_results.extend(step1_results)

            # Execute second query (Subject 2) - parallel with extraction
            if on_progress:
                on_progress(f"🔍 {steps[1].description}")

            step2_results = await self._perform_search(
                steps[1].query,
                context,
                on_progress,
            )
            all_results.extend(step2_results)

            # Extract comparison data
            all_results = self._extract_comparison_data(
                all_results,
                steps[0].description,
                steps[1].description,
            )
        else:
            # Execute all steps sequentially
            for step in steps:
                if on_progress:
                    on_progress(f"🔍 {step.description}")

                step_results = await self._perform_search(
                    step.query,
                    context,
                    on_progress,
                )
                all_results.extend(step_results)

        return ResearchResult(
            query=main_query,
            main_results=all_results,
        )

    async def _simple_research(
        self,
        query: str,
        context: ConversationContext | None,
        on_progress: Callable[[str], None] | None,
    ) -> ResearchResult:
        """
        Perform simple research (one search query).

        Args:
            query: Search query
            context: Optional conversation context
            on_progress: Optional callback for progress updates

        Returns:
            ResearchResult with simple search results
        """
        results = await self._perform_search(
            query,
            context,
            on_progress,
        )

        return ResearchResult(
            query=query,
            main_results=results,
        )

    async def _perform_search(
        self,
        query: str,
        context: ConversationContext | None,
        on_progress: Callable[[str], None] | None,
    ) -> list[dict[str, Any]]:
        """
        Perform a single search query.

        Args:
            query: Search query
            context: Optional conversation context
            on_progress: Optional callback for progress updates

        Returns:
            List of search results (dicts)
        """
        # This would call the actual search engine
        # For now, return empty list - will be integrated with WebSearchClient
        return []

    async def _read_top_pages(
        self,
        ranked_results: list[RankedResult],
        context: ConversationContext | None,
        on_progress: Callable[[str], None] | None,
    ) -> list[PageContent]:
        """
        Read content from top-ranked pages.

        Args:
            ranked_results: Ranked search results
            context: Optional conversation context
            on_progress: Optional callback for progress updates

        Returns:
            List of PageContent objects
        """
        page_contents = []

        # Read top 3-5 pages
        num_pages = min(len(ranked_results), 5)

        for i, ranked_result in enumerate(ranked_results[:num_pages]):
            url = ranked_result.result.get("url", "")

            if on_progress:
                on_progress(
                    f"📄 Reading {ranked_result.result.get('title', 'source')} ({i+1}/{num_pages})..."
                )

            try:
                # Read the page
                page_content = self.page_reader.read_page(url)
                page_contents.append(page_content)
            except Exception as exc:
                # Continue even if one page fails
                if on_progress:
                    on_progress(f"⚠️ Failed to read page: {exc}")
                continue

        return page_contents

    def _extract_comparison_data(
        self,
        results: list[dict[str, Any]],
        subject1_description: str,
        subject2_description: str,
    ) -> list[dict[str, Any]]:
        """
        Extract comparison data from search results.

        Args:
            results: Search results
            subject1_description: Description of first subject
            subject2_description: Description of second subject

        Returns:
            Filtered results with comparison data
        """
        # Simple extraction - in reality, this would use NLP to extract
        # features, advantages, disadvantages, etc.
        return results

    def _calculate_confidence(self, result: ResearchResult) -> float:
        """
        Calculate confidence score based on source quality and consistency.

        Args:
            result: Research result

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not result.top_sources:
            return 0.0

        # Calculate average confidence from top sources
        avg_confidence = sum(r.confidence for r in result.top_sources[:5]) / min(
            5, len(result.top_sources)
        )

        # Higher confidence if we have page contents
        if result.page_contents:
            avg_confidence += 0.1

        return min(avg_confidence, 1.0)

    def format_research_summary(
        self,
        result: ResearchResult,
        include_citations: bool = True,
    ) -> str:
        """
        Format research results into a human-readable summary.

        Args:
            result: Research result
            include_citations: Whether to include citations

        Returns:
            Formatted summary
        """
        if not result.main_results:
            return "No results found."

        # Generate a summary using the citations and page contents
        summary_parts = []

        # Add sources used
        if result.top_sources:
            sources_list = ", ".join(
                [r.result.get("title", "") for r in result.top_sources[:5]]
            )
            summary_parts.append(f"Based on {sources_list}")

        # Add key findings from page contents
        if result.page_contents:
            key_findings = []
            for page in result.page_contents[:3]:
                title = page.title
                text = page.main_text[:200]  # First 200 chars
                key_findings.append(f"- {title}: {text}...")

            if key_findings:
                summary_parts.append("\nKey findings:")
                for finding in key_findings:
                    summary_parts.append(finding)

        # Build citation section if requested
        citations_section = ""
        if include_citations and result.citations:
            citations_section = self.citation_builder.build_citations_section(
                result.citations,
                heading="Sources",
            )

        # Combine
        if include_citations:
            return "\n".join(summary_parts) + citations_section
        else:
            return "\n".join(summary_parts)

    def __del__(self):
        """Clean up resources."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)
