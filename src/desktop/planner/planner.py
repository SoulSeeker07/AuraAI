"""
Desktop Planner Orchestrator
Main entry point for Phase 3 Desktop Planning. Converts goals into graph-driven execution plans and dispatches to DesktopExecutionEngine.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging

from ..native.capability_registry import CapabilityRegistry
from ..native.desktop_execution_engine import DesktopExecutionEngine, get_desktop_execution_engine
from .desktop_goal import DesktopGoal
from .desktop_step import StepStatus
from .desktop_plan import DesktopPlan
from .dependency_resolver import DependencyResolver

logger = logging.getLogger(__name__)


class DesktopPlanner:
    """
    Graph-driven planner that turns user goals into structured plans and executes them via DesktopExecutionEngine.
    """

    def __init__(
        self,
        engine: Optional[DesktopExecutionEngine] = None,
        registry: Optional[CapabilityRegistry] = None,
        resolver: Optional[DependencyResolver] = None,
    ):
        self.engine = engine or get_desktop_execution_engine()
        self.registry = registry or CapabilityRegistry()
        self.resolver = resolver or DependencyResolver(registry=self.registry)
        logger.info("DesktopPlanner initialized")

    def create_plan(
        self,
        goal_text: str,
        capability: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> DesktopPlan:
        """
        Create a graph-driven execution plan for a goal.

        Args:
            goal_text: Natural language goal
            capability: Optional explicit capability
            parameters: Optional execution parameters

        Returns:
            Resolved DesktopPlan
        """
        parameters = parameters or {}
        goal = DesktopGoal(
            goal=goal_text,
            explicit_capability=capability,
            parameters=parameters,
        )

        cap_to_use = capability
        if not cap_to_use:
            cap_to_use = self.engine._discover_capability(goal_text) or "list_windows"

        return self.resolver.resolve_plan(goal, cap_to_use)

    def execute_plan(self, plan: DesktopPlan) -> DesktopPlan:
        """
        Execute all steps in a DesktopPlan sequentially through DesktopExecutionEngine.

        Args:
            plan: The DesktopPlan to execute

        Returns:
            Updated DesktopPlan with execution results
        """
        logger.info(f"Executing DesktopPlan '{plan.plan_id}' ({len(plan.steps)} steps)")
        all_ok = True

        for step in plan.steps:
            step.status = StepStatus.RUNNING
            res = self.engine.execute(
                goal=step.description,
                capability=step.capability,
                arguments=step.arguments,
            )

            if res.success:
                step.status = StepStatus.SUCCESS
                step.result_data = res.data
            else:
                step.status = StepStatus.FAILURE
                step.error_message = res.error
                all_ok = False
                logger.warning(f"Plan step '{step.step_id}' failed: {res.error}")
                break

        plan.completed_at = datetime.now()
        plan.is_successful = all_ok
        return plan

    def plan_and_execute(
        self,
        goal_text: str,
        capability: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> DesktopPlan:
        """Convenience method to create and execute a plan in one call."""
        plan = self.create_plan(goal_text, capability, parameters)
        return self.execute_plan(plan)
