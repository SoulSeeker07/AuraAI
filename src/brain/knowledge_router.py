from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RoutingConfig:
    """Configuration for routing queries to appropriate sources."""

    # Live information sources
    news_sources = [
        "news.google.com",
        "bbc.com",
        "reuters.com",
        "apnews.com",
    ]

    # Programming sources
    programming_sources = [
        "github.com",
        "stackoverflow.com",
        "stackoverflow.org",
        "python.org",
        "developer.mozilla.org",
        "learn.microsoft.com",
    ]

    # Networking sources
    networking_sources = [
        "cisco.com",
        "microsoft.com",
        "juniper.net",
        "paloaltonetworks.com",
        "fortinet.com",
    ]

    # Medical sources
    medical_sources = [
        "who.int",
        "mayoclinic.org",
        "cdc.gov",
        "nih.gov",
        "healthline.com",
    ]

    # Research/educational sources
    research_sources = [
        "wikipedia.org",
        "sciencedirect.com",
        "springer.com",
        "arxiv.org",
        "ncbi.nlm.nih.gov",
    ]


class KnowledgeRouter:
    """
    Routes user queries to the most appropriate information sources.
    This is Aura's traffic controller, deciding which domains to search.
    """

    ROUTING_RULES = {
        "LIVE_INFORMATION": {
            "source_type": "news",
            "priority": ["news.google.com", "bbc.com", "reuters.com"],
            "exclude": [],
        },
        "KNOWLEDGE_REQUEST": {
            "source_type": "general",
            "priority": [
                "wikipedia.org",
                "developer.mozilla.org",
                "learn.microsoft.com",
            ],
            "exclude": [],
        },
        "PROGRAMMING": {
            "source_type": "programming",
            "priority": ["github.com", "stackoverflow.com", "python.org"],
            "exclude": [],
        },
        "NETWORKING": {
            "source_type": "networking",
            "priority": ["cisco.com", "microsoft.com", "juniper.net"],
            "exclude": [],
        },
        "MEDICAL": {
            "source_type": "medical",
            "priority": ["who.int", "mayoclinic.org", "cdc.gov"],
            "exclude": [],
        },
        "RESEARCH": {
            "source_type": "research",
            "priority": ["wikipedia.org", "arxiv.org", "ncbi.nlm.nih.gov"],
            "exclude": [],
        },
        "SPECIALIZED_ASK": {
            "source_type": "general",
            "priority": ["google.com"],
            "exclude": [],
        },
        "TIME_DATE": {
            "source_type": "local",
            "priority": [],
            "exclude": [],
        },
        "SETTINGS": {
            "source_type": "local",
            "priority": [],
            "exclude": [],
        },
        "VISION": {
            "source_type": "local",
            "priority": [],
            "exclude": [],
        },
        "TASK_EXECUTION": {
            "source_type": "local",
            "priority": [],
            "exclude": [],
        },
        "GENERAL_CHAT": {
            "source_type": "general",
            "priority": ["wikipedia.org", "google.com"],
            "exclude": [],
        },
        "REMEMBER_FACT": {
            "source_type": "local",
            "priority": [],
            "exclude": [],
        },
    }

    def __init__(self, config: RoutingConfig | None = None):
        self.config = config or RoutingConfig()
        self.routing_rules = self.ROUTING_RULES.copy()

    def get_routing_config(
        self, intent: str, specialized_sources: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Get routing configuration for a given intent.

        Args:
            intent: The intent category to route
            specialized_sources: User-specified special sources to prioritize

        Returns:
            Dict with source_type, priority, and exclude lists
        """
        rules = self.routing_rules.get(intent, self.routing_rules["GENERAL_CHAT"])

        # If user provided specialized sources, merge them
        if specialized_sources:
            priority = rules["priority"] + specialized_sources
        else:
            priority = rules["priority"]

        return {
            "source_type": rules["source_type"],
            "priority": priority,
            "exclude": rules["exclude"],
            "default_sources": self._get_default_sources(rules["source_type"]),
        }

    def _get_default_sources(self, source_type: str) -> list[str]:
        """Get default sources for a source type."""
        if source_type == "news":
            return self.config.news_sources
        elif source_type == "programming":
            return self.config.programming_sources
        elif source_type == "networking":
            return self.config.networking_sources
        elif source_type == "medical":
            return self.config.medical_sources
        elif source_type == "research":
            return self.config.research_sources
        else:
            return ["google.com"]

    def determine_source_strategy(self, intent: str, needs_deep_research: bool) -> str:
        """
        Determine the search strategy for an intent.

        Returns:
            "quick" for simple searches
            "deep" for multi-source research
            "news" for live information
            "specialized" for domain-specific queries
        """
        if intent == "LIVE_INFORMATION":
            return "news"
        elif needs_deep_research:
            return "deep"
        elif intent in ["PROGRAMMING", "NETWORKING", "MEDICAL"]:
            return "specialized"
        else:
            return "quick"

    def get_search_limit(self, intent: str) -> int:
        """Get appropriate search limit for an intent."""
        if intent == "LIVE_INFORMATION":
            return 10  # More sources for news
        elif intent == "RESEARCH":
            return 15  # Deep research needs many sources
        elif intent in ["PROGRAMMING", "NETWORKING", "MEDICAL"]:
            return 10  # Specialized queries benefit from more results
        else:
            return 5  # Default
