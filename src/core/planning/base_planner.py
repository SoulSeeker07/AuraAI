"""
Base Planner API
Universal abstract contract for all Aura AI subsystem planners (Desktop, Research, Coding, Browser).
"""

from abc import ABC, abstractmethod
from typing import Any


class BasePlanner(ABC):
    """
    Abstract contract implemented by all Aura planners.
    """

    @abstractmethod
    def can_handle(self, goal_text: str) -> bool:
        """Evaluate whether this planner can handle the specified goal."""
        pass

    @abstractmethod
    def create_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> Any:
        """Create an execution plan for a goal."""
        pass

    @abstractmethod
    def optimize_plan(self, plan: Any) -> Any:
        """Optimize step ordering or execution strategy in a plan."""
        pass

    @abstractmethod
    def execute_plan(self, plan: Any) -> Any:
        """Execute all steps in a plan."""
        pass

    @abstractmethod
    def explain_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a human-readable dry-run preview of plan execution."""
        pass
