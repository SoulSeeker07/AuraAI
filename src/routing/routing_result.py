"""
Routing Result

Structured result of a routing decision.

The router doesn't need to understand the user's request in detail.
Its job is to choose the best capability to handle the request.
"""

from dataclasses import dataclass, field
from typing import Any

from .capability_types import CapabilityPriority, CapabilityType


@dataclass
class RoutingResult:
    """
    Result of a routing decision.

    This object contains rich information about how a request should be handled,
    including which capability is best suited, confidence levels, and any
    required permissions or follow-up actions.
    """

    capability: CapabilityType
    confidence: float
    requires_ai: bool = False
    requires_permission: bool = False
    permission_level: str = "none"
    estimated_steps: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    priority: CapabilityPriority = CapabilityPriority.MEDIUM
    risk_level: str = "low"
    follow_up_actions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RoutingResult(capability={self.capability.value}, "
            f"confidence={self.confidence:.2f}, "
            f"priority={self.priority.value}, "
            f"risk_level={self.risk_level})"
        )

    def add_step(self, step: str) -> None:
        """Add a step to the execution plan."""
        if step not in self.estimated_steps:
            self.estimated_steps.append(step)

    def add_plugin(self, plugin_name: str) -> None:
        """Add a plugin to the routing result."""
        if plugin_name not in self.plugins:
            self.plugins.append(plugin_name)

    def set_permission_required(self, level: str = "confirmation") -> None:
        """Set that permission is required."""
        self.requires_permission = True
        self.permission_level = level
        self.risk_level = level  # Use permission level as risk level

    def needs_confirmation(self) -> bool:
        """Check if user confirmation is required."""
        return self.permission_level in ["confirmation", "high", "critical"]

    def needs_confirmation_from_user(self) -> bool:
        """Check if explicit user confirmation is needed."""
        return self.permission_level in ["confirmation", "high", "critical"]

    def is_safe(self) -> bool:
        """Check if the routing is safe without confirmation."""
        return self.permission_level == "none" or self.permission_level == "low"

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "capability": self.capability.value,
            "confidence": self.confidence,
            "requires_ai": self.requires_ai,
            "requires_permission": self.requires_permission,
            "permission_level": self.permission_level,
            "estimated_steps": self.estimated_steps,
            "plugins": self.plugins,
            "priority": self.priority.value,
            "risk_level": self.risk_level,
            "follow_up_actions": self.follow_up_actions,
            "metadata": self.metadata,
        }
