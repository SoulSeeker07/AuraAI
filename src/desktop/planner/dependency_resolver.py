"""
Capability Graph Dependency Resolver
Uses CapabilityRegistry metadata to construct graph execution plans automatically.
"""

from typing import List, Dict, Any, Optional
import uuid

from ..native.capability_registry import CapabilityRegistry
from .desktop_goal import DesktopGoal
from .desktop_step import DesktopStep, StepType, StepStatus
from .desktop_plan import DesktopPlan


class DependencyResolver:
    """
    Resolves CapabilityRegistry graph relationships (requires, verifies, rollback) into a DesktopPlan.
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None):
        self.registry = registry or CapabilityRegistry()

    def resolve_plan(self, goal: DesktopGoal, capability_name: str) -> DesktopPlan:
        """
        Build a multi-step DesktopPlan from capability graph metadata.

        Args:
            goal: User DesktopGoal
            capability_name: Primary action capability

        Returns:
            Fully resolved DesktopPlan with preparation, action, verification, and recovery steps.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        plan = DesktopPlan(plan_id=plan_id, goal=goal)

        graph = self.registry.get_capability_graph(capability_name)

        # 1. Preparation Steps (Requires)
        for req_cap in graph.get("requires", []):
            req_desc = self.registry.get(req_cap)
            step_desc = req_desc.description if req_desc else f"Prepare {req_cap}"
            plan.add_step(DesktopStep(
                step_id=f"step_{len(plan.steps)+1}_prep",
                capability=req_cap,
                description=step_desc,
                step_type=StepType.PREPARATION,
                arguments=goal.parameters,
            ))

        # 2. Main Action Step
        main_desc = self.registry.get(capability_name)
        action_desc = main_desc.description if main_desc else f"Execute {capability_name}"
        plan.add_step(DesktopStep(
            step_id=f"step_{len(plan.steps)+1}_action",
            capability=capability_name,
            description=action_desc,
            step_type=StepType.ACTION,
            arguments=goal.parameters,
            requires=graph.get("requires", []),
            verifies=graph.get("verifies", []),
            rollback_capabilities=graph.get("rollback_capabilities", []),
        ))

        # 3. Verification Steps (Verifies)
        for ver_cap in graph.get("verifies", []):
            ver_desc = self.registry.get(ver_cap)
            ver_msg = ver_desc.description if ver_desc else f"Verify {ver_cap}"
            plan.add_step(DesktopStep(
                step_id=f"step_{len(plan.steps)+1}_verify",
                capability=ver_cap,
                description=ver_msg,
                step_type=StepType.VERIFICATION,
                arguments=goal.parameters,
            ))

        return plan
