"""
Planner Registry & Role-Based Planners (Milestone 16 - Phase 2)

Defines role-based domain planners (Desktop, Research, Coding, Browser)
and the central PlannerRegistry for matching decomposed subtasks to planners.
"""

from abc import ABC, abstractmethod
import logging
from typing import Any

from .task_decomposer import PlannerRole, SubTask

logger = logging.getLogger(__name__)


class BaseRolePlanner(ABC):
    """Abstract base class for all role-based domain planners."""

    def __init__(self, role: PlannerRole, name: str):
        self.role = role
        self.name = name

    @abstractmethod
    def plan(self, subtask: SubTask, context: dict[str, Any]) -> dict[str, Any]:
        """
        Formulate an execution plan for a given subtask.

        Returns a dictionary containing required capability, intent, and execution parameters.
        """
        pass


class DesktopPlanner(BaseRolePlanner):
    """Planner responsible for local OS desktop interactions and app orchestration."""

    def __init__(self):
        super().__init__(role=PlannerRole.DESKTOP, name="Desktop Planner")

    def plan(self, subtask: SubTask, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "capability": "desktop",
            "action": "launch_or_focus",
            "target": subtask.description,
            "parameters": subtask.parameters,
        }


class ResearchPlanner(BaseRolePlanner):
    """Planner responsible for information gathering, search, and RAG synthesis."""

    def __init__(self):
        super().__init__(role=PlannerRole.RESEARCH, name="Research Planner")

    def plan(self, subtask: SubTask, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "capability": "research",
            "action": "query_and_summarize",
            "query": subtask.description,
            "parameters": subtask.parameters,
        }


class CodingPlanner(BaseRolePlanner):
    """Planner responsible for software development, code generation, and refactoring."""

    def __init__(self):
        super().__init__(role=PlannerRole.CODING, name="Coding Planner")

    def plan(self, subtask: SubTask, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "capability": "coding",
            "action": "execute_code_changes",
            "task": subtask.description,
            "context": context,
            "parameters": subtask.parameters,
        }


class BrowserPlanner(BaseRolePlanner):
    """Planner responsible for web browsing and web page interaction."""

    def __init__(self):
        super().__init__(role=PlannerRole.BROWSER, name="Browser Planner")

    def plan(self, subtask: SubTask, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "capability": "browser",
            "action": "navigate_and_interact",
            "target": subtask.description,
            "parameters": subtask.parameters,
        }


class PlannerRegistry:
    """Central registry holding role-based planners."""

    def __init__(self):
        self._planners: dict[PlannerRole, BaseRolePlanner] = {}
        self._register_default_planners()

    def _register_default_planners(self) -> None:
        self.register(DesktopPlanner())
        self.register(ResearchPlanner())
        self.register(CodingPlanner())
        self.register(BrowserPlanner())

    def register(self, planner: BaseRolePlanner) -> None:
        """Register a role planner."""
        self._planners[planner.role] = planner
        logger.info(f"Registered role planner: {planner.name} [{planner.role.value}]")

    def get_planner(self, role: PlannerRole) -> BaseRolePlanner:
        """Get planner by role."""
        if role not in self._planners:
            raise KeyError(f"No planner registered for role: {role}")
        return self._planners[role]
