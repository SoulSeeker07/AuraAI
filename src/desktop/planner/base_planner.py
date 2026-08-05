"""
Desktop Base Planner
Inherits from universal Core BasePlanner.
"""

from abc import abstractmethod
from typing import Any

from core.planning.base_planner import BasePlanner as CoreBasePlanner

from .desktop_plan import DesktopPlan


class BasePlanner(CoreBasePlanner):
    """
    Abstract Base Class for Desktop Planning subsystem.
    """

    def can_handle(self, goal_text: str) -> bool:
        """Default desktop planner intent evaluation."""
        return True

    @abstractmethod
    def create_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> DesktopPlan:
        """Create an execution plan for a goal."""
        pass

    @abstractmethod
    def execute_plan(self, plan: DesktopPlan) -> DesktopPlan:
        """Execute a plan."""
        pass

    @abstractmethod
    def optimize_plan(self, plan: DesktopPlan) -> DesktopPlan:
        """Optimize step ordering and parallelization in a plan."""
        pass
