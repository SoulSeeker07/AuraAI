"""
Planner Registry
Dynamic registry for registering and resolving BasePlanner subsystem implementations.
"""

import logging
from typing import Optional

from ..planning.base_planner import BasePlanner

logger = logging.getLogger(__name__)


class PlannerRegistry:
    """
    Centralized registry for BasePlanner implementations (Desktop, Research, Coding, Browser).
    """

    _instance: Optional["PlannerRegistry"] = None

    def __init__(self):
        self._planners: dict[str, BasePlanner] = {}

    @classmethod
    def get_instance(cls) -> "PlannerRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def register(self, name: str, planner: BasePlanner) -> None:
        """Register a BasePlanner implementation."""
        self._planners[name] = planner
        logger.info(f"Registered planner '{name}'")

    def get_planner(self, name: str) -> BasePlanner | None:
        """Get planner by name."""
        return self._planners.get(name)

    def find_planners_for_goal(self, goal_text: str) -> list[tuple[str, BasePlanner]]:
        """Find all registered planners that can handle a goal."""
        return [
            (name, planner)
            for name, planner in self._planners.items()
            if planner.can_handle(goal_text)
        ]

    def list_planners(self) -> list[str]:
        """List names of all registered planners."""
        return list(self._planners.keys())
