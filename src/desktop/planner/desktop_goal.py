"""
Desktop Goal Representation
Represents high-level user intent decomposed into planning targets.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


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
    context: Dict[str, Any] = field(default_factory=dict)
    explicit_capability: Optional[str] = None
    target_window: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "category": self.category,
            "priority": self.priority.value,
            "context": self.context,
            "explicit_capability": self.explicit_capability,
            "target_window": self.target_window,
            "parameters": self.parameters,
        }
