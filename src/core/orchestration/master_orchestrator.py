"""
Master Orchestrator
Main entry point for Aura AI Orchestration. Receives user requests, classifies intent, dispatches to planners and backends, and merges execution results.
"""

import logging
from datetime import datetime
from typing import Any

from ..backends.backend_registry import BackendRegistry
from ..planning.execution_result import ExecutionResult
from .planner_registry import PlannerRegistry
from .result_merger import ResultMerger

logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """
    Master Orchestrator for coordinating planners, backends, and multi-subsystem goals.
    """

    def __init__(
        self,
        planner_registry: PlannerRegistry | None = None,
        backend_registry: BackendRegistry | None = None,
        result_merger: ResultMerger | None = None,
    ):
        self.planner_registry = planner_registry or PlannerRegistry.get_instance()
        self.backend_registry = backend_registry or BackendRegistry.get_instance()
        self.result_merger = result_merger or ResultMerger()
        logger.info(
            "MasterOrchestrator initialized with PlannerRegistry and BackendRegistry"
        )

    def process_request(
        self,
        goal_text: str,
        preferred_planner: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        Process a user request end-to-end through intent routing, planner selection, backend execution, and result merging.

        Args:
            goal_text: Natural language user request
            preferred_planner: Optional explicit planner name ('desktop', 'research', 'coding', 'browser')
            parameters: Optional execution arguments

        Returns:
            Unified ExecutionResult
        """
        start_t = datetime.now().timestamp()
        logger.info(f"MasterOrchestrator processing request: '{goal_text}'")

        # 1. Select Planner
        selected_planner_tuple = None
        if preferred_planner:
            p = self.planner_registry.get_planner(preferred_planner)
            if p:
                selected_planner_tuple = (preferred_planner, p)

        if not selected_planner_tuple:
            candidates = self.planner_registry.find_planners_for_goal(goal_text)
            if candidates:
                selected_planner_tuple = candidates[0]

        if not selected_planner_tuple:
            # Check direct backend execution if no planner matched
            discovered_backend = self.backend_registry.select_best_backend(goal_text)
            if discovered_backend:
                logger.info(
                    f"Direct capability backend match: '{discovered_backend.name}'"
                )
                return discovered_backend.execute(
                    capability=goal_text, goal=goal_text, arguments=parameters
                )

            return ExecutionResult(
                success=False,
                planner="master_orchestrator",
                goal=goal_text,
                confidence=0.0,
                observations=[
                    "No suitable planner or backend adapter registered for goal."
                ],
                warnings=[f"Unresolvable goal: '{goal_text}'"],
            )

        planner_name, planner_instance = selected_planner_tuple
        logger.info(f"Dispatched goal to planner '{planner_name}'")

        # 2. Execute through Planner
        if hasattr(planner_instance, "plan_and_execute"):
            desktop_plan = planner_instance.plan_and_execute(
                goal_text, parameters=parameters
            )
            total_dur = datetime.now().timestamp() - start_t
            return ExecutionResult(
                success=desktop_plan.is_successful,
                planner=planner_name,
                goal=goal_text,
                confidence=0.98 if desktop_plan.is_successful else 0.2,
                execution_time_seconds=total_dur,
                trace=getattr(planner_instance, "last_trace", None),
                observations=[
                    f"Executed through '{planner_name}' with {len(desktop_plan.steps)} steps"
                ],
                data={
                    "plan_id": desktop_plan.plan_id,
                    "state": desktop_plan.state.value,
                },
            )
        else:
            plan = planner_instance.create_plan(goal_text, parameters=parameters)
            plan_res = planner_instance.execute_plan(plan)
            total_dur = datetime.now().timestamp() - start_t
            return ExecutionResult(
                success=getattr(plan_res, "is_successful", True),
                planner=planner_name,
                goal=goal_text,
                confidence=0.95,
                execution_time_seconds=total_dur,
                observations=[f"Executed through '{planner_name}'"],
            )
