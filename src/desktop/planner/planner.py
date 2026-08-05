"""
Desktop Planner Orchestrator
Main entry point for Phase 3 Desktop Planning. Converts goals into graph-driven execution plans and dispatches to DesktopExecutionEngine.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from ..native.capability_registry import CapabilityRegistry
from ..native.desktop_execution_engine import (
    DesktopExecutionEngine,
    get_desktop_execution_engine,
)
from .base_planner import BasePlanner
from .dependency_resolver import DependencyResolver
from .desktop_plan import DesktopPlan
from .desktop_step import DesktopStep, StepStatus, StepType
from .execution_memory import ExecutionMemory
from .execution_monitor import ExecutionMonitor
from .execution_trace import ExecutionTrace
from .goal_classifier import GoalClassifier
from .goal_graph import GoalGraph
from .goal_parser import GoalParser
from .plan_cache import PlanCache
from .plan_evaluator import EvaluationResult, PlanEvaluator
from .plan_optimizer import PlanOptimizer
from .planner_events import PlannerEventBus
from .planner_state import PlanState
from .strategy_selector import StrategySelector

logger = logging.getLogger(__name__)


class DesktopPlanner(BasePlanner):
    """
    Graph-driven planner that turns user goals into structured plans and executes them via DesktopExecutionEngine.
    """

    def __init__(
        self,
        engine: DesktopExecutionEngine | None = None,
        registry: CapabilityRegistry | None = None,
        resolver: DependencyResolver | None = None,
        parser: GoalParser | None = None,
        classifier: GoalClassifier | None = None,
        optimizer: PlanOptimizer | None = None,
        cache: PlanCache | None = None,
        event_bus: PlannerEventBus | None = None,
        evaluator: PlanEvaluator | None = None,
        memory: ExecutionMemory | None = None,
        strategy_selector: StrategySelector | None = None,
    ):
        self.engine = engine or get_desktop_execution_engine()
        self.registry = registry or CapabilityRegistry()
        self.resolver = resolver or DependencyResolver(registry=self.registry)
        self.parser = parser or GoalParser()
        self.classifier = classifier or GoalClassifier()
        self.goal_graph = GoalGraph(registry=self.registry)
        self.optimizer = optimizer or PlanOptimizer()
        self.cache = cache or PlanCache()
        self.monitor = ExecutionMonitor()
        self.event_bus = event_bus or PlannerEventBus()
        self.evaluator = evaluator or PlanEvaluator()
        self.memory = memory or ExecutionMemory()
        self.strategy_selector = strategy_selector or StrategySelector()
        self.last_trace: ExecutionTrace | None = None
        self.last_evaluation: EvaluationResult | None = None

    def can_handle(self, goal_text: str) -> bool:
        """Return True if goal is a desktop management goal."""
        goal_lower = goal_text.lower()
        if any(
            goal_lower.startswith(prefix)
            for prefix in ["code.", "chat.", "reason.", "git.", "multimodal."]
        ):
            return False
        return True

    def create_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> DesktopPlan:
        """
        Create a graph-driven execution plan for a goal.

        Args:
            goal_text: Natural language goal
            capability: Optional explicit capability
            parameters: Optional execution parameters

        Returns:
            Resolved and optimized DesktopPlan
        """
        trace = ExecutionTrace(
            trace_id=f"trace_{uuid.uuid4().hex[:8]}",
            agent_subsystem="desktop",
            goal=goal_text,
        )
        self.last_trace = trace

        # Check ExecutionMemory for past identical successful plans
        mem_plan = self.memory.find_best_plan(goal_text)
        if mem_plan:
            logger.info(f"Retrieved plan from ExecutionMemory for goal '{goal_text}'")
            trace.add_node(
                "Memory",
                "Reused plan from ExecutionMemory",
                details={"plan_id": mem_plan.plan_id},
            )
            mem_plan.transition_to(PlanState.CREATED)
            for s in mem_plan.steps:
                s.status = StepStatus.PENDING
            self.event_bus.publish(
                "PlanCreated",
                mem_plan.plan_id,
                {"goal": goal_text, "steps": len(mem_plan.steps)},
            )
            return mem_plan

        # Check short-term cache
        cached = self.cache.get(goal_text)
        if cached:
            logger.info(f"Retrieved cached plan for goal '{goal_text}'")
            trace.add_node(
                "Cache",
                "Plan retrieved from cache",
                details={"plan_id": cached.plan_id},
            )
            cached.transition_to(PlanState.CREATED)
            for s in cached.steps:
                s.status = StepStatus.PENDING
            self.event_bus.publish(
                "PlanCreated",
                cached.plan_id,
                {"goal": goal_text, "steps": len(cached.steps)},
            )
            return cached

        goal = self.parser.parse(goal_text, parameters=parameters)
        trace.add_node(
            "Parse",
            "Goal parsed",
            details={"priority": goal.priority.value, "parameters": goal.parameters},
        )

        goal.category = self.classifier.classify(goal_text)
        trace.add_node(
            "Classify",
            f"Goal classified as '{goal.category}'",
            details={"category": goal.category},
        )

        cap_to_use = capability or goal.explicit_capability
        if not cap_to_use:
            cap_to_use = self.engine._discover_capability(goal_text) or "list_windows"
        trace.add_node(
            "CapabilityDiscovery", f"Discovered target capability '{cap_to_use}'"
        )

        raw_plan = self.resolver.resolve_plan(goal, cap_to_use)
        raw_plan.transition_to(PlanState.ANALYZED)
        raw_plan.transition_to(PlanState.PLANNED)
        trace.add_node(
            "Resolve", f"Resolved graph plan with {len(raw_plan.steps)} steps"
        )

        optimized_plan = self.optimize_plan(raw_plan)
        optimized_plan.transition_to(PlanState.OPTIMIZED)
        trace.add_node(
            "Optimize", f"Plan optimized ({len(optimized_plan.steps)} steps)"
        )

        self.event_bus.publish(
            "PlanCreated",
            optimized_plan.plan_id,
            {"goal": goal_text, "steps": len(optimized_plan.steps)},
        )
        return optimized_plan

    def explain_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Dry Run / Explain Mode: Generate a human-readable preview of plan execution.

        Returns:
            Dictionary detailing steps, estimated duration, risk level, permissions, and expected effects.
        """
        plan = self.create_plan(goal_text, capability, parameters)
        steps_preview = []
        max_risk = "LOW"
        permissions = set()
        est_duration = 0.0

        for step in plan.steps:
            desc = self.registry.get(step.capability)
            risk = desc.risk_level.value.upper() if desc else "LOW"
            perm = desc.permission.value if desc else "read"
            permissions.add(perm)

            if risk in ("HIGH", "CRITICAL"):
                max_risk = risk
            elif risk == "MODERATE" and max_risk != "HIGH" and max_risk != "CRITICAL":
                max_risk = "MODERATE"

            duration = step.estimated_time_ms
            est_duration += duration

            steps_preview.append(
                {
                    "step_id": step.step_id,
                    "capability": step.capability,
                    "type": step.step_type.value,
                    "description": step.description,
                    "risk_level": risk,
                    "permission": perm,
                    "estimated_duration_ms": duration,
                }
            )

        return {
            "goal": goal_text,
            "total_steps": len(plan.steps),
            "estimated_duration_ms": est_duration,
            "overall_risk_level": max_risk,
            "required_permissions": sorted(list(permissions)),
            "steps": steps_preview,
            "explain_summary": f"Plan requires {len(plan.steps)} steps (~{est_duration/1000.0:.1f}s) with risk level '{max_risk}'.",
        }

    def optimize_plan(self, plan: DesktopPlan) -> DesktopPlan:
        """Optimize step ordering in plan."""
        return self.optimizer.optimize(plan)

    def execute_plan(self, plan: DesktopPlan) -> DesktopPlan:
        """
        Execute all steps in a DesktopPlan sequentially through DesktopExecutionEngine.

        Args:
            plan: The DesktopPlan to execute

        Returns:
            Updated DesktopPlan with execution results
        """
        logger.info(f"Executing DesktopPlan '{plan.plan_id}' ({len(plan.steps)} steps)")
        plan.transition_to(PlanState.EXECUTING)
        self.event_bus.publish(
            "PlanStarted", plan.plan_id, {"total_steps": len(plan.steps)}
        )

        if self.last_trace:
            self.last_trace.add_node(
                "Execute", f"Started plan execution with {len(plan.steps)} steps"
            )

        all_ok = True

        for step in plan.steps:
            step.status = StepStatus.RUNNING
            self.monitor.on_step_start(step)

            if step.step_type == StepType.VERIFICATION:
                plan.transition_to(PlanState.VERIFYING)
                self.event_bus.publish(
                    "StepVerifying",
                    plan.plan_id,
                    {"step_id": step.step_id, "capability": step.capability},
                )

            self.event_bus.publish(
                "StepStarted",
                plan.plan_id,
                {"step_id": step.step_id, "capability": step.capability},
            )

            # Attempt execution with retries
            attempt = 0
            res = None
            start_t = datetime.now().timestamp()

            while attempt <= step.max_retries:
                res = self.engine.execute(
                    goal=step.description,
                    capability=step.capability,
                    arguments=step.arguments,
                )
                step.retry_count = attempt
                if res.success:
                    break
                attempt += 1

            step.actual_time_ms = (datetime.now().timestamp() - start_t) * 1000.0

            # Record adapter execution performance for StrategySelector
            if res and res.manager:
                self.strategy_selector.record_execution(
                    capability=step.capability,
                    adapter_name=res.manager,
                    success=res.success,
                    duration_ms=step.actual_time_ms,
                )

            if res and res.success:
                step.status = StepStatus.SUCCESS
                step.result_data = res.data
                self.monitor.on_step_finish(step, success=True)
                self.event_bus.publish(
                    "StepCompleted",
                    plan.plan_id,
                    {"step_id": step.step_id, "capability": step.capability},
                )
                if self.last_trace:
                    self.last_trace.add_node(
                        "StepCompleted",
                        f"Step '{step.step_id}' succeeded",
                        duration_ms=step.actual_time_ms,
                        details={"capability": step.capability},
                    )
            else:
                step.status = StepStatus.FAILURE
                step.error_message = res.error if res else "Unknown error"
                self.monitor.on_step_finish(
                    step, success=False, error=step.error_message
                )
                self.event_bus.publish(
                    "StepFailed",
                    plan.plan_id,
                    {"step_id": step.step_id, "error": step.error_message},
                )
                if self.last_trace:
                    self.last_trace.add_node(
                        "StepFailed",
                        f"Step '{step.step_id}' failed: {step.error_message}",
                    )

                # Adaptive Replanning or Recovery steps
                replanned = self.adaptive_replan(plan, step)
                if not replanned and step.rollback_capabilities:
                    plan.transition_to(PlanState.RECOVERING)
                    self.event_bus.publish(
                        "StepRecovering",
                        plan.plan_id,
                        {
                            "step_id": step.step_id,
                            "rollback": step.rollback_capabilities,
                        },
                    )
                    for rb_cap in step.rollback_capabilities:
                        rb_res = self.engine.execute(
                            goal=f"Rollback {step.capability}", capability=rb_cap
                        )
                        step.rollback_result = rb_res.data

                all_ok = False
                logger.warning(
                    f"Plan step '{step.step_id}' failed: {step.error_message}"
                )
                break

        plan.completed_at = datetime.now()
        plan.is_successful = all_ok

        # Evaluate plan quality score
        eval_res = self.evaluator.evaluate(plan)
        self.last_evaluation = eval_res

        if all_ok:
            plan.transition_to(PlanState.COMPLETED)
            self.cache.put(plan.goal.goal, plan)
            self.memory.store_plan(plan, eval_res)
            self.event_bus.publish(
                "PlanCompleted",
                plan.plan_id,
                {"goal": plan.goal.goal, "score": eval_res.overall_score},
            )
            if self.last_trace:
                self.last_trace.complete(success=True, score=eval_res.overall_score)
        else:
            plan.transition_to(PlanState.FAILED)
            self.event_bus.publish(
                "PlanFailed",
                plan.plan_id,
                {"goal": plan.goal.goal, "score": eval_res.overall_score},
            )
            if self.last_trace:
                self.last_trace.complete(success=False, score=eval_res.overall_score)

        return plan

    def adaptive_replan(self, plan: DesktopPlan, failed_step: DesktopStep) -> bool:
        """
        Attempt adaptive replanning by querying alternative capabilities for a failed step.

        Args:
            plan: The executing DesktopPlan
            failed_step: The step that failed

        Returns:
            True if fallback capability succeeded.
        """
        desc = self.registry.get(failed_step.capability)
        if not desc:
            return False

        fallbacks = []
        if desc.fallback_capability:
            fallbacks.append(desc.fallback_capability)
        fallbacks.extend(desc.alternative_actions)

        for fb_cap in fallbacks:
            logger.info(
                f"Adaptive Replanning: attempting fallback capability '{fb_cap}' for step '{failed_step.step_id}'"
            )
            res = self.engine.execute(
                goal=f"Fallback {failed_step.description}",
                capability=fb_cap,
                arguments=failed_step.arguments,
            )
            if res.success:
                failed_step.status = StepStatus.SUCCESS
                failed_step.result_data = res.data
                failed_step.error_message = None
                if self.last_trace:
                    self.last_trace.add_node(
                        "AdaptiveReplan", f"Fallback capability '{fb_cap}' succeeded"
                    )
                return True

        return False

    def plan_and_execute(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> DesktopPlan:
        """Convenience method to create and execute a plan in one call."""
        plan = self.create_plan(goal_text, capability, parameters)
        return self.execute_plan(plan)
