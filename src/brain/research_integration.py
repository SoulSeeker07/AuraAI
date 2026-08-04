"""
Research Integration for Aura Brain

Integrates the Research Engine with Aura's Brain to provide
evidence-based answers to queries that require live data.
"""

import logging
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass

from research import ResearchEngine, SearchQuery, SearchMode

logger = logging.getLogger(__name__)


# Keywords that trigger research (higher priority if query contains multiple)
RESEARCH_KEYWORDS: Set[str] = {
    # Temporal queries
    "latest", "recent", "current", "now", "today", "tomorrow", "yesterday",
    # Version and release queries
    "version", "release", "beta", "stable", "release", "upcoming", "planned",
    # Technical documentation queries
    "RFC", "specification", "spec", "guide", "documentation", "tutorial", "how to",
    # Problem and troubleshooting queries
    "bug", "bugs", "issue", "issues", "problems", "error", "errors", "fix", "fixes",
    # Business and market queries
    "market", "price", "stock", "earnings", "result", "results", "quarterly",
    # Product-specific queries
    "guide", "install", "configuration", "setup",
    # High-confidence knowledge queries (require verification)
    "gpt", "claude", "gemini", "llama", "ai", "model", "updated", "released",
}

# Product names that trigger research
PRODUCT_NAMES: Set[str] = {
    "windows", "macos", "linux", "python", "java", "javascript", "typescript",
    "react", "vue", "angular", "nodejs", "docker", "kubernetes", "aws", "azure",
    "google", "microsoft", "openai", "anthropic", "meta", "facebook", "linkedin",
    "bloomberg", "bel", "goldman", "jpmorgan", "morgan stanley", "visa",
}


@dataclass
class ResearchDecision:
    """Decision about whether research is needed."""
    needs_research: bool
    reason: str
    research_mode: SearchMode
    confidence: float  # 0-1, higher means more confident research is needed


