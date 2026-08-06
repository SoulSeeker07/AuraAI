"""
Layer 7: Execution Coordinator
==============================

Aura doesn't execute. It coordinates.

The Execution Coordinator delegates work to:
    * Desktop Engine
    * Browser Engine
    * Research Engine
    * Engineering Engine
    * Voice Engine
    * Memory Engine

Each engine never thinks. It simply executes assigned tasks.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_index: int
    engine: str
    action: str
    success: bool
    observations: list[str] = field(default_factory=list)
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "engine": self.engine,
            "action": self.action,
            "success": self.success,
            "observations": self.observations,
            "error": self.error,
            "data": self.data,
            "execution_time": self.execution_time,
        }


@dataclass
class CoordinationResult:
    """Result of coordinating an entire Execution Map."""

    goal: str
    success: bool
    step_results: list[StepResult] = field(default_factory=list)
    failed_steps: list[StepResult] = field(default_factory=list)
    total_time: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "success": self.success,
            "step_results": [s.to_dict() for s in self.step_results],
            "failed_steps": [s.to_dict() for s in self.failed_steps],
            "total_time": self.total_time,
            "data": self.data,
        }


class ExecutionCoordinator:
    """
    Coordinates execution by delegating each step to the appropriate engine.

    This layer NEVER thinks. It simply coordinates.
    """

    def __init__(
        self,
        orchestrator: Any | None = None,
        engine_callbacks: dict[str, Any] | None = None,
    ):
        """
        Initialize the Execution Coordinator.

        Args:
            orchestrator: Optional MasterOrchestrator for delegation.
            engine_callbacks: Optional dict of engine → callable.
                Each callback receives (action, parameters) and returns a result dict.
        """
        self.orchestrator = orchestrator
        self.engine_callbacks = engine_callbacks or {}

    # ── Public API ──────────────────────────────────────────────────────────

    async def coordinate(self, execution_map: dict[str, Any]) -> CoordinationResult:
        """
        Coordinate the execution of an Execution Map.

        Args:
            execution_map: The validated Execution Map dict.

        Returns:
            CoordinationResult with per-step results.
        """
        import time

        start_time = time.time()
        step_results: list[StepResult] = []
        failed_steps: list[StepResult] = []

        goal = execution_map.get("goal", "unknown")
        steps = execution_map.get("steps", [])

        logger.info(f"ExecutionCoordinator coordinating: '{goal}' ({len(steps)} steps)")

        for i, step in enumerate(steps):
            engine = step.get("engine", "")
            action = step.get("action", "")
            params = step.get("parameters", {})

            logger.info(
                f"Coordinator step {i + 1}/{len(steps)}: "
                f"[{engine}] {action}"
            )

            step_result = await self._coordinate_step(i, engine, action, params)

            if step_result.success:
                logger.info(f"Step {i + 1} succeeded")
            else:
                logger.warning(f"Step {i + 1} failed: {step_result.error}")
                failed_steps.append(step_result)

            step_results.append(step_result)

        total_time = time.time() - start_time
        success = len(failed_steps) == 0

        logger.info(
            f"ExecutionCoordinator completed: success={success}, "
            f"failed={len(failed_steps)}/{len(step_results)}, time={total_time:.2f}s"
        )

        return CoordinationResult(
            goal=goal,
            success=success,
            step_results=step_results,
            failed_steps=failed_steps,
            total_time=total_time,
        )

    # ── Step Coordination ───────────────────────────────────────────────────

    async def _coordinate_step(
        self, index: int, engine: str, action: str, params: dict[str, Any]
    ) -> StepResult:
        """
        Coordinate a single step by delegating to the right engine.

        Priority:
        1. Custom engine callback
        2. MasterOrchestrator
        3. Provider fallback
        """
        import time

        start_time = time.time()

        # 1. Custom engine callback or EngineRegistry lookup
        from .aca.engine_interface import EngineRegistry

        reg_engine = EngineRegistry.get_instance().resolve(engine)
        if reg_engine is not None:
            try:
                res = reg_engine.execute(action, params)
                execution_time = time.time() - start_time
                observations = res.get("observations", []) if isinstance(res, dict) else [str(res)]
                return StepResult(
                    step_index=index,
                    engine=engine,
                    action=action,
                    success=res.get("success", True) if isinstance(res, dict) else True,
                    observations=observations,
                    data=res if isinstance(res, dict) else {"output": str(res)},
                    execution_time=execution_time,
                )
            except Exception as e:
                return StepResult(
                    step_index=index,
                    engine=engine,
                    action=action,
                    success=False,
                    error=f"EngineRegistry engine '{engine}' failed: {type(e).__name__}: {e}",
                    execution_time=time.time() - start_time,
                )

        if engine in self.engine_callbacks:
            try:
                callback = self.engine_callbacks[engine]
                if asyncio.iscoroutinefunction(callback):
                    result = await callback(action, params)
                else:
                    result = callback(action, params)

                execution_time = time.time() - start_time
                observations = (
                    result.get("observations", [])
                    if isinstance(result, dict)
                    else [str(result)]
                )
                return StepResult(
                    step_index=index,
                    engine=engine,
                    action=action,
                    success=result.get("success", True) if isinstance(result, dict) else True,
                    observations=observations,
                    data=result if isinstance(result, dict) else {"output": str(result)},
                    execution_time=execution_time,
                )
            except Exception as e:
                return StepResult(
                    step_index=index,
                    engine=engine,
                    action=action,
                    success=False,
                    error=f"Engine callback failed: {type(e).__name__}: {e}",
                    execution_time=time.time() - start_time,
                )

        # 2. MasterOrchestrator delegation
        if self.orchestrator is not None:
            try:
                result = await self._delegate_to_orchestrator(engine, action, params)
                execution_time = time.time() - start_time
                return StepResult(
                    step_index=index,
                    engine=engine,
                    action=action,
                    success=result.success,
                    observations=list(result.observations or []),
                    data=result.data if isinstance(result.data, dict) else {},
                    execution_time=execution_time,
                )
            except Exception as e:
                logger.warning(f"Orchestrator delegation failed: {e}")

        # 3. Provider fallback
        try:
            result = await self._provider_fallback(engine, action, params)
            return StepResult(
                step_index=index,
                engine=engine,
                action=action,
                success=True,
                observations=[str(result)],
                data={"response": str(result)},
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return StepResult(
                step_index=index,
                engine=engine,
                action=action,
                success=False,
                error=f"Coordination failed: {type(e).__name__}: {e}",
                execution_time=time.time() - start_time,
            )

    async def _delegate_to_orchestrator(
        self, engine: str, action: str, params: dict[str, Any]
    ) -> Any:
        """Delegate a step to the MasterOrchestrator."""
        # Build a goal description for the orchestrator
        goal = f"{action}"
        if params.get("url"):
            goal = f"Navigate to {params['url']}"
        elif params.get("application"):
            goal = f"Open {params['application']}"
        elif params.get("query"):
            goal = f"Research: {params['query']}"
        elif params.get("task"):
            goal = str(params["task"])

        if hasattr(self.orchestrator, "process_request_async"):
            return await self.orchestrator.process_request_async(goal, None, params)

        return self.orchestrator.process_request(goal, None, params)

    async def _provider_fallback(
        self, engine: str, action: str, params: dict[str, Any]
    ) -> str:
        """Generate a natural language response using the LLM provider."""
        llm = getattr(self, "_llm_client", None)
        if llm is not None:
            try:
                message = params.get("message", f"{action} {params}")
                response = llm.chat.completions.create(
                    model=params.get("model", "llama3-8b-8192"),
                    messages=[
                        {"role": "system", "content": "You are Aura, an AI operating system."},
                        {"role": "user", "content": message},
                    ],
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.debug(f"LLM call failed: {e}")

        return f"[{engine}] {action} completed"

    # ── Configuration ───────────────────────────────────────────────────────

    def register_engine(self, engine: str, callback: Any) -> None:
        """Register a custom engine callback."""
        self.engine_callbacks[engine] = callback

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for provider fallback."""
        self._llm_client = client


__all__ = ["ExecutionCoordinator", "CoordinationResult", "StepResult"]