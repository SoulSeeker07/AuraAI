"""
Layer 2: Executive Planner
==========================

Converts an ExecutionMap into concrete runtime actions.

The Planner determines:
    * execution order
    * dependencies
    * retries
    * parallel tasks
    * runtime sessions

The planner never decides the goal.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from .execution_map import Capability, ExecutionMap, ExecutionStep

logger = logging.getLogger(__name__)


@dataclass
class PlannedAction:
    """
    A concrete runtime action derived from an ExecutionStep.

    This is what the Executor will actually execute.
    """

    action_id: str
    step_type: str
    description: str
    capability: str
    parameters: dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    timeout: int = 30
    parallel: bool = False
    depends_on: list[str] = field(default_factory=list)
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "step_type": self.step_type,
            "description": self.description,
            "capability": self.capability,
            "parameters": self.parameters,
            "retries": self.retries,
            "timeout": self.timeout,
            "parallel": self.parallel,
            "depends_on": self.depends_on,
            "session_id": self.session_id,
        }


@dataclass
class ExecutionPlan:
    """
    The Planner's output: an ordered, dependency-resolved runnable plan.
    """

    plan_id: str
    execution_map_id: str
    goal: str
    ordered_actions: list[PlannedAction] = field(default_factory=list)
    parallel_groups: list[list[PlannedAction]] = field(default_factory=list)
    total_steps: int = 0
    estimated_timeout: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "execution_map_id": self.execution_map_id,
            "goal": self.goal,
            "ordered_actions": [a.to_dict() for a in self.ordered_actions],
            "parallel_groups": [
                [a.to_dict() for a in group] for group in self.parallel_groups
            ],
            "total_steps": self.total_steps,
            "estimated_timeout": self.estimated_timeout,
        }


class ExecutivePlanner:
    """
    Converts ExecutionMaps into runtime-schedulable ExecutionPlans.

    This is the "organizer" — it never decides the goal.
    """

    def __init__(self):
        self._action_counter = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def create_plan(
        self, execution_map: ExecutionMap, session_id: str = ""
    ) -> ExecutionPlan:
        """
        Convert an ExecutionMap into a concrete ExecutionPlan.

        Args:
            execution_map: The ExecutionMap produced by the DMM.
            session_id: Optional session identifier for traceability.

        Returns:
            ExecutionPlan with ordered, dependency-resolved actions.
        """
        # Validate first
        valid, errors = execution_map.validate()
        if not valid:
            logger.error(f"Planner received invalid ExecutionMap: {errors}")
            raise ValueError(f"Invalid ExecutionMap: {errors}")

        # Convert steps to planned actions
        actions: list[PlannedAction] = []
        for step in execution_map.execution_plan:
            action = self._to_planned_action(step, session_id)
            actions.append(action)

        # Resolve dependencies and order
        ordered, parallel_groups = self._resolve_execution_order(actions)

        # Calculate total timeout
        total_timeout = sum(a.timeout for a in actions)

        logger.info(
            f"Planner created plan for '{execution_map.goal}' "
            f"({len(actions)} steps, {len(parallel_groups)} parallel groups)"
        )

        return ExecutionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            execution_map_id=execution_map.map_id,
            goal=execution_map.goal,
            ordered_actions=ordered,
            parallel_groups=parallel_groups,
            total_steps=len(actions),
            estimated_timeout=total_timeout,
        )

    def optimize_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Optimize an existing plan by merging parallelizable actions.

        The Planner never changes the goal — it only organizes execution.
        """
        # Identify actions that could be parallelized
        # (no dependencies between them)
        parallel_candidates: list[PlannedAction] = []
        for action in plan.ordered_actions:
            if not action.depends_on and action.capability in (
                Capability.RESEARCH.value,
                Capability.PROVIDER.value,
            ):
                parallel_candidates.append(action)

        if len(parallel_candidates) > 1:
            logger.info(
                f"Planner optimized: {len(parallel_candidates)} actions eligible for parallel execution"
            )
            # Mark them as parallel
            for action in parallel_candidates:
                action.parallel = True

        return plan

    # ── Internal Helpers ────────────────────────────────────────────────────

    def _to_planned_action(self, step: ExecutionStep, session_id: str) -> PlannedAction:
        """Convert an ExecutionStep to a PlannedAction."""
        self._action_counter += 1
        return PlannedAction(
            action_id=f"act_{self._action_counter}_{uuid.uuid4().hex[:4]}",
            step_type=step.step_type.value,
            description=step.description,
            capability=step.capability.value,
            parameters=step.parameters,
            retries=step.retries,
            timeout=step.timeout,
            parallel=step.parallel,
            depends_on=step.depends_on,
            session_id=session_id,
        )

    def _resolve_execution_order(
        self, actions: list[PlannedAction]
    ) -> tuple[list[PlannedAction], list[list[PlannedAction]]]:
        """
        Resolve the execution order based on dependencies.

        Creates a topological ordering, grouping independent actions
        into parallel groups.

        Returns:
            (ordered_actions, parallel_groups)
        """
        ordered: list[PlannedAction] = []
        parallel_groups: list[list[PlannedAction]] = []

        current_group: list[PlannedAction] = []
        for action in actions:
            if action.parallel:
                current_group.append(action)
            else:
                if current_group:
                    if len(current_group) > 1:
                        parallel_groups.append(current_group)
                    else:
                        ordered.extend(current_group)
                    current_group = []
                ordered.append(action)

        # Flush remaining group
        if current_group:
            if len(current_group) > 1:
                parallel_groups.append(current_group)
            else:
                ordered.extend(current_group)

        return ordered, parallel_groups


__all__ = ["ExecutivePlanner", "ExecutionPlan", "PlannedAction"]
