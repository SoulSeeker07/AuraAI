"""
Layer 3: Executive Executor
===========================

The Executor uses existing engines:
    * Desktop Engine
    * Browser Engine
    * Research Engine
    * Engineering Engine (Antigravity)
    * Memory Engine
    * Voice Engine

These engines never think. They simply execute assigned tasks.

The Executor receives an ExecutionPlan and delegates each action
to the appropriate engine.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from .planner import ExecutionPlan, PlannedAction

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single planned action."""

    action_id: str
    success: bool
    observations: list[str] = field(default_factory=list)
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "success": self.success,
            "observations": self.observations,
            "error": self.error,
            "data": self.data,
            "execution_time": self.execution_time,
        }


@dataclass
class PlanResult:
    """Result of executing an entire ExecutionPlan."""

    plan_id: str
    success: bool
    step_results: list[StepResult] = field(default_factory=list)
    failed_steps: list[StepResult] = field(default_factory=list)
    total_time: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "success": self.success,
            "step_results": [s.to_dict() for s in self.step_results],
            "failed_steps": [s.to_dict() for s in self.failed_steps],
            "total_time": self.total_time,
            "data": self.data,
        }


class ExecutiveExecutor:
    """
    Delegates planned actions to the appropriate execution engines.

    This layer NEVER thinks. It simply executes assigned tasks.
    """

    def __init__(
        self,
        orchestrator: Any | None = None,
        callbacks: dict[str, Any] | None = None,
    ):
        """
        Initialize the Executor.

        Args:
            orchestrator: Optional MasterOrchestrator instance.
            callbacks: Optional dict of capability → callable for custom engines.
                Each callback receives (parameters: dict) and returns a result dict.
        """
        self.orchestrator = orchestrator
        self.callbacks = callbacks or {}

    # ── Public API ──────────────────────────────────────────────────────────

    async def execute_plan(self, plan: ExecutionPlan) -> PlanResult:
        """
        Execute an ExecutionPlan by delegating each action.

        Args:
            plan: The ExecutionPlan produced by the Planner.

        Returns:
            PlanResult with per-step results.
        """
        import time

        start_time = time.time()
        step_results: list[StepResult] = []
        failed_steps: list[StepResult] = []

        logger.info(f"Executor executing plan [{plan.plan_id}]: '{plan.goal}'")

        for action in plan.ordered_actions:
            logger.info(
                f"Executor step: [{action.step_type}] {action.description} "
                f"(capability={action.capability})"
            )

            step_result = await self._execute_action(action)

            if step_result.success:
                logger.info(f"Step {action.action_id} succeeded")
            else:
                logger.warning(f"Step {action.action_id} failed: {step_result.error}")
                failed_steps.append(step_result)

            step_results.append(step_result)

        total_time = time.time() - start_time
        success = len(failed_steps) == 0

        logger.info(
            f"Executor completed plan [{plan.plan_id}]: "
            f"success={success}, failed={len(failed_steps)}/{len(step_results)}, "
            f"time={total_time:.2f}s"
        )

        return PlanResult(
            plan_id=plan.plan_id,
            success=success,
            step_results=step_results,
            failed_steps=failed_steps,
            total_time=total_time,
        )

    # ── Action Execution ────────────────────────────────────────────────────

    async def _execute_action(self, action: PlannedAction) -> StepResult:
        """
        Execute a single planned action by delegating to the right engine.

        Priority:
        1. Custom callback registered for this capability
        2. MasterOrchestrator (if available)
        3. Default provider (conversational fallback)
        """
        import time

        start_time = time.time()

        # 1. Custom callback registered for this capability
        if action.capability in self.callbacks:
            try:
                callback = self.callbacks[action.capability]
                if asyncio.iscoroutinefunction(callback):
                    result = await callback(action.parameters)
                else:
                    result = callback(action.parameters)

                execution_time = time.time() - start_time
                observations = (
                    result.get("observations", [])
                    if isinstance(result, dict)
                    else [str(result)]
                )
                return StepResult(
                    action_id=action.action_id,
                    success=result.get("success", True) if isinstance(result, dict) else True,
                    observations=observations,
                    data=result if isinstance(result, dict) else {"output": str(result)},
                    execution_time=execution_time,
                )
            except Exception as e:
                return StepResult(
                    action_id=action.action_id,
                    success=False,
                    error=f"Callback failed: {type(e).__name__}: {e}",
                    execution_time=time.time() - start_time,
                )

        # 2. MasterOrchestrator delegation
        if self.orchestrator is not None:
            try:
                result = await self._execute_via_orchestrator(action)
                execution_time = time.time() - start_time
                return StepResult(
                    action_id=action.action_id,
                    success=result.success,
                    observations=list(result.observations or []),
                    error="",
                    data=result.data if isinstance(result.data, dict) else {},
                    execution_time=execution_time,
                )
            except Exception as e:
                logger.warning(
                    f"Orchestrator execution failed for {action.action_id}: {e}"
                )

        # 3. Default provider fallback — generate a natural response
        try:
            result = await self._execute_via_provider(action)
            return StepResult(
                action_id=action.action_id,
                success=True,
                observations=[str(result)],
                data={"response": str(result)},
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return StepResult(
                action_id=action.action_id,
                success=False,
                error=f"Execution failed: {type(e).__name__}: {e}",
                execution_time=time.time() - start_time,
            )

    async def _execute_via_orchestrator(self, action: PlannedAction) -> Any:
        """
        Delegate an action to the MasterOrchestrator.

        The orchestrator handles the actual backend selection and execution.
        """
        params = action.parameters or {}

        if hasattr(self.orchestrator, "process_request_async"):
            # Build a goal description for the orchestrator
            goal = action.description
            if params.get("url"):
                goal = f"Navigate to {params['url']}"
            elif params.get("app_name") and str(action.capability).lower() in ("desktop.launch", "app_open", "launch_app", "open_app", "window.open"):
                goal = f"Open {params['app_name']}"
            elif params.get("query"):
                goal = f"Research: {params['query']}"
            elif params.get("task"):
                goal = str(params["task"])

            return await self.orchestrator.process_request_async(goal, None, params)

        # Fallback to sync orchestrator
        return self.orchestrator.process_request(
            action.description, None, params
        )

    async def _execute_via_provider(self, action: PlannedAction) -> str:
        """
        Generate a natural language response using the LLM provider.

        This is the default fallback for any action type.
        """
        params = action.parameters or {}

        # If we have an LLM client, use it
        llm = getattr(self, "_llm_client", None)
        if llm is not None:
            try:
                message = params.get("message", action.description)
                response = llm.chat.completions.create(
                    model=params.get("model", "llama3-8b-8192"),
                    messages=[
                        {"role": "system", "content": "You are Aura, an AI operating system."},
                        {"role": "user", "content": message},
                    ],
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.debug(f"LLM call failed, returning description: {e}")

        # No LLM available — return the action description as the "result"
        return action.description

    def register_callback(self, capability: str, callback: Any) -> None:
        """Register a custom callback for a capability."""
        self.callbacks[capability] = callback

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for provider fallback."""
        self._llm_client = client


__all__ = ["ExecutiveExecutor", "PlanResult", "StepResult"]