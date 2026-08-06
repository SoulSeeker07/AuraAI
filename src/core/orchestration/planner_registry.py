"""
Planner Registry
Location: src/core/orchestration/planner_registry.py

Single centralized registry for BasePlanner role implementations (Desktop, Research, Coding, Browser).
"""

import logging
from typing import Any, Optional

from ..planning.base_planner import BasePlanner
from .task_decomposer import PlannerRole

logger = logging.getLogger(__name__)


class DefaultRolePlanner(BasePlanner):
    """Fallback / default role planner wrapper for domain roles."""

    def __init__(self, role_name: str, capability: str):
        self.role_name = role_name
        self.capability = capability

    def can_handle(self, goal_text: str) -> bool:
        return True

    def create_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "role": self.role_name,
            "capability": capability or self.capability,
            "goal": goal_text,
            "parameters": parameters or {},
        }

    def optimize_plan(self, plan: Any) -> Any:
        return plan

    def execute_plan(self, plan: Any) -> Any:
        return plan

    def explain_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"description": f"Role planner {self.role_name} execution plan"}


class PlannerRegistry:
    """
    Centralized registry for BasePlanner implementations.
    """

    _instance: Optional["PlannerRegistry"] = None

    def __init__(self):
        self._planners: dict[str, BasePlanner] = {}
        self._register_default_role_planners()

    @classmethod
    def get_instance(cls) -> "PlannerRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def _register_default_role_planners(self) -> None:
        """Register canonical role planners."""
        self.register(
            PlannerRole.DESKTOP.value, DefaultRolePlanner("desktop", "desktop")
        )
        self.register(
            PlannerRole.RESEARCH.value, DefaultRolePlanner("research", "research")
        )
        self.register(PlannerRole.CODING.value, DefaultRolePlanner("coding", "coding"))

        try:
            from browser.planner.browser_goal_planner import BrowserGoalPlanner

            self.register(PlannerRole.BROWSER.value, BrowserGoalPlanner())
        except Exception as e:
            logger.warning(
                f"Failed to load BrowserGoalPlanner, using default fallback: {e}"
            )
            self.register(
                PlannerRole.BROWSER.value, DefaultRolePlanner("browser", "browser")
            )

    def register(self, name: str, planner: BasePlanner) -> None:
        """Register a BasePlanner implementation."""
        key = name.lower()
        self._planners[key] = planner
        logger.info(f"Registered role planner '{key}'")

    def get_planner(self, name: str) -> BasePlanner | None:
        """Retrieve a registered BasePlanner by role name."""
        return self._planners.get(name.lower())

    def list_planners(self) -> list[str]:
        """List all registered planner role names."""
        return list(self._planners.keys())

    def get_engineering_supervisor(self):
        """Retrieve or instantiate the SoftwareEngineeringSupervisor."""
        try:
            from .software_engineering_supervisor import SoftwareEngineeringSupervisor

            return SoftwareEngineeringSupervisor()
        except Exception as e:
            logger.warning(f"Could not load SoftwareEngineeringSupervisor: {e}")
            return None

    def find_planners_for_goal(self, goal_text: str) -> list[tuple[str, BasePlanner]]:
        """Find all registered planners that can handle a goal."""
        return [
            (name, planner)
            for name, planner in self._planners.items()
            if planner.can_handle(goal_text)
        ]
