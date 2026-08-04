"""
Research Engine

Main orchestrator for research operations.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import time
from pathlib import Path
from collections import defaultdict

from .models import (
    SearchQuery, SearchResult, ResearchReport,
    ResearchConfig, SearchMode, SourceTrustLevel, ConflictResolution, Document,
    Evidence, SourceRanking
)
from .citation_builder import Citation
from .search_manager import SearchManager
from .content_fetcher import ContentFetcher
from .cache_manager import CacheManager
from .research_planner import ResearchPlanner, ResearchMode as PlannerMode
from .reasoning_layer import ResearchReasoner
from .research_context import ResearchContext, ResearchMode
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


class ResearchEngine:
    """
    Main orchestrator for research operations.

    Handles research decision-making, coordination, merging,
    and report generation.
    """

    def __init__(self, config: Optional[ResearchConfig] = None, settings_path: Optional[str] = None):
        """
        Initialize the research engine.

        Args:
            config: Research configuration
            settings_path: Path to settings.json file for provider configurations
        """
        self.config = config or ResearchConfig()
        self.search_manager = None
        self.content_fetcher = ContentFetcher()
        self.cache_manager = CacheManager(self.config.cache_ttl)
        self.planner = ResearchPlanner()
        self.reasoner = ResearchReasoner(debug=self.config.debug)

        # Load provider configurations from settings.json
        self._provider_configs = self._load_provider_configs(settings_path)

        # Initialize providers
        providers = []

        # Import each provider independently so one missing dependency
        # (e.g. the 'wikipedia' package) doesn't take down all providers.
        TavilyProvider = None
        GitHubProvider = None
        WikipediaProvider = None

        try:
            from .providers import TavilyProvider
        except ImportError as e:
            logger.warning(f"TavilyProvider unavailable: {e}")

        try:
            from .providers import GitHubProvider
        except ImportError as e:
            logger.warning(f"GitHubProvider unavailable: {e}")

        try:
            from .providers import WikipediaProvider
        except ImportError as e:
            logger.warning(f"WikipediaProvider unavailable: {e}")

        # Get research settings
        research_settings = self._provider_configs.get("research", {})
        providers_settings = research_settings.get("providers", {})

        # Initialize TavilyProvider
        if TavilyProvider:
            try:
                if providers_settings.get("tavily", {}).get("enabled", True):
                    tavily_config = providers_settings.get("tavily", {})
                    api_key = tavily_config.get("api_key", "")
                    provider_config = {"api_key": api_key} if api_key else {}
                    tavily = TavilyProvider(config=provider_config)
                    providers.append(tavily)
                    logger.info("TavilyProvider initialized successfully")
                else:
                    logger.info("TavilyProvider is disabled")
            except Exception as e:
                logger.warning(f"Could not initialize TavilyProvider: {e}")

        # Initialize GitHubProvider
        if GitHubProvider:
            try:
                if providers_settings.get("github", {}).get("enabled", True):
                    github_config = providers_settings.get("github", {})
                    api_token = github_config.get("api_token", "")
                    provider_config = {"api_token": api_token} if api_token else {}
                    github = GitHubProvider(config=provider_config)
                    providers.append(github)
                    logger.info("GitHubProvider initialized successfully")
                else:
                    logger.info("GitHubProvider is disabled")
            except Exception as e:
                logger.warning(f"Could not initialize GitHubProvider: {e}")

        # Initialize WikipediaProvider
        if WikipediaProvider:
            try:
                if providers_settings.get("wikipedia", {}).get("enabled", True):
                    provider_config = {}
                    wikipedia = WikipediaProvider(config=provider_config)
                    providers.append(wikipedia)
                    logger.info("WikipediaProvider initialized successfully")
                else:
                    logger.info("WikipediaProvider is disabled")
            except Exception as e:
                logger.warning(f"Could not initialize WikipediaProvider: {e}")

        # Create search manager with available providers
        self.search_manager = SearchManager(providers)
        logger.info(f"Research Engine initialized with {len(providers)} providers")

    def _load_provider_configs(self, settings_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load provider configurations from settings.json.

        Args:
            settings_path: Path to settings.json file

        Returns:
            Dictionary of provider configurations
        """
        if not settings_path:
            # Default to workspace root settings.json
            workspace_root = Path(__file__).parent.parent.parent.parent.parent
            settings_path = workspace_root / "settings.json"
        
        try:
            settings_file = Path(settings_path)
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                logger.info(f"Loaded provider configurations from {settings_path}")
                return settings
            else:
                logger.warning(f"Settings file not found at {settings_path}")
                return {}
        except Exception as e:
            logger.warning(f"Failed to load provider configurations: {e}")
            return {}

    def research(
        self,
        query: str,
        mode: Optional[SearchMode] = None,
        **kwargs
    ) -> ResearchReport:
        """
        Perform research on a query.

        Args:
            query: Research query
            mode: Search mode (quick, standard, deep)
            **kwargs: Additional search parameters

        Returns:
            Research report
        """
        # Check if research is enabled
        if not self.config.enabled:
            logger.warning("Research Engine is disabled")
            return self._create_empty_report(query)

        # Create metrics collector
        metrics = MetricsCollector(query=query)

        # Create search query
        search_mode = mode or self.config.default_mode
        query_obj = SearchQuery(
            query_text=query,
            mode=search_mode,
            **kwargs
        )

        # Check cache first
        cache_key = self._get_cache_key(query_obj)
        if self.cache_manager.has_cache(cache_key):
            logger.info(f"Returning cached results for: {query}")
            metrics.stop_timer('search')
            metrics.finalize()
            metrics.print_summary()
            return self.cache_manager.get(cache_key)

        # Start research timing
        metrics.start_timer('planning')

        # Execute research using the new planner + reasoning layer
        context = self._execute_research(query_obj, metrics_collector=metrics)

        # Stop timing
        metrics.stop_timer('planning')
        metrics.finalize()

        # Cache results (only cache if reasonably fast)
        duration = metrics.total_ms
        if duration < 60000:
            cache_key = self._get_cache_key(query_obj)
            self.cache_manager.set(
                cache_key,
                report=None,
                results=context.evidence,
                query_obj=query_obj
            )
            logger.info(f"Cached results for: {query}")

        return context

    def _execute_research(
        self,
        query_obj: SearchQuery,
        max_iterations: int = 3,
        metrics_collector: Optional[MetricsCollector] = None
    ) -> ResearchContext:
        """
        Execute research using the planner, reasoning layer, and confidence loop.

        This is the NEW implementation that includes:
        1. Research planning before execution
        2. Parallel search of plan steps
        3. Evidence reasoning and confidence evaluation
        4. Iterative refinement until confidence threshold is met

        Args:
            query_obj: Search query object
            max_iterations: Maximum number of planning iterations
            metrics_collector: Optional metrics collector for timing

        Returns:
            ResearchContext with all findings and reasoning
        """
        query = query_obj.query_text
        mode = query_obj.mode or self.config.default_mode

        if metrics_collector:
            metrics_collector.start_timer('search')

        logger.info(f"Starting research for: {query}")
        logger.info(f"Research mode: {mode}")

        # Convert search mode to planner mode
        planner_mode = PlannerMode.STANDARD
        if mode == SearchMode.QUICK:
            planner_mode = PlannerMode.QUICK
        elif mode == SearchMode.DEEP:
            planner_mode = PlannerMode.DEEP

        # Create initial plan
        plan = self.planner.create_plan(query, mode=planner_mode)
        logger.info(f"Created plan with {len(plan.steps)} steps")

        # Track all evidence across iterations
        all_evidence = []
        all_citations = []

        # Confidence loop - continue until confidence threshold is met
        iteration = 0
        should_continue = True

        # Log iteration summary block
        iteration_summaries = []

        while should_continue and iteration < max_iterations:
            if metrics_collector:
                metrics_collector.start_timer('extraction')

            iteration += 1

            # Log iteration header
            logger.info(f"\n{'='*50}")
            logger.info(f"Iteration {iteration}")
            logger.info(f"{'='*50}")

            # Log current confidence before this iteration
            if iteration > 1:
                logger.info(f"Previous Confidence: {iteration_summaries[-1]['confidence']:.2f}")

            logger.info(f"Executing research plan with {len(plan.steps)} steps")

            # Execute each step in the plan
            step_results = []

            for step in plan.steps:
                logger.info(f"  Executing step: {step.query[:50]}...")

                # Execute search for this step
                try:
                    metrics_collector.start_timer('search')
                    search_results = self.search_manager.search_all(
                        query=step.query,
                        query_obj=query_obj
                    )

                    # Fetch documents
                    metrics_collector.start_timer('extraction')
                    documents = self._fetch_documents(search_results)

                    # Merge and rank
                    ranked_results = self._merge_results(search_results, documents)

                    # Create evidence from results
                    evidence = self._create_evidence_from_results(
                        ranked_results,
                        step.query
                    )

                    metrics_collector.stop_timer('extraction')

                    step_results.extend(evidence)

                    # Extract citations
                    citations = self._create_citations(ranked_results)
                    all_citations.extend(citations)

                except Exception as e:
                    logger.warning(f"Step failed: {e}")

            # Add new evidence to collection
            all_evidence.extend(step_results)

            if metrics_collector:
                metrics_collector.stop_timer('search')

            # Use reasoning layer to evaluate all evidence
            if metrics_collector:
                metrics_collector.start_timer('reasoning')

            reasoning_result = self.reasoner.reason(all_evidence, query)

            if metrics_collector:
                metrics_collector.stop_timer('reasoning')

            # Capture iteration summary
            iteration_summaries.append({
                'iteration': iteration,
                'strong_evidence': len(reasoning_result.strong_evidence),
                'weak_evidence': len(reasoning_result.weak_evidence),
                'confidence': reasoning_result.confidence
            })

            # Check if we should continue to next iteration
            should_continue = self._should_continue_research(
                reasoning_result.confidence,
                iteration,
                max_iterations,
                reasoning_result
            )

            # Log iteration results
            logger.info(
                f"\nIteration {iteration} complete: "
                f"{len(reasoning_result.strong_evidence)} strong, "
                f"{len(reasoning_result.weak_evidence)} weak, "
                f"confidence: {reasoning_result.confidence:.2f}"
            )

            # Log confidence vs threshold
            logger.info(f"Threshold: {self.planner.confidence_threshold:.2f}")
            logger.info(f"Continue: {should_continue}")

            if should_continue and reasoning_result.conflicts:
                logger.info(f"Conflicts detected: {len(reasoning_result.conflicts)}")

            # Refine the plan if we should continue
            if should_continue:
                # Refine the plan based on missing information and recommendations
                if reasoning_result.missing_information and iteration < max_iterations:
                    new_steps = self.planner.refine_plan(
                        query,
                        reasoning_result.missing_information,
                        reasoning_result.recommendations
                    )
                    plan.steps = new_steps
                    logger.info(f"Refined plan: {len(plan.steps)} steps")
                else:
                    logger.info("No refinement needed")

        # Stop timing after all research steps complete
        if metrics_collector:
            metrics_collector.stop_timer('search')
            metrics_collector.finalize()
            metrics_collector.print_summary()

        # Create final ResearchContext
        final_context = ResearchContext(
            query=query,
            mode=ResearchMode.from_search_mode(mode),
            evidence=reasoning_result.strong_evidence + reasoning_result.weak_evidence,
            citations=all_citations,
            confidence=reasoning_result.confidence,
            conflicts=reasoning_result.conflicts,
            unanswered_questions=reasoning_result.missing_information,
            recommendations=reasoning_result.recommendations,
            metadata={
                'iterations': iteration,
                'total_evidence': len(all_evidence),
                'reasoning': {
                    'strong_evidence': len(reasoning_result.strong_evidence),
                    'weak_evidence': len(reasoning_result.weak_evidence),
                    'confidence': reasoning_result.confidence
                }
            }
        )

        # Log comprehensive research summary
        logger.info(f"\n{'='*70}")
        logger.info("=============== Research Summary ================")
        logger.info(f"{'='*70}")

        logger.info("\nGoal")
        logger.info(f"----")
        logger.info(f"{query}")

        logger.info("\nIterations")
        logger.info(f"----------")
        logger.info(f"{iteration}")

        # Log providers used (from search manager's available providers)
        logger.info("\nProviders Used")
        logger.info(f"--------------")
        providers_used = list(self.search_manager.providers.keys()) if self.search_manager else ["None"]
        for provider in providers_used:
            logger.info(f"  - {provider}")

        logger.info("\nEvidence")
        logger.info(f"--------")
        logger.info(f"Strong : {len(reasoning_result.strong_evidence)}")
        logger.info(f"Weak   : {len(reasoning_result.weak_evidence)}")

        logger.info("\nConflicts")
        logger.info(f"---------")
        logger.info(f"{len(reasoning_result.conflicts)}")

        logger.info("\nConfidence")
        logger.info(f"----------")
        logger.info(f"{final_context.confidence:.2f}")

        logger.info("\nDecision")
        logger.info(f"--------")

        # Determine stop reason
        stop_reason = []
        if reasoning_result.confidence >= self.planner.confidence_threshold:
            stop_reason.append("✓ Confidence reached threshold")
        if iteration >= max_iterations:
            stop_reason.append("✓ Max iterations reached")
        if not reasoning_result.missing_information:
            stop_reason.append("✓ No additional information needed")
        if not should_continue and reasoning_result.confidence < self.planner.confidence_threshold:
            stop_reason.append("✓ Provider exhaustion or other stop condition")

        logger.info("\nStopping because:")
        for reason in stop_reason:
            logger.info(f"  {reason}")

        logger.info(f"\n{'='*70}")
        logger.info(f"=============== Research Complete ================")
        logger.info(f"{'='*70}\n")

        # Add Research Trace block (final comprehensive summary)
        self._log_research_trace(query, iteration, should_continue, reasoning_result, final_context, duration)

        return final_context

    def _fetch_documents(self, results: List[SearchResult]) -> Dict[str, Document]:
        """
        Fetch documents from search results.

        Args:
            results: Search results

        Returns:
            Dictionary mapping URLs to documents
        """
        documents = {}
        
        # Limit document fetching to top 5-10 results
        for result in results[:10]:
            if result.url not in documents:
                try:
                    document = self.content_fetcher.fetch(result.url)
                    if document and document.content:
                        result.document = document
                        documents[result.url] = document
                except Exception as e:
                    logger.debug(f"Failed to fetch {result.url}: {e}")

        return documents

    def _merge_results(
        self,
        results: List[SearchResult],
        documents: Dict[str, Document]
    ) -> List[SearchResult]:
        """
        Merge and rank results.

        Args:
            results: Raw search results
            documents: Parsed documents

        Returns:
            Merged and ranked results
        """
        # Merge documents with results
        for result in results:
            if result.url in documents:
                result.document = documents[result.url]

        # Apply additional ranking based on document quality
        ranked_results = []
        for result in results:
            score = result.score
            
            # Boost results with well-formed documents
            if result.document and result.document.content:
                score += result.document.summary.count(" ") / 10  # Bonus for length
                score += result.document.content_type == "documentation" * 10

            result.score = min(100, score)
            ranked_results.append(result)

        # Sort by score
        ranked_results.sort(key=lambda r: r.score, reverse=True)
        
        return ranked_results

    def _extract_facts(
        self,
        results: List[SearchResult],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Extract relevant facts from results.

        Args:
            results: Search results
            query: Original query

        Returns:
            List of extracted facts
        """
        facts = []

        for result in results:
            if result.document and result.document.content:
                # Extract facts from document
                doc_facts = self.content_fetcher.extract_facts(
                    result.document,
                    query
                )
                facts.extend(doc_facts)

        return facts

    def _create_report(
        self,
        query: str,
        results: List[SearchResult],
        duration: float
    ) -> ResearchReport:
        """
        Create a research report.

        Args:
            query: Original query
            results: Search results
            duration: Research duration

        Returns:
            Research report
        """
        report = ResearchReport(
            query=query,
            results=results,
            timestamp=datetime.now(),
            duration=duration
        )

        # Create citations
        report.citations = self._create_citations(results)

        # Identify conflicts
        report.conflicts = self._identify_conflicts(results)

        # Extract summary
        report.summary = self._generate_summary(results)

        # Build detailed findings
        report.detailed_findings = self._build_detailed_findings(results)

        # Extract key statistics
        report.key_stats = self._extract_key_stats(results)

        # Identify primary sources
        report.primary_sources = self._identify_primary_sources(results)

        return report

    def _create_citations(self, results: List[SearchResult]) -> List[Citation]:
        """
        Create citations from search results.

        Args:
            results: Search results

        Returns:
            List of citations
        """
        citations = []

        for i, result in enumerate(results[:10], start=1):  # Top 10 sources
            trust_level_str = (
                result.trust_level.value
                if isinstance(result.trust_level, SourceTrustLevel)
                else str(result.trust_level)
            )
            citation = Citation(
                id=i,
                source=result.source,
                title=result.title,
                url=result.url,
                trust_level=trust_level_str,
                confidence=result.score / 100.0,  # score is 0-100, Citation wants 0-1
                evidence_ids=[i],
            )
            citations.append(citation)

        return citations

    def _identify_conflicts(self, results: List[SearchResult]) -> List[Dict[str, Any]]:
        """
        Identify conflicts between sources.

        Args:
            results: Search results

        Returns:
            List of conflicts
        """
        conflicts = []
        
        # Simple conflict detection: check if multiple sources contradict
        # In production, use NLP for semantic conflict detection
        texts = [r.snippet for r in results if r.snippet]
        
        if len(texts) < 5:
            return conflicts

        # Count word frequency
        word_counts = defaultdict(int)
        for text in texts:
            words = text.lower().split()
            for word in words:
                if len(word) > 5 and word.isalnum():
                    word_counts[word] += 1

        # Find words that appear in many sources (potential conflicts)
        for word, count in word_counts.items():
            if count >= 3:
                conflicts.append({
                    "word": word,
                    "sources": count,
                    "severity": "high" if count >= 5 else "medium"
                })

        return conflicts

    def _generate_summary(self, results: List[SearchResult]) -> str:
        """
        Generate a summary of the research.

        Args:
            results: Search results

        Returns:
            Summary text
        """
        if not results:
            return "No results found."

        # Combine top snippets
        snippets = [r.snippet for r in results[:5] if r.snippet]
        combined = ". ".join(snippets[:3])

        return combined[:500] + "..." if len(combined) > 500 else combined

    def _build_detailed_findings(
        self,
        results: List[SearchResult]
    ) -> Dict[str, Any]:
        """
        Build detailed findings.

        Args:
            results: Search results

        Returns:
            Detailed findings dictionary
        """
        findings = {
            "total_sources": len(results),
            "trust_distribution": self._get_trust_distribution(results),
            "top_sources": [
                {"url": r.url, "title": r.title, "score": r.score}
                for r in results[:10]
            ]
        }

        return findings

    def _extract_key_stats(
        self,
        results: List[SearchResult]
    ) -> Dict[str, Any]:
        """
        Extract key statistics.

        Args:
            results: Search results

        Returns:
            Key statistics
        """
        stats = {
            "source_count": len(results),
            "confidence_score": sum(r.score for r in results) / len(results) if results else 0,
            "evidence_count": len(results) * 2,  # Estimate: 2 evidence items per source
            "average_trust_score": self._get_average_trust_score(results)
        }

        return stats

    def _identify_primary_sources(self, results: List[SearchResult]) -> List[str]:
        """
        Identify primary sources.

        Args:
            results: Search results

        Returns:
            List of primary source URLs
        """
        primary = []
        
        for result in results[:5]:
            # Official sources first
            if result.trust_level == SourceTrustLevel.OFFICIAL:
                primary.append(result.url)
            # Government sources second
            elif result.trust_level == SourceTrustLevel.GOVERNMENT:
                primary.append(result.url)
            # High-trust sources
            elif result.score > 70:
                primary.append(result.url)
        
        return primary

    def _get_trust_distribution(self, results: List[SearchResult]) -> Dict[str, int]:
        """
        Get distribution of trust levels.

        Args:
            results: Search results

        Returns:
            Trust level distribution
        """
        distribution = {level.value: 0 for level in SourceTrustLevel}
        
        for result in results:
            trust = result.trust_level.value
            distribution[trust] += 1
        
        return distribution

    def _get_average_trust_score(self, results: List[SearchResult]) -> float:
        """
        Get average trust score.

        Args:
            results: Search results

        Returns:
            Average trust score
        """
        if not results:
            return 0.0
        return sum(r.score for r in results) / len(results)

    def _get_cache_key(self, query_obj: SearchQuery) -> str:
        """
        Generate cache key for a query.

        Args:
            query_obj: Search query

        Returns:
            Cache key
        """
        import hashlib
        import json
        
        data = {
            "query": query_obj.query_text,
            "mode": query_obj.mode.value,
            "max_results": query_obj.max_results,
            "language": query_obj.language
        }
        
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _create_empty_report(self, query: str) -> ResearchReport:
        """Create an empty report."""
        return ResearchReport(
            query=query,
            results=[],
            summary="Research Engine is disabled"
        )

    def _create_error_report(
        self,
        query: str,
        error: str,
        duration: float
    ) -> ResearchReport:
        """Create an error report."""
        report = ResearchReport(
            query=query,
            results=[],
            summary=f"Research failed: {error}",
            duration=duration
        )
        report.metadata["error"] = error
        return report

    def is_research_needed(self, query: str) -> bool:
        """
        Determine if research is needed for a query.

        Args:
            query: Query to check

        Returns:
            True if research is needed
        """
        # Research is needed for queries that require live data
        research_keywords = [
            "latest", "newest", "today", "currently", "latest update",
            "recent", "recently", "current version", "released",
            "recent news", "breaking", "latest update", "bug report",
            "driver", "update", "patch", "fix", "security",
            "best", "top", "review", "comparison", "ranking",
            "how to", "tutorial", "guide", "tutorial"
        ]

        query_lower = query.lower()
        
        for keyword in research_keywords:
            if keyword in query_lower:
                return True
        
        return False

    def _should_continue_research(
        self,
        confidence: float,
        iteration: int,
        max_iterations: int,
        reasoning_result
    ) -> bool:
        """
        Determine if research should continue to the next iteration.
        
        Research continues until:
        1. Confidence threshold is met (0.85)
        2. Maximum iterations is reached
        3. No useful evidence is added
        4. Remaining providers unlikely to improve results
        5. User selected Quick mode
        
        Args:
            confidence: Current confidence score
            iteration: Current iteration number
            max_iterations: Maximum allowed iterations
            reasoning_result: Reasoning result from ResearchReasoner
            
        Returns:
            True if research should continue, False otherwise
        """
        # Check if max iterations reached
        if iteration >= max_iterations:
            logger.info(f"Max iterations ({max_iterations}) reached")
            return False
        
        # Check if confidence threshold is met
        if confidence >= self.planner.confidence_threshold:
            logger.info(f"Confidence threshold ({self.planner.confidence_threshold}) reached")
            return False
        
        # Check if there's sufficient evidence
        total_evidence = len(reasoning_result.strong_evidence) + len(reasoning_result.weak_evidence)
        if total_evidence < self.reasoner.min_evidence_count:
            logger.info(
                f"Insufficient evidence ({total_evidence} < {self.reasoner.min_evidence_count})"
            )
            return False
        
        # Check if no useful evidence was added in this iteration
        if iteration > 1:
            # In a real implementation, we'd track evidence added in this iteration
            # For now, we'll assume there's always some new evidence
            pass
        
        # Check if remaining steps are unlikely to improve results
        if reasoning_result.recommendations:
            # If there are recommendations, consider continuing
            # In a full implementation, we'd analyze recommendations
            pass
        
        # Default: continue if conditions not met
        return True
    
    def _create_evidence_from_results(
        self,
        results: list,
        query: str
    ) -> list:
        """
        Convert search results to Evidence objects.
        
        Args:
            results: Search results
            query: Original query
            
        Returns:
            List of Evidence objects
        """
        evidence_list = []
        
        for result in results:
            # Prefer full fetched document content, fall back to the
            # search snippet, then the title, so we always have something.
            fact_text = ""
            if result.document and result.document.content:
                fact_text = result.document.content[:500]
            elif result.snippet:
                fact_text = result.snippet
            elif result.title:
                fact_text = result.title

            if not fact_text:
                # Nothing usable from this result; skip it rather than
                # creating empty evidence.
                continue

            evidence = Evidence(
                fact=fact_text,
                source=result.source,
                trust_level=result.trust_level,
                score=result.score,
                url=result.url,
                confidence=float(result.score),  # score is already 0-100
                raw_snippet=result.snippet
            )
            evidence_list.append(evidence)
        
        logger.info(f"Created {len(evidence_list)} evidence items from {len(results)} results")
        return evidence_list
    
    def get_report(self, report_id: str) -> Optional[ResearchReport]:
        """
        Get a previously created report.

        Args:
            report_id: Report ID

        Returns:
            Research report or None
        """
        # Implementation for persistent storage
        return None

    def _log_research_trace(
        self,
        query: str,
        iteration: int,
        should_continue: bool,
        reasoning_result,
        final_context,
        duration: float
    ):
        """
        Log comprehensive Research Trace block.

        Args:
            query: Original research query
            iteration: Number of iterations completed
            should_continue: Whether research would continue
            reasoning_result: Reasoning result from ResearchReasoner
            final_context: Final ResearchContext
            duration: Total execution time in seconds
        """
        logger.info(f"\n{'='*60}")
        logger.info("Research Trace")
        logger.info(f"{'='*60}\n")

        # Check if research was needed
        research_needed = (
            len(final_context.evidence) > 0 or
            final_context.confidence > 0
        )
        logger.info(f"Need Research")
        logger.info(f"{'YES' if research_needed else 'NO'}\n")

        # Reason
        logger.info(f"Reason")
        if reasoning_result.missing_information:
            logger.info(f"Missing information:")
            for info in reasoning_result.missing_information[:3]:
                logger.info(f"  - {info}")
        else:
            logger.info(f"Current information is sufficient")
        logger.info()

        # Planner
        logger.info(f"Planner")
        logger.info(f"STANDARD")
        logger.info()

        # Providers
        logger.info(f"Providers")
        if self.search_manager and self.search_manager.providers:
            for provider_name in self.search_manager.providers.keys():
                logger.info(f"  ✓ {provider_name}")
        else:
            logger.info(f"  (No providers available)")
        logger.info()

        # Iterations
        logger.info(f"Iterations")
        logger.info(f"{iteration}")
        logger.info()

        # Confidence
        logger.info(f"Confidence")
        logger.info(f"{final_context.confidence:.2f}")
        logger.info()

        # Evidence distribution
        logger.info(f"Strong Evidence")
        logger.info(f"{len(reasoning_result.strong_evidence)}")
        logger.info()

        logger.info(f"Weak Evidence")
        logger.info(f"{len(reasoning_result.weak_evidence)}")
        logger.info()

        # Conflicts
        logger.info(f"Conflicts")
        logger.info(f"{len(reasoning_result.conflicts)}")
        logger.info()

        # Stopped because
        logger.info(f"Stopped Because")
        stop_reason = []
        if reasoning_result.confidence >= self.planner.confidence_threshold:
            stop_reason.append("Confidence reached threshold")
        if iteration >= 3:  # max_iterations
            stop_reason.append("Max iterations reached")
        if not reasoning_result.missing_information:
            stop_reason.append("No additional information needed")
        if not should_continue and reasoning_result.confidence < self.planner.confidence_threshold:
            stop_reason.append("Provider exhaustion or other stop condition")

        for reason in stop_reason:
            logger.info(f"  - {reason}")
        logger.info()

        # Execution time
        logger.info(f"Execution Time")
        logger.info(f"{duration:.2f} sec")
        logger.info(f"\n{'='*60}\n")