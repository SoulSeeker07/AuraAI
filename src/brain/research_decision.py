"""
ResearchDecision module.

Determines whether a query requires research and what type of research is needed.

Flow:
    User → IntentRouter → ResearchDecision → Needs Research? → ResearchPlanner → Providers → Evidence → Reasoner → Confidence → Groq
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SearchMode(Enum):
    """Search mode enumeration."""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class ResearchDecision:
    """
    Decides whether a query needs research and what mode to use.

    This replaces keyword-based routing in IntentRouter with semantic reasoning.
    """

    # Keywords that indicate research is needed
    RESEARCH_KEYWORDS = {
        # Financial research
        "stock",
        "stocks",
        "invest",
        "investment",
        "investing",
        "bel",
        "kaynes",
        "market",
        "performance",
        "earnings",
        "dividend",
        "profit",
        "loss",
        "revenue",
        "gdp",
        "inflation",
        "interest rate",
        "bond",
        "forex",
        # Product/feature comparison
        "compare",
        "versus",
        "vs",
        "difference between",
        "which is better",
        "pros and cons",
        "advantages and disadvantages",
        "comparison",
        "better than",
        "worse than",
        "difference",
        # Research and analysis
        "research",
        "analyze",
        "investigate",
        "study",
        # Official information
        "latest",
        "current",
        "today",
        "now",
        "news",
        "release",
        "version",
        "roadmap",
        "road map",
        "upgrade",
        "new feature",
        # Deep knowledge
        "explain",
        "how",
        "how does",
        "overview",
        "summary",
        "analysis",
        # Historical/Time-based
        "history",
        "past",
        "before",
        "future",
        "forecast",
        "prediction",
        "years ago",
        "since",
        "until",
        # Company/product specific
        "company",
        "product",
        "service",
        "platform",
        "technology",
        "technology",
        "ai",
        "machine learning",
        "deep learning",
    }

    # Query types that always require research
    ALWAYS_RESEARCH_INTENTS = {
        "web_search",
        "deep_research",
        "compare",
        "analyze",
        "forecast",
    }

    def analyze(self, query: str) -> tuple[bool, str, SearchMode]:
        """
        Analyze a query and determine if research is needed.

        Args:
            query: User input query

        Returns:
            Tuple of (needs_research, reason, search_mode)
        """
        normalized = query.lower()

        logger.info(f"[ResearchDecision] Analyzing query: {query}")
        logger.info(f"[ResearchDecision] Normalized: {normalized}")

        # Check for always-research intents
        if normalized in self.ALWAYS_RESEARCH_INTENTS:
            reason = f"Intent is '{normalized}'"
            search_mode = (
                SearchMode.DEEP
                if normalized in ["deep_research", "analyze"]
                else SearchMode.STANDARD
            )
            logger.info(
                f"[ResearchDecision] → NEEDS RESEARCH - {reason}, mode={search_mode.value}"
            )
            return True, reason, search_mode

        # Check for research keywords
        matched_keywords = []
        for keyword in self.RESEARCH_KEYWORDS:
            if keyword in normalized:
                matched_keywords.append(keyword)

        if matched_keywords:
            # Determine search mode based on keyword strength
            search_mode = self._determine_search_mode(matched_keywords)
            reason = f"Contains research keywords: {', '.join(matched_keywords[:5])}"
            logger.info(
                f"[ResearchDecision] NEEDS RESEARCH - {reason}, mode={search_mode.value}"
            )
            return True, reason, search_mode

        # Default: no research needed
        logger.info("[ResearchDecision] NO RESEARCH - No research keywords found")
        return False, "No research keywords found", SearchMode.STANDARD

    def _determine_search_mode(self, keywords: list[str]) -> SearchMode:
        """
        Determine search mode based on matched keywords.

        Args:
            keywords: List of matched keywords

        Returns:
            SearchMode (QUICK, STANDARD, or DEEP)
        """
        # Deep research keywords
        deep_keywords = {
            "forecast",
            "prediction",
            "compare",
            "versus",
            "vs",
            "pros and cons",
            "advantages and disadvantages",
            "investment",
            "market",
            "earnings",
            "dividend",
        }

        # Quick research keywords
        quick_keywords = {
            "latest",
            "current",
            "today",
            "now",
            "news",
            "release",
            "version",
            "price",
            "score",
        }

        # Check for deep keywords first
        if any(kw in deep_keywords for kw in keywords):
            return SearchMode.DEEP

        # Check for quick keywords
        if any(kw in quick_keywords for kw in keywords):
            return SearchMode.QUICK

        # Default to standard
        return SearchMode.STANDARD
