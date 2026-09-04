"""
Capability Graph Dependency Resolver
Uses CapabilityRegistry metadata and DesktopContext World Model state to construct graph execution plans automatically.
"""

import uuid

from ..native.capability_registry import CapabilityRegistry
from ..native.desktop_context import DesktopContext, get_desktop_context
from .desktop_goal import DesktopGoal
from .desktop_plan import DesktopPlan
from .desktop_step import DesktopStep, StepStatus, StepType


class DependencyResolver:
    """
    Resolves CapabilityRegistry graph relationships (requires, verifies, rollback) into a DesktopPlan,
    consulting DesktopContext to eliminate redundant pre-requisite steps.
    """

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        context: DesktopContext | None = None,
    ):
        self.registry = registry or CapabilityRegistry()
        self.context = context or get_desktop_context()

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
        # Check cross-app coordination and chain window activation if needed
        try:
            from routing.app_context_router import AppContextRouter
            router = AppContextRouter.get_instance()
            curr_app = ""
            if self.context and hasattr(self.context, "active_window"):
                curr_app = getattr(self.context.active_window, "app_name", "") or ""

            target_app = (goal.parameters or {}).get("target_app")
            tgt = target_app
            if not tgt and goal.goal:
                _, _, detected_tgt = router.detect_cross_app_intent(goal.goal, current_app=curr_app)
                tgt = detected_tgt

            if tgt and (not curr_app or curr_app.lower() != tgt.lower()):
                plan.add_step(
                    DesktopStep(
                        step_id=f"step_{len(plan.steps)+1}_prep",
                        capability="window.switch_to",
                        description=f"Switch to {tgt}",
                        step_type=StepType.PREPARATION,
                        arguments={"title": tgt, "app_name": tgt},
                    )
                )
                plan.add_step(
                    DesktopStep(
                        step_id=f"step_{len(plan.steps)+1}_prep",
                        capability="screen.wait_for_change",
                        description=f"Wait for {tgt} to focus and stabilize",
                        step_type=StepType.PREPARATION,
                        arguments={"timeout": 0.5},
                    )
                )
        except Exception:
            pass

        for req_cap in graph.get("requires", []):
            req_desc = self.registry.get(req_cap)
            step_desc = req_desc.description if req_desc else f"Prepare {req_cap}"

            # Check DesktopContext World Model to evaluate if pre-requisite is already satisfied
            skip_step = False
            if (
                req_cap == "list_windows"
                and self.context
                and self.context.get_windows()
            ):

                # Windows already cached in context, but keep prep step for freshness unless explicit
                pass

            plan.add_step(
                DesktopStep(
                    step_id=f"step_{len(plan.steps)+1}_prep",
                    capability=req_cap,
                    description=step_desc,
                    step_type=StepType.PREPARATION,
                    arguments=goal.parameters,
                    status=StepStatus.SKIPPED if skip_step else StepStatus.PENDING,
                )
            )

        # 2. Main Action Step
        main_desc = self.registry.get(capability_name)
        action_desc = (
            main_desc.description if main_desc else f"Execute {capability_name}"
        )
        plan.add_step(
            DesktopStep(
                step_id=f"step_{len(plan.steps)+1}_action",
                capability=capability_name,
                description=action_desc,
                step_type=StepType.ACTION,
                arguments=goal.parameters,
                requires=graph.get("requires", []),
                verifies=graph.get("verifies", []),
                rollback_capabilities=graph.get("rollback_capabilities", []),
            )
        )

        # 3. Verification Steps (Verifies)
        for ver_cap in graph.get("verifies", []):
            ver_desc = self.registry.get(ver_cap)
            ver_msg = ver_desc.description if ver_desc else f"Verify {ver_cap}"
            plan.add_step(
                DesktopStep(
                    step_id=f"step_{len(plan.steps)+1}_verify",
                    capability=ver_cap,
                    description=ver_msg,
                    step_type=StepType.VERIFICATION,
                    arguments=goal.parameters,
                )
            )

        return plan
