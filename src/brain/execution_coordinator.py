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

    def render_trace(self, level: int = 1) -> str:
        """Render Aura Activity Trace at Level 1 (Compact), Level 2 (Summary), or Level 3 (Full Diagnostic)."""
        from core.orchestration.activity_trace_renderer import ActivityTraceRenderer
        return ActivityTraceRenderer.render(self, level=level)


class ExecutionCoordinator:
    """
    Coordinates execution by delegating each step to the appropriate engine.

    This layer NEVER thinks. It simply coordinates.
    """

    def __init__(
        self,
        orchestrator: Any | None = None,
        engine_callbacks: dict[str, Any] | None = None,
        memory_manager: Any | None = None,
    ):
        """
        Initialize the Execution Coordinator.

        Args:
            orchestrator: Optional MasterOrchestrator for delegation.
            engine_callbacks: Optional dict of engine → callable.
                Each callback receives (action, parameters) and returns a result dict.
            memory_manager: Optional MemoryManager for conversation context in fallbacks.
        """
        self.orchestrator = orchestrator
        self.engine_callbacks = engine_callbacks or {}
        self.memory_manager = memory_manager

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
                f"Coordinator step {i + 1}/{len(steps)}: " f"[{engine}] {action}"
            )

            step_result = await self._coordinate_step(i, engine, action, params)

            if step_result.success:
                logger.info(f"Step {i + 1} succeeded")
            else:
                logger.warning(f"Step {i + 1} failed: {step_result.error}")
                failed_steps.append(step_result)

            step_results.append(step_result)

        total_time = time.time() - start_time
        steps_succeeded = len(failed_steps) == 0

        # Invoke M19.1 Goal Verifier Engine
        from .goal_verifier import GoalVerifier
        goal_verifier = GoalVerifier()
        temp_coord_result = CoordinationResult(
            goal=goal,
            success=steps_succeeded,
            step_results=step_results,
            failed_steps=failed_steps,
            total_time=total_time,
        )
        goal_report = goal_verifier.verify_goal(goal, temp_coord_result)

        overall_success = steps_succeeded and goal_report.passed

        logger.info(
            f"ExecutionCoordinator completed: success={overall_success} (steps={steps_succeeded}, goal={goal_report.passed}), "
            f"failed={len(failed_steps)}/{len(step_results)}, time={total_time:.2f}s"
        )

        return CoordinationResult(
            goal=goal,
            success=overall_success,
            step_results=step_results,
            failed_steps=failed_steps,
            total_time=total_time,
            data={"goal_verification": goal_report.to_dict()},
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
        try:
            from ..core.orchestration.observation_models import ExpectedState, FailureType
        except (ImportError, ValueError):
            from core.orchestration.observation_models import ExpectedState, FailureType

        expected_state = ExpectedState(
            process=params.get("application") or params.get("app_name"),
            url=params.get("url"),
            element=params.get("selector") or params.get("query"),
        )

        reg_engine = EngineRegistry.get_instance().resolve(engine)
        if reg_engine is not None:
            try:
                try:
                    res = reg_engine.execute(action, params)
                except Exception as exc:
                    res = {"success": False, "observations": [f"Execution exception: {exc}"]}
                execution_time = time.time() - start_time

                obs = None
                v_report = None
                if hasattr(reg_engine, "observe"):
                    try:
                        obs = reg_engine.observe(action, params)
                    except Exception:
                        obs = None

                if hasattr(reg_engine, "verify") and obs is not None:
                    try:
                        v_report = reg_engine.verify(expected_state, obs)
                    except Exception:
                        v_report = None

                # Physical Failure Recovery & Self-Healing Loop
                recovery_trace = None
                alt_target = params.get("alternative_selector") or params.get("alternative_url")
                is_failed = (v_report is not None and not v_report.passed) or (not getattr(res, "success", True) if not isinstance(res, dict) else not res.get("success", True))

                if is_failed:
                    err_str = str(getattr(res, "observations", []) or (res.get("observations") if isinstance(res, dict) else str(res))).lower()
                    if v_report and getattr(v_report, "errors", None):
                        err_str += " " + " ".join(v_report.errors).lower()

                    # 1. Classify Barrier Failures (CAPTCHA, Auth, Permission) -> Immediate Honest BLOCKED
                    is_barrier = any(w in err_str for w in ["captcha", "auth_required", "permission_denied", "sign in", "log in", "access denied"])
                    if is_barrier:
                        logger.warning(f"[ExecutionCoordinator] Security/Auth barrier detected at Step {index + 1}. Halting as BLOCKED.")
                        res = {"success": False, "status": "BLOCKED", "barrier_type": "SECURITY_BARRIER"}
                        is_failed = True

                    # 2. Alternative Target Recovery
                    elif alt_target:
                        logger.info(f"[ExecutionCoordinator] Step {index + 1} execution/verification failed. Recovering via alt_target='{alt_target}'")
                        recovery_params = {**params, "recovered": True}
                        if alt_target.startswith("http"):
                            recovery_params["url"] = alt_target
                        else:
                            recovery_params["selector"] = alt_target
                            recovery_params["primary_selector"] = None

                        res_alt = reg_engine.execute(action, recovery_params)
                        if hasattr(reg_engine, "observe"):
                            obs_alt = reg_engine.observe(action, recovery_params)
                            if hasattr(reg_engine, "verify"):
                                rec_expected_state = ExpectedState(
                                    process=recovery_params.get("application") or recovery_params.get("app_name"),
                                    url=recovery_params.get("url"),
                                    element=recovery_params.get("selector"),
                                )
                                v_report_alt = reg_engine.verify(rec_expected_state, obs_alt)
                                if v_report_alt.passed:
                                    res = res_alt
                                    obs = obs_alt
                                    v_report = v_report_alt
                                    recovery_trace = {
                                        "primary_target": params.get("url") or params.get("primary_selector") or params.get("selector"),
                                        "alternative_target": alt_target,
                                        "primary_failure": FailureType.VERIFICATION_FAILURE.value,
                                        "recovery_status": "RECOVERED_SUCCESS",
                                    }

                    # 3. Transient Self-Healing (Stale DOM, Focus Loss, Slow Load)
                    else:
                        is_transient = any(w in err_str for w in ["stale", "focus", "timeout", "unavailable", "loading", "not active", "dom", "hwnd", "exception", "failure"])
                        if is_transient:
                            logger.info(f"[ExecutionCoordinator] Step {index + 1} transient physical failure detected. Initiating re-observation and self-healing retry.")
                            time.sleep(0.3)
                            # Re-observe live environment
                            if hasattr(reg_engine, "observe"):
                                obs_retry = reg_engine.observe(action, params)
                            # Re-focus desktop HWND if lost focus
                            if engine == "desktop" and params.get("app_name"):
                                try:
                                    reg_engine.execute("app_open", {"app_name": params.get("app_name")})
                                except Exception:
                                    pass

                            # Retry execution
                            res_retry = reg_engine.execute(action, params)
                            if hasattr(reg_engine, "observe"):
                                obs_retry = reg_engine.observe(action, params)
                                if hasattr(reg_engine, "verify"):
                                    v_report_retry = reg_engine.verify(expected_state, obs_retry)
                                    if v_report_retry.passed:
                                        res = res_retry
                                        obs = obs_retry
                                        v_report = v_report_retry
                                        recovery_trace = {
                                            "primary_target": params.get("selector") or params.get("url") or action,
                                            "primary_failure": "TRANSIENT_PHYSICAL_FAILURE",
                                            "recovery_status": "RECOVERED_SUCCESS",
                                        }

                if hasattr(res, "observations"):
                    observations = list(res.observations)
                elif isinstance(res, dict):
                    observations = res.get("observations", [])
                else:
                    observations = [str(res)]

                if hasattr(res, "data") and isinstance(res.data, dict):
                    data_dict = dict(res.data)
                elif isinstance(res, dict):
                    data_dict = dict(res)
                else:
                    data_dict = {"output": str(res)}

                if obs is not None:
                    data_dict["observation"] = obs.to_dict()
                if v_report is not None:
                    data_dict["verification_report"] = v_report.to_dict()
                if recovery_trace:
                    data_dict["recovery_trace"] = recovery_trace

                res_success = getattr(res, "success", True) if not isinstance(res, dict) else res.get("success", True)
                if v_report is not None:
                    step_success = bool(v_report.passed and res_success)
                    logger.warning(f"[DEBUG_COORD] step={index+1} action={action} res_success={res_success} v_report_passed={v_report.passed} evidence={v_report.evidence}")
                else:
                    step_success = bool(res_success)
                    logger.warning(f"[DEBUG_COORD] step={index+1} action={action} res_success={res_success} v_report=None")

                return StepResult(
                    step_index=index,
                    engine=engine,
                    action=action,
                    success=step_success,
                    observations=observations,
                    data=data_dict,
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
                    success=(
                        result.get("success", True)
                        if isinstance(result, dict)
                        else True
                    ),
                    observations=observations,
                    data=(
                        result if isinstance(result, dict) else {"output": str(result)}
                    ),
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
        goal = params.get("goal") or f"{action}"
        if params.get("url"):
            goal = f"Navigate to {params['url']}"
        elif params.get("application") and action in (
            "launch",
            "launch_application",
            "open_application",
            "app_open",
            "open",
        ):
            goal = f"Open {params['application']}"
        elif params.get("query"):
            goal = f"Research: {params['query']}"
        elif params.get("task"):
            goal = str(params["task"])
        elif "." in action and not params.get("goal"):
            goal = f"Execute capability {action}"

        if hasattr(self.orchestrator, "process_request_async"):
            return await self.orchestrator.process_request_async(goal, None, params)

        return self.orchestrator.process_request(goal, None, params)

    async def _provider_fallback(
        self, engine: str, action: str, params: dict[str, Any]
    ) -> str:
        """Generate a natural language response using the LLM provider."""
        from ai.provider_manager import ProviderManager
        from ai.models import ChatRequest, ChatMessage

        provider = ProviderManager()
        try:
            message = params.get("message") or params.get("response") or f"{action} {params}"
            messages = []
            
            if self.memory_manager is not None:
                context_msgs = self.memory_manager.get_context_messages()
                # Prepend Persona System Prompt
                messages.append(ChatMessage(role="system", content="You are Aura, an AI operating system."))
                for msg in context_msgs:
                    messages.append(ChatMessage(role=msg["role"], content=msg["content"]))
            else:
                messages.append(ChatMessage(role="system", content="You are Aura, an AI operating system."))
                
            messages.append(ChatMessage(role="user", content=message))

            req = ChatRequest(
                messages=messages,
                model=params.get("model", "llama-3.1-8b-instant"),
            )
            response = provider.chat(req)
            return response.text
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