class ResearchIntegration:
    """
    Integrates research capabilities with Aura's Brain.

    Automatically decides when research is needed based on query analysis.
    """

    def __init__(self, research_engine: ResearchEngine):
        """
        Initialize research integration.

        Args:
            research_engine: Research engine instance
        """
        self.research_engine = research_engine
        self.research_enabled = research_engine.config.enabled

    def is_research_needed(self, query: str) -> bool:
        """
        Determine if research is needed for a query.

        Args:
            query: User query

        Returns:
            True if research is needed
        """
        decision = self._analyze_research_needs(query)
        return decision.needs_research

    def _analyze_research_needs(self, query: str) -> ResearchDecision:
        """
        Analyze a query to determine if research is needed.

        Uses keyword detection and confidence scoring.

        Args:
            query: User query

        Returns:
            ResearchDecision with reasoning
        """
        if not self.research_enabled:
            return ResearchDecision(False, "Research engine disabled", SearchMode.STANDARD, 0.0)

        query_lower = query.lower()
        score = 0.0
        reasons = []
        detected_keywords = set()
        detected_products = set()

        # Check for temporal keywords
        temporal_keywords = {"latest", "recent", "current", "now", "today", "tomorrow", "yesterday"}
        if temporal_keywords & query_lower.split():
            score += 1.0
            reasons.append("temporal keyword detected")
            detected_keywords.update(temporal_keywords & query_lower.split())

        # Check for version/release keywords
        version_keywords = {"version", "release", "beta", "stable", "upcoming", "planned"}
        if version_keywords & query_lower.split():
            score += 1.0
            reasons.append("version/release query")
            detected_keywords.update(version_keywords & query_lower.split())

        # Check for technical documentation keywords
        doc_keywords = {"RFC", "spec", "guide", "documentation", "tutorial", "how to"}
        if doc_keywords & query_lower.split():
            score += 1.0
            reasons.append("documentation query")
            detected_keywords.update(doc_keywords & query_lower.split())

        # Check for troubleshooting keywords
        troubleshooting_keywords = {"bug", "issue", "problems", "error", "fix"}
        if troubleshooting_keywords & query_lower.split():
            score += 0.8
            reasons.append("troubleshooting query")
            detected_keywords.update(troubleshooting_keywords & query_lower.split())

        # Check for business queries
        business_keywords = {"market", "price", "stock", "earnings", "result", "quarterly"}
        if business_keywords & query_lower.split():
            score += 1.0
            reasons.append("business/market query")
            detected_keywords.update(business_keywords & query_lower.split())

        # Check for product names
        for product in PRODUCT_NAMES:
            if product in query_lower:
                detected_products.add(product)

        # Check for AI/model updates
        ai_keywords = {"gpt", "claude", "gemini", "llama", "ai", "updated", "released"}
        if ai_keywords & query_lower.split():
            score += 1.0
            reasons.append("AI/model update query")
            detected_keywords.update(ai_keywords & query_lower.split())

        # High-confidence research triggers (very strong indicators)
        high_confidence_triggers = {
            "current", "latest", "now", "release", "version", "updated",
            "earnings", "price", "stock", "RFC", "spec", "guide", "tutorial"
        }
        if high_confidence_triggers & query_lower.split():
            score = min(score + 0.5, 2.0)

        # Determine if research is definitely needed
        if score >= 1.5:
            needs_research = True
            research_mode = self._determine_research_mode(reasons, detected_keywords, detected_products)
            return ResearchDecision(True, f"Research needed: {', '.join(reasons)}", research_mode, 0.8 + score * 0.1)

        if score >= 1.0:
            # Check for exact phrase matches in common knowledge
            common_knowledge_patterns = [
                "what is", "explain", "definition", "overview", "introduction",
                "basic", "fundamental", "principles", "concepts"
            ]
            has_common_knowledge = any(pattern in query_lower for pattern in common_knowledge_patterns)

            if not has_common_knowledge:
                needs_research = True
                research_mode = self._determine_research_mode(reasons, detected_keywords, detected_products)
                return ResearchDecision(True, f"Research needed: {', '.join(reasons)}", research_mode, 0.7 + score * 0.1)

        # Check for products that require research
        if detected_products:
            needs_research = True
            research_mode = SearchMode.STANDARD
            return ResearchDecision(
                True,
                f"Research needed: {', '.join(detected_products)} mentioned",
                research_mode,
                0.6
            )

        # No strong indicators - no research needed
        return ResearchDecision(False, "Query appears to be common knowledge or specific question", SearchMode.STANDARD, 0.0)

    def _determine_research_mode(self, reasons: list, detected_keywords: set, detected_products: set) -> SearchMode:
        """
        Determine appropriate research mode based on query characteristics.

        Args:
            reasons: List of reasons research might be needed
            detected_keywords: Set of detected keywords
            detected_products: Set of detected product names

        Returns:
            SearchMode (QUICK, STANDARD, or DEEP)
        """
        # Check for deep research triggers
        deep_keywords = {
            "comprehensive", "best", "complete", "thorough", "detailed",
            "analysis", "deep dive", "in-depth", "comparison"
        }
        if deep_keywords & detected_keywords:
            return SearchMode.DEEP

        # Check for quick research triggers
        quick_keywords = {
            "latest", "current", "now", "today", "quick", "recent"
        }
        if quick_keywords & detected_keywords:
            return SearchMode.QUICK

        # Check for business queries
        business_keywords = {
            "price", "stock", "earnings", "result", "market"
        }
        if business_keywords & detected_keywords:
            return SearchMode.QUICK

        # Default to standard for technical documentation
        if "RFC" in detected_keywords or "spec" in detected_keywords:
            return SearchMode.STANDARD

        return SearchMode.STANDARD

    def perform_research(self, query: str, mode: SearchMode = SearchMode.STANDARD) -> Optional[Dict[str, Any]]:
        """
        Perform research and return results.

        Args:
            query: Research query
            mode: Search mode (quick, standard, deep)

        Returns:
            Research results dictionary or None if failed
        """
        logger.info(f"ResearchIntegration.perform_research() called with query='{query}', mode={mode}")
        try:
            report = self.research_engine.research(query, mode=mode)
            logger.info(f"ResearchEngine.research() returned: results_count={len(report.results)}, citations_count={len(report.citations)}")

            if not report.results:
                logger.warning(f"ResearchEngine returned empty results for query: {query}")

            return {
                "query": report.query,
                "has_results": len(report.results) > 0,
                "confidence_score": report.get_confidence_score(),
                "summary": report.summary,
                "citations": [
                    {
                        "url": c.url,
                        "title": c.title,
                        "score": c.score,
                        "trust_level": c.trust_level.value
                    }
                    for c in report.citations
                ],
                "primary_sources": report.primary_sources,
                "conflicts": report.conflicts,
                "duration": report.duration
            }

        except Exception as e:
            logger.error(f"Research failed: {e}", exc_info=True)
            return None

    def enhance_response_with_research(
        self,
        query: str,
        user_message: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Enhance a response with research findings.

        This method checks if research is needed, performs it, and
        returns a dict with the research findings and a flag indicating
        whether research was used.

        Args:
            query: Original query
            user_message: Full user message
            max_results: Maximum results to include

        Returns:
            Dict with research_used flag, enhanced_message, and research details
        """
        # Analyze research needs using ResearchDecision system
        research_decision = self._analyze_research_needs(user_message)

        # Log research decision
        self.logger.info(f"Research Decision: {research_decision.reason} (confidence: {research_decision.confidence:.2f}, mode: {research_decision.mode.name})")

        # If research is not needed
        if not research_decision.need_research:
            return {
                "research_used": False,
                "message": research_decision.reason,
                "confidence": research_decision.confidence
            }

        # Perform research with determined mode
        research_results = self.perform_research(user_message, mode=research_decision.mode)

        if not research_results or not research_results.get("has_results"):
            return {
                "research_used": False,
                "message": research_decision.reason + " - but research returned no results",
                "confidence": research_decision.confidence
            }

        # Build research-enhanced message with confidence
        enhanced_message = self._build_enhanced_message(
            query=user_message,
            research=research_results,
            confidence=research_decision.confidence
        )

        return {
            "research_used": True,
            "enhanced_message": enhanced_message,
            "research_results": research_results,
            "reason": research_decision.reason,
            "confidence": research_decision.confidence
        }

    def _build_enhanced_message(self, query: str, research: Dict[str, Any], confidence: float = 0.0) -> str:
        """
        Build an enhanced message with research findings.

        Args:
            query: Original query
            research: Research results
            confidence: Research confidence score (0-1)

        Returns:
            Enhanced message with research
        """
        # Start with standard response
        message = f"I've researched your question about '{query}':\n\n"

        # Add summary if available
        if research.get("summary"):
            message += f"**Summary:** {research['summary']}\n\n"

        # Add key sources
        if research.get("primary_sources"):
            message += f"**Key Sources:**\n"
            for source in research["primary_sources"][:3]:
                message += f"- {source}\n"
            message += "\n"

        # Add confidence score
        message += f"**Confidence Score:** {confidence * 100:.1f}/100\n\n"

        # Add citation note
        if research.get("citations"):
            message += f"*Based on {len(research['citations'])} sources*\n"

        return message

    def get_research_stats(self) -> Dict[str, Any]:
        """
        Get research engine statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "research_engine_initialized": self.research_engine.config.enabled,
            "cache_stats": self.research_engine.cache_manager.get_stats()
        }
