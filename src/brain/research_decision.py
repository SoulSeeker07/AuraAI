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
        # Deep knowledge / factual question patterns
        "explain",
        "how does",
        "how do",
        "how to",
        "how can",
        "how it works",
        "how tall",
        "how many",
        "how much",
        "how long",
        "how far",
        "how old",
        "how fast",
        "how big",
        "how deep",
        "how high",
        "how heavy",
        "how often",
        "how is",
        "how was",
        "how were",
        "how will",
        "how would",
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

    # Conversational greeting phrases that should never trigger research
    CONVERSATIONAL_GREETINGS = {
        "hello",
        "hi",
        "hey",
        "how are you",
        "how are you doing",
        "how do you do",
        "how's it going",
        "how is it going",
        "how have you been",
        "how is your day",
        "how's your day",
        "how are things",
        "good morning",
        "good afternoon",
        "good evening",
        "what's up",
        "whats up",
        "nice to meet you",
    }

    def analyze(self, query: str) -> tuple[bool, str, SearchMode]:
        """
        Analyze a query and determine if research is needed.

        Args:
            query: User input query

        Returns:
            Tuple of (needs_research, reason, search_mode)
        """
        import re
        normalized = query.lower().strip()
        clean_query = re.sub(r"[^a-z0-9\s']", " ", normalized)
        clean_query = " ".join(clean_query.split())

        logger.info(f"[ResearchDecision] Analyzing query: {query}")
        logger.info(f"[ResearchDecision] Normalized: {normalized}")

        # Check for conversational greetings first
        greeting_phrases = (
            "hello",
            "hi",
            "hey",
            "how are you",
            "how are you doing",
            "how do you do",
            "how's it going",
            "how is it going",
            "hows it going",
            "how have you been",
            "how is your day",
            "how's your day",
            "hows your day",
            "how are things",
            "good morning",
            "good afternoon",
            "good evening",
            "what's up",
            "whats up",
        )
        if clean_query in self.CONVERSATIONAL_GREETINGS or any(
            clean_query.startswith(g) for g in ("hello", "hi ", "hey ", "how are you", "how's it going", "how is it going", "good morning", "good evening")
        ) or any(
            g in clean_query for g in ("how are you", "how is it going", "hows it going", "how are things", "how have you been", "how is your day", "hows your day")
        ):
            if not any(k in clean_query for k in ("stock", "price", "market", "weather", "news", "versus", "compare", "tall", "many", "much", "old", "far", "fast", "deep")):
                logger.info("[ResearchDecision] NO RESEARCH - Conversational greeting")
                return False, "Conversational greeting", SearchMode.STANDARD

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
