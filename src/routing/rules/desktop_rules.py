"""
Desktop Rules

Rules for routing desktop-related requests.
"""

from typing import List, Dict, Any
from ..capability_types import CapabilityType, CapabilityPriority
from ..routing_result import RoutingResult


class DesktopRules:
    """Rules for desktop capability routing."""

    def __init__(self):
        """Initialize desktop rules."""
        self.rules = [
            # Window management
            {
                "keywords": ["minimize", "minimise", "maximize", "maximise", "maximize all", "maximise all"],
                "confidence": 0.95,
                "priority": CapabilityPriority.HIGH,
                "requires_permission": False,
            },
            {
                "keywords": ["close", "close all", "close window"],
                "confidence": 0.90,
                "priority": CapabilityPriority.HIGH,
                "requires_permission": False,
            },
            {
                "keywords": ["hide", "hide all"],
                "confidence": 0.85,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            # Application management
            {
                "keywords": ["open", "launch", "start", "run"],
                "confidence": 0.85,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["quit", "force quit", "terminate", "kill"],
                "confidence": 0.90,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": True,
            },
            {
                "keywords": ["close application"],
                "confidence": 0.85,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            # System operations
            {
                "keywords": ["shutdown", "power off", "reboot", "restart"],
                "confidence": 0.95,
                "priority": CapabilityPriority.HIGH,
                "requires_permission": True,
            },
            {
                "keywords": ["sleep", "hibernate", "lock", "log out"],
                "confidence": 0.90,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
        ]

    def route(self, text: str) -> Optional[RoutingResult]:
        """
        Route desktop-related request.

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
                        capability=CapabilityType.DESKTOP,
                        confidence=rule["confidence"],
                        priority=rule["priority"],
                        requires_permission=rule["requires_permission"],
                    )

        return None
