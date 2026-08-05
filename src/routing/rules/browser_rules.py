"""
Browser Rules

Rules for routing browser-related requests.
"""

from ..capability_types import CapabilityPriority, CapabilityType
from ..routing_result import RoutingResult


class BrowserRules:
    """Rules for browser capability routing."""

    def __init__(self):
        """Initialize browser rules."""
        self.rules = [
            {
                "keywords": ["search", "find", "look for", "browse"],
                "confidence": 0.90,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["open", "visit", "navigate to", "go to"],
                "confidence": 0.95,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["close", "quit"],
                "confidence": 0.85,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["new tab", "open new tab"],
                "confidence": 0.80,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
        ]

    def route(self, text: str) -> RoutingResult | None:
        """
        Route browser-related request.

        Args:
            text: User request text

        Returns:
            RoutingResult if rule matches, None otherwise
        """
        text_lower = text.lower().strip()

        for rule in self.rules:
            for keyword in rule["keywords"]:
                if keyword in text_lower:
                    return RoutingResult(
                        capability=CapabilityType.BROWSER,
                        confidence=rule["confidence"],
                        priority=rule["priority"],
                        requires_permission=rule["requires_permission"],
                    )

        return None
