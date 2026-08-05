"""
Desktop Goal Representation
Represents high-level user intent decomposed into planning targets.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GoalPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DesktopGoal:
    """
    Representation of a user desktop goal for the Desktop Planner.
    """

    goal: str
    category: str = "general"
    priority: GoalPriority = GoalPriority.NORMAL
    context: dict[str, Any] = field(default_factory=dict)
    explicit_capability: str | None = None
    target_window: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "category": self.category,
            "priority": self.priority.value,
            "context": self.context,
            "explicit_capability": self.explicit_capability,
            "target_window": self.target_window,
            "parameters": self.parameters,
        }
