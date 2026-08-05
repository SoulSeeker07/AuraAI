"""
Supervisor Agent (Cognitive Supervisor)
Location: src/core/orchestration/supervisor_agent.py

Supervises multi-agent delegation across role planners without performing low-level execution directly.
Evaluates:
- Need Research? -> Delegate to Research Planner
- Need Desktop? -> Delegate to Desktop Planner
- Need Coding? -> Delegate to Coding Planner
- Need Browser? -> Delegate to Browser Planner
"""

import logging
from typing import Any

from ..planning.base_planner import BasePlanner
from .planner_registry import PlannerRegistry
from .reasoning_engine import ReasoningDecision
from .task_decomposer import SubTask

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """
    Cognitive supervisor agent for high-level task delegation and role assignment.
    """

    def __init__(self, planner_registry: PlannerRegistry | None = None):
        self.planner_registry = planner_registry or PlannerRegistry.get_instance()

    def delegate_subtask(
        self, subtask: SubTask, reasoning: ReasoningDecision, context: dict[str, Any]
    ) -> tuple[str, BasePlanner, dict[str, Any]]:
        """
        Delegate a subtask node in the TaskGraph to a domain role planner.

        Args:
            subtask: SubTask node from TaskGraph
            reasoning: ReasoningDecision from ReasoningEngine
            context: Shared execution context

        Returns:
            Tuple of (planner_name, BasePlanner_instance, plan_payload)
        """
        role_key = subtask.required_role.value.lower()
        planner = self.planner_registry.get_planner(role_key)

        if not planner:
            logger.warning(
                f"No planner registered for role '{role_key}', falling back to default"
            )
            planner = self.planner_registry.get_planner(
                "coding"
            ) or self.planner_registry.get_planner("desktop")

        logger.info(
            f"SupervisorAgent delegating subtask '{subtask.title}' to role planner '{role_key}'"
        )

        plan_payload = planner.create_plan(
            goal_text=subtask.description,
            capability=subtask.capability,
            parameters=subtask.parameters,
        )

        return role_key, planner, plan_payload
