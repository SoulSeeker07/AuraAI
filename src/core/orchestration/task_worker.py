"""
M19.5 Generic TaskWorker & Scoped Profiles
==========================================
Location: src/core/orchestration/task_worker.py

Defines a generic TaskWorker execution context with scoped context windows,
permission boundaries, profiles (Research, Test, Coding, Browser), and structured WorkerResult.

Architectural Rule:
    A TaskWorker may execute only within the scope, tools, permissions, and capabilities assigned by
    ExecutionCoordinator. A worker may not modify global policy, spawn another worker, bypass verification,
    bypass autonomy gates, or directly promote its own result to goal success.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WorkerProfile:
    """Capability & permission configuration profile for TaskWorker."""

    profile_name: str
    allowed_tools: list[str] = field(default_factory=list)
    filesystem_scope: list[str] = field(default_factory=list)
    execution_permissions: list[str] = field(default_factory=list)
    can_write: bool = False
    can_execute: bool = False


# Pre-defined profiles
ResearchProfile = WorkerProfile(
    profile_name="ResearchProfile",
    allowed_tools=["web.search", "web.fetch", "doc.query"],
    filesystem_scope=[],
    execution_permissions=["read"],
    can_write=False,
    can_execute=False,
)

TestProfile = WorkerProfile(
    profile_name="TestProfile",
    allowed_tools=["pytest", "unittest", "code.inspect"],
    filesystem_scope=["tests/", "src/"],
    execution_permissions=["read", "execute_test"],
    can_write=False,
    can_execute=True,
)

CodingProfile = WorkerProfile(
    profile_name="CodingProfile",
    allowed_tools=["code.analyze", "code.edit", "ast.inspect"],
    filesystem_scope=["src/", "tests/"],
    execution_permissions=["read", "write", "test"],
    can_write=True,
    can_execute=True,
)

BrowserProfile = WorkerProfile(
    profile_name="BrowserProfile",
    allowed_tools=["browser.open", "browser.click", "browser.input", "browser.extract"],
    filesystem_scope=[],
    execution_permissions=["browser"],
    can_write=False,
    can_execute=False,
)


@dataclass
class WorkerResult:
    """Standardized structured output from a TaskWorker execution."""

    worker_name: str
    status: str  # "SUCCESS", "FAILED", "CANCELLED"
    task: str
    actions_taken: int = 0
    observations: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        raw = {
            "worker_name": self.worker_name,
            "status": self.status,
            "task": self.task,
            "actions_taken": self.actions_taken,
            "observations": self.observations,
            "verification": self.verification,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "recommendations": self.recommendations,
            "duration": self.duration,
        }
        return sanitize_worker_output(raw)


# Regex patterns for sensitive data redaction
_RE_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)
_RE_ANTHROPIC_KEY = re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")
_RE_OPENAI_KEY = re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")
_RE_GROQ_KEY = re.compile(r"\bgsk_[A-Za-z0-9_\-]{20,}\b")
_RE_GITHUB_KEY = re.compile(r"\bgh[pousr]_[A-Za-z0-9_\-]{20,}\b")
_RE_SLACK_KEY = re.compile(r"\bxox[baprs]-[A-Za-z0-9_\-]{10,}\b")
_RE_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_RE_GOOGLE_KEY = re.compile(r"\bAIza[0-9A-Za-z_\-]{30,40}\b")
_RE_BEARER_TOKEN = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE)
_RE_GENERIC_SECRET_KV = re.compile(
    r"\b((?:api[_-]?key|secret|token|password|passwd|auth)\s*[:=]\s*['\"]?)(?!(?:api[_-]?key|secret|token|password|passwd|auth)\b)([a-zA-Z0-9_\-\.]{4,})(['\"]?)",
    re.IGNORECASE,
)
_RE_CREDIT_CARD = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

_SENSITIVE_KEY_NAMES = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "auth",
    "authorization",
    "private_key",
}


def sanitize_worker_output(data: Any) -> Any:
    """
    Recursively sanitize sensitive information (API keys, secrets, tokens,
    passwords, private keys, credit cards) from text, structures, or WorkerResult.
    """
    if data is None:
        return None
    if isinstance(data, str):
        cleaned = data
        cleaned = _RE_PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", cleaned)
        cleaned = _RE_ANTHROPIC_KEY.sub("[REDACTED_API_KEY]", cleaned)
        cleaned = _RE_OPENAI_KEY.sub("[REDACTED_API_KEY]", cleaned)
        cleaned = _RE_GROQ_KEY.sub("[REDACTED_API_KEY]", cleaned)
        cleaned = _RE_GITHUB_KEY.sub("[REDACTED_API_KEY]", cleaned)
        cleaned = _RE_SLACK_KEY.sub("[REDACTED_API_KEY]", cleaned)
        cleaned = _RE_AWS_KEY.sub("[REDACTED_API_KEY]", cleaned)
        cleaned = _RE_GOOGLE_KEY.sub("[REDACTED_API_KEY]", cleaned)
        cleaned = _RE_BEARER_TOKEN.sub(r"\1[REDACTED_SECRET]", cleaned)
        cleaned = _RE_GENERIC_SECRET_KV.sub(r"\1[REDACTED_SECRET]\3", cleaned)
        cleaned = _RE_CREDIT_CARD.sub("[REDACTED_CARD]", cleaned)
        return cleaned
    if isinstance(data, dict):
        sanitized_dict: dict[str, Any] = {}
        for k, v in data.items():
            key_str = str(k).lower()
            if any(sens in key_str for sens in _SENSITIVE_KEY_NAMES):
                sanitized_dict[k] = "[REDACTED_SECRET]"
            else:
                sanitized_dict[k] = sanitize_worker_output(v)
        return sanitized_dict
    if isinstance(data, list):
        return [sanitize_worker_output(item) for item in data]
    if isinstance(data, tuple):
        return tuple(sanitize_worker_output(item) for item in data)
    if isinstance(data, set):
        return {sanitize_worker_output(item) for item in data}
    if isinstance(data, WorkerResult):
        return WorkerResult(
            worker_name=sanitize_worker_output(data.worker_name),
            status=data.status,
            task=sanitize_worker_output(data.task),
            actions_taken=data.actions_taken,
            observations=sanitize_worker_output(data.observations),
            verification=sanitize_worker_output(data.verification),
            artifacts=sanitize_worker_output(data.artifacts),
            errors=sanitize_worker_output(data.errors),
            recommendations=sanitize_worker_output(data.recommendations),
            duration=data.duration,
        )
    return data


class TaskWorker:
    """
    Generic scoped worker assigned bounded execution tasks by ExecutionCoordinator.
    Executes an autonomous, isolated ReAct loop (Perceive -> Reason -> Act -> Observe -> Verify).
    """

    def __init__(
        self,
        worker_name: str,
        profile: WorkerProfile,
        time_budget_seconds: float = 60.0,
        max_turns: int = 10,
    ):
        self.worker_name = worker_name
        self.profile = profile
        self.time_budget_seconds = time_budget_seconds
        self.max_turns = max_turns
        self.messages: list[dict[str, Any]] = []
        self.working_memory: Any = None

    def execute_task(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        coordinator_callback: Any | None = None,
    ) -> WorkerResult:
        """
        Execute an assigned task within the profile's tool/permission boundaries
        using an isolated, multi-turn ReAct loop (Perceive -> Reason -> Act -> Observe -> Verify).

        Args:
            task: Task description.
            context: Bounded input context dictionary (can contain 'llm_caller', 'steps', or 'tool').
            coordinator_callback: Optional callback to invoke engine actions via ExecutionCoordinator.

        Returns:
            Structured, sanitized WorkerResult (no raw chain-of-thought).
        """
        import inspect
        import asyncio
        from .task_working_memory import TaskWorkingMemory

        start_time = time.time()
        context = context or {}
        observations: list[str] = []
        errors: list[str] = []
        actions_count = 0
        verification_status: dict[str, Any] = {"passed": True}

        # Initialize private, isolated working memory
        self.working_memory = TaskWorkingMemory(goal=task, max_steps=self.max_turns)

        logger.info(
            f"[TaskWorker:{self.worker_name}] Starting ReAct loop: '{task}' "
            f"under {self.profile.profile_name} (max_turns={self.max_turns}, budget={self.time_budget_seconds}s)"
        )

        # Perceive phase: seed isolated conversation history
        system_prompt = (
            f"You are subagent '{self.worker_name}', a specialized background worker operating under {self.profile.profile_name}.\n"
            f"Your role: Execute the assigned subtask autonomously within your permission boundary.\n"
            f"Allowed tools: {', '.join(self.profile.allowed_tools)}\n"
            f"Filesystem scope: {', '.join(self.profile.filesystem_scope) if self.profile.filesystem_scope else 'read-only'}\n"
            f"Permissions: {', '.join(self.profile.execution_permissions)}\n"
            "Execution Invariants:\n"
            "1. Plan and execute steps strictly using allowed tools.\n"
            "2. All mutating actions are verified against policy.\n"
            "3. Provide concise observations and structured results."
        )
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Subtask: {task}"},
        ]

        def _execute_single_action(tool_name: str, tool_params: dict[str, Any]) -> tuple[bool, Any, str]:
            """
            Checks tool allowlist, evaluates Gate 2 ExecutionPolicy, executes via callback,
            and runs pluggable capability verification.
            Returns (success: bool, raw_output: Any, detail_or_error: str).
            """
            # 1. Profile Tool Permission Guardrail
            if tool_name not in self.profile.allowed_tools:
                err_msg = f"Tool '{tool_name}' is forbidden for worker profile {self.profile.profile_name}"
                logger.warning(f"[TaskWorker:{self.worker_name}] {err_msg}")
                return False, None, err_msg

            # 2. Gate 2: ExecutionPolicy Risk & Confirmation Guardrail
            try:
                from .execution_policy import ExecutionPolicy, PolicyAction

                policy = ExecutionPolicy.get_instance()
                parts = tool_name.split(".", 1)
                engine = parts[0] if len(parts) > 1 else "generic"
                action = parts[1] if len(parts) > 1 else tool_name

                decision = policy.evaluate_action(engine=engine, action=action, params=tool_params)
                if decision.action == PolicyAction.ASK_USER:
                    risk_str = decision.risk.value.upper() if getattr(decision, "risk", None) else "HIGH"
                    err_msg = (
                        f"Action '{tool_name}' blocked by ExecutionPolicy: "
                        f"Requires user confirmation ({risk_str} risk). "
                        f"Background subagents cannot execute confirmation-gated operations."
                    )
                    logger.warning(f"[TaskWorker:{self.worker_name}] {err_msg}")
                    return False, None, err_msg
            except Exception as pol_err:
                err_msg = (
                    f"ExecutionPolicy evaluation error for '{tool_name}': {pol_err}. "
                    f"Subagents fail closed on policy evaluation failures."
                )
                logger.error(f"[TaskWorker:{self.worker_name}] {err_msg}")
                return False, None, err_msg

            # 3. Act: Execute tool logic via coordinator_callback or unified dispatcher
            raw_out: Any = None
            if coordinator_callback is not None:
                try:
                    if inspect.iscoroutinefunction(coordinator_callback):
                        raw_out = asyncio.run(coordinator_callback(tool_name, tool_params))
                    else:
                        res = coordinator_callback(tool_name, tool_params)
                        raw_out = asyncio.run(res) if inspect.iscoroutine(res) else res
                except Exception as exec_err:
                    return False, None, f"Execution failed: {exec_err}"
            else:
                raw_out = f"Action '{tool_name}' completed (dry-run)."

            # 4. Verify: Run capability-specific verifier from VERIFIER_REGISTRY
            is_verified = True
            verif_reason = "No capability-specific verification required"
            try:
                from .agent_loop import VERIFIER_REGISTRY

                if tool_name in VERIFIER_REGISTRY:
                    verifier_payload = raw_out if isinstance(raw_out, dict) else {"result": raw_out, "status": "success"}
                    is_verified, verif_reason = VERIFIER_REGISTRY[tool_name](tool_name, tool_params, verifier_payload)
            except Exception as v_err:
                err_msg = (
                    f"Verifier execution error for '{tool_name}': {v_err}. "
                    f"Subagents fail closed on verification exceptions."
                )
                logger.error(f"[TaskWorker:{self.worker_name}] {err_msg}")
                return False, raw_out, err_msg

            if not is_verified:
                return False, raw_out, f"Verification failed: {verif_reason}"

            return True, raw_out, verif_reason

        # Execution Mode Resolution
        llm_caller = context.get("llm_caller")
        steps = context.get("steps")
        single_tool = context.get("tool")

        # ── Mode A: Autonomous LLM-Driven ReAct Loop ────────────────────────
        if llm_caller is not None:
            for turn in range(self.max_turns):
                if time.time() - start_time > self.time_budget_seconds:
                    errors.append(f"Time budget of {self.time_budget_seconds}s exceeded")
                    break

                # Reason
                try:
                    if inspect.iscoroutinefunction(llm_caller):
                        llm_resp = asyncio.run(llm_caller(self.messages))
                    else:
                        resp = llm_caller(self.messages)
                        llm_resp = asyncio.run(resp) if inspect.iscoroutine(resp) else resp
                except Exception as llm_err:
                    errors.append(f"LLM reasoning error at turn {turn + 1}: {llm_err}")
                    break

                # Parse tool calls vs direct answer
                tool_calls = getattr(llm_resp, "tool_calls", None)
                if not tool_calls and isinstance(llm_resp, dict):
                    tool_calls = llm_resp.get("tool_calls")

                if tool_calls:
                    # Act & Observe & Verify
                    for tc in tool_calls:
                        actions_count += 1
                        tc_name = getattr(tc, "name", None) or (tc.get("name") if isinstance(tc, dict) else str(tc))
                        tc_args = getattr(tc, "args", None) or (tc.get("args") or tc.get("parameters") if isinstance(tc, dict) else {})
                        if isinstance(tc_args, str):
                            import json
                            try:
                                tc_args = json.loads(tc_args)
                            except Exception:
                                tc_args = {}

                        ok, raw_out, detail = _execute_single_action(tc_name, tc_args)
                        target_str = str(tc_args.get("path") or tc_args.get("target") or tc_name)
                        self.working_memory.record_step(
                            capability=tc_name,
                            target=target_str,
                            goal=task,
                            success=ok,
                            observations=[f"{tc_name}: {raw_out}"] if ok else [detail],
                        )
                        self.messages.append({
                            "role": "assistant",
                            "content": f"Action: {tc_name}({tc_args})",
                        })
                        self.messages.append({
                            "role": "tool",
                            "name": tc_name,
                            "content": str(raw_out) if ok else f"Error: {detail}",
                        })
                        if ok:
                            observations.append(f"Turn {turn + 1}: {tc_name} -> {raw_out}")
                        else:
                            errors.append(detail)
                            if "blocked by ExecutionPolicy" in detail or "ExecutionPolicy evaluation error" in detail:
                                verification_status = {"passed": False, "reason": "policy_blocked", "detail": detail}
                                break
                            else:
                                verification_status = {"passed": False, "reason": detail}
                    if any("blocked by ExecutionPolicy" in e or "ExecutionPolicy evaluation error" in e for e in errors):
                        break
                else:
                    # Direct reasoning completion
                    content = getattr(llm_resp, "content", None) or (llm_resp.get("content") if isinstance(llm_resp, dict) else str(llm_resp))
                    observations.append(f"Completed: {content}")
                    self.messages.append({"role": "assistant", "content": content})
                    self.working_memory.mark_complete(success=True, final_observation=content)
                    break

        # ── Mode B: Multi-Step Plan ReAct Execution ─────────────────────────
        elif steps and isinstance(steps, list):
            for step_idx, step in enumerate(steps):
                if time.time() - start_time > self.time_budget_seconds:
                    errors.append(f"Time budget of {self.time_budget_seconds}s exceeded")
                    break
                if step_idx >= self.max_turns:
                    errors.append(f"Turn budget of {self.max_turns} turns exceeded")
                    break

                tool_name = step.get("tool") if isinstance(step, dict) else str(step)
                tool_params = step.get("params", {}) if isinstance(step, dict) else {}
                actions_count += 1

                ok, raw_out, detail = _execute_single_action(tool_name, tool_params)
                target_str = str(tool_params.get("path") or tool_params.get("target") or tool_name)
                self.working_memory.record_step(
                    capability=tool_name,
                    target=target_str,
                    goal=task,
                    success=ok,
                    observations=[f"{tool_name}: {raw_out}"] if ok else [detail],
                )
                self.messages.append({
                    "role": "assistant",
                    "content": f"Step {step_idx + 1}: {tool_name}({tool_params})",
                })
                self.messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "content": str(raw_out) if ok else f"Error: {detail}",
                })

                if ok:
                    observations.append(f"Step {step_idx + 1} ({tool_name}): {raw_out}")
                else:
                    errors.append(detail)
                    if "blocked by ExecutionPolicy" in detail or "ExecutionPolicy evaluation error" in detail:
                        verification_status = {"passed": False, "reason": "policy_blocked", "detail": detail}
                        break
                    else:
                        verification_status = {"passed": False, "reason": detail}

        # ── Mode C: Single Tool Invocation ──────────────────────────────────
        elif single_tool:
            tool_params = context.get("params", {})
            actions_count += 1
            ok, raw_out, detail = _execute_single_action(single_tool, tool_params)
            target_str = str(tool_params.get("path") or tool_params.get("target") or single_tool)
            self.working_memory.record_step(
                capability=single_tool,
                target=target_str,
                goal=task,
                success=ok,
                observations=[f"{single_tool}: {raw_out}"] if ok else [detail],
            )
            self.messages.append({
                "role": "assistant",
                "content": f"Action: {single_tool}({tool_params})",
            })
            self.messages.append({
                "role": "tool",
                "name": single_tool,
                "content": str(raw_out) if ok else f"Error: {detail}",
            })
            if ok:
                observations.append(f"Tool {single_tool} returned: {raw_out}")
            else:
                errors.append(detail)
                if "blocked by ExecutionPolicy" in detail or "ExecutionPolicy evaluation error" in detail:
                    verification_status = {"passed": False, "reason": "policy_blocked", "detail": detail}
                else:
                    verification_status = {"passed": False, "reason": detail}

        # Final evaluation
        duration = time.time() - start_time
        success = len(errors) == 0
        if self.working_memory:
            self.working_memory.mark_complete(success=success)

        result = WorkerResult(
            worker_name=self.worker_name,
            status="SUCCESS" if success else "FAILED",
            task=task,
            actions_taken=actions_count,
            observations=observations,
            verification=verification_status if not success and "reason" in verification_status else {"passed": success},
            artifacts=context.get("expected_artifacts", {}),
            errors=errors,
            duration=duration,
        )
        return sanitize_worker_output(result)


__all__ = [
    "WorkerProfile",
    "ResearchProfile",
    "TestProfile",
    "CodingProfile",
    "BrowserProfile",
    "WorkerResult",
    "TaskWorker",
    "sanitize_worker_output",
]
