"""
Plan Optimizer
Optimizes step ordering and groups independent steps for parallel or batch execution.
"""

from .desktop_plan import DesktopPlan
from .desktop_step import StepType


class PlanOptimizer:
    """
    Optimizes a DesktopPlan for execution efficiency.
    """

    def optimize(self, plan: DesktopPlan) -> DesktopPlan:
        """
        Deduplicate and optimize steps in a DesktopPlan.

        Args:
            plan: Input DesktopPlan

        Returns:
            Optimized DesktopPlan
        """
        seen_capabilities = set()
        optimized_steps = []

        for step in plan.steps:
            # Keep action steps always; deduplicate read preparation steps if duplicate
            if step.step_type == StepType.PREPARATION:
                if step.capability in seen_capabilities:
                    continue
                seen_capabilities.add(step.capability)

            optimized_steps.append(step)

        plan.steps = optimized_steps
        return plan
