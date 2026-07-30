"""
Filesystem Rules

Rules for routing filesystem-related requests.
"""

from typing import List, Dict, Any, Optional
from ..capability_types import CapabilityType, CapabilityPriority
from ..routing_result import RoutingResult


class FilesystemRules:
    """Rules for filesystem capability routing."""

    def __init__(self):
        """Initialize filesystem rules."""
        self.rules = [
            # File operations
            {
                "keywords": ["create", "new", "make"],
                "confidence": 0.80,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["delete", "remove", "trash", "recycle", "destroy", "erase"],
                "confidence": 0.95,
                "priority": CapabilityPriority.HIGH,
                "requires_permission": True,
            },
            {
                "keywords": ["move", "rename", "rename file", "rename folder", "change name"],
                "confidence": 0.90,
                "priority": CapabilityPriority.HIGH,
                "requires_permission": False,
            },
            {
                "keywords": ["copy", "duplicate", "clone"],
                "confidence": 0.85,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["compress", "archive", "zip", "unzip"],
                "confidence": 0.85,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
            {
                "keywords": ["delete all", "clear", "wipe", "format"],
                "confidence": 0.95,
                "priority": CapabilityPriority.HIGH,
                "requires_permission": True,
            },
            {
                "keywords": ["read", "view", "show", "display", "open file"],
                "confidence": 0.90,
                "priority": CapabilityPriority.MEDIUM,
                "requires_permission": False,
            },
        ]

    def route(self, text: str) -> Optional[RoutingResult]:
        """
        Route filesystem-related request.

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
                        capability=CapabilityType.FILESYSTEM,
                        confidence=rule["confidence"],
                        priority=rule["priority"],
                        requires_permission=rule["requires_permission"],
                    )

        return None
