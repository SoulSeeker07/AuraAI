"""
Vision Rules

Rules for routing vision-related requests.
"""

from ..capability_types import CapabilityPriority, CapabilityType
from ..routing_result import RoutingResult


class VisionRules:
    """Rules for vision capability routing."""

    def __init__(self):
        """Initialize vision rules."""
        self.rules = [
            {
                "keywords": ["analyze", "describe", "explain", "what is"],
                "confidence": 0.90,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["read", "extract text", "ocr", "recognize"],
                "confidence": 0.85,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["what is in", "what do you see", "identify"],
                "confidence": 0.85,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
        ]

    def route(self, text: str) -> RoutingResult | None:
        """
        Route vision-related request.

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
                        capability=CapabilityType.VISION,
                        confidence=rule["confidence"],
                        priority=rule["priority"],
                        requires_permission=rule["requires_permission"],
                    )

        return None
