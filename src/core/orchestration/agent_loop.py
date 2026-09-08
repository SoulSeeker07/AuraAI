"""
Agent Loop - Active Verified Goal/Step Agent Loop for AuraAI.
Location: src/core/orchestration/agent_loop.py

Implements the 5-stage loop lifecycle:
  Perceive -> Reason -> Act -> Observe -> Verify
with bounded execution, pluggable capability verification, repeated failure guards,
and failure-reason feedback into the LLM context (adaptation loop).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from .agent_session import AgentSession
from .goal_state import Goal, GoalStatus, Step, StepStatus
from .goal_store import GoalStore, MAX_OBSERVATION_LENGTH

logger = logging.getLogger(__name__)


def is_agent_loop_enabled() -> bool:
    """
    Single source of truth for AgentLoop activation.
    Defaults to True (enabled). Opt out by setting AURA_ENABLE_AGENT_LOOP=0.
    """
    return os.environ.get("AURA_ENABLE_AGENT_LOOP", "1").lower() in ("1", "true", "yes")


# ── Pluggable Capability Verifiers ──────────────────────────────────────────


def verify_create_file_artifact(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: dict[str, Any],
) -> tuple[bool, str]:
    """
    Pluggable verifier for 'create_file_artifact'.
    Verifies that the target file exists on disk and has non-zero size.
    """
    if not isinstance(tool_result, dict):
        return False, f"create_file_artifact returned non-dict result: {type(tool_result).__name__}"

    if tool_result.get("status") == "confirmation_required":
        return True, "Confirmation required by user policy"

    if tool_result.get("status") != "success":
        err_msg = tool_result.get("error") or tool_result.get("message") or "Unknown tool execution failure"
        return False, f"Execution failed: {err_msg}"

    output_path = tool_result.get("output_path")
    if not output_path:
        output_filename = tool_args.get("output_filename")
        if output_filename:
            destination = (tool_args.get("destination") or "cwd").lower()
            home = Path.home()
            dest_map = {
                "desktop": home / "Desktop",
                "downloads": home / "Downloads",
                "documents": home / "Documents",
                "cwd": Path.cwd(),
            }
            dest_dir = dest_map.get(destination, Path.cwd())
            output_path = str(dest_dir / output_filename)

    if not output_path:
        return False, "Missing output_path in result and tool arguments"

    p = Path(output_path)
    if not p.is_absolute():
        p = Path.cwd() / p

    if not p.exists():
        return False, f"Artifact file does not exist at expected path '{output_path}'"

    if not p.is_file():
        return False, f"Artifact path is not a regular file: '{output_path}'"

    try:
        size = p.stat().st_size
        if size <= 0:
            return False, f"Artifact file at '{output_path}' is empty (0 bytes)"
        return True, f"File artifact verified on disk ({size} bytes at '{p.name}')"
    except Exception as ex:
        return False, f"Failed reading artifact file stats at '{output_path}': {ex}"


def verify_browser_navigate_and_read(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: dict[str, Any],
) -> tuple[bool, str]:
    """
    Pluggable verifier for 'browser_navigate_and_read'.
    Verifies successful execution and non-empty, substantive extracted web content.
    """
    if not isinstance(tool_result, dict):
        return False, f"browser_navigate_and_read returned non-dict result: {type(tool_result).__name__}"

    if tool_result.get("status") == "confirmation_required":
        return True, "Confirmation required by user policy"

    if tool_result.get("status") != "success":
        err_msg = tool_result.get("error") or "Unknown browser navigation failure"
        return False, f"Navigation failed: {err_msg}"

    url = tool_args.get("url") or tool_result.get("url") or "unknown_url"
    content = tool_result.get("content") or tool_result.get("title")

    if not content or not str(content).strip():
        return False, f"Browser navigation succeeded but extracted content is empty for URL '{url}'"

    content_str = str(content).strip()
    if len(content_str) < 15 and not tool_result.get("title"):
        return False, f"Extracted web content ({len(content_str)} chars) is too brief to be substantive"

    return True, f"Web content verified ({len(content_str)} chars extracted from '{url}')"


def verify_browser_interact(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: dict[str, Any],
) -> tuple[bool, str]:
    """
    Shallow verifier for 'browser_interact'.

    IMPORTANT SCOPE NOTE: This verifier checks dispatch completion, non-empty execution
    result, and argument consistency. It does NOT independently re-query the browser DOM
    or A11Y tree to confirm visual element mutation. True DOM-state verification requires
    an active page handle and is scheduled for Phase 3.
    """
    if not isinstance(tool_result, dict):
        return False, f"browser_interact returned non-dict result: {type(tool_result).__name__}"

    if tool_result.get("status") == "confirmation_required":
        return True, "Confirmation required by user policy"

    if tool_result.get("status") != "success":
        err_msg = tool_result.get("error") or "Unknown browser interaction failure"
        return False, f"Browser interaction failed: {err_msg}"

    expected_action = tool_args.get("action")
    expected_selector = tool_args.get("selector")

    res_action = tool_result.get("action")
    if expected_action and res_action and res_action != expected_action:
        return False, f"Browser action mismatch: expected '{expected_action}', got '{res_action}'"

    res_selector = tool_result.get("selector")
    if expected_selector and res_selector and res_selector != expected_selector:
        return False, f"Browser selector mismatch: expected '{expected_selector}', got '{res_selector}'"

    res_msg = tool_result.get("result") or tool_result.get("message")
    if not res_msg or not str(res_msg).strip():
        return False, f"Browser interaction '{expected_action}' on '{expected_selector}' produced no execution confirmation result"

    return True, f"Browser interaction '{expected_action}' on '{expected_selector}' verified: {res_msg}"


def verify_terminal_run_command(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: dict[str, Any],
) -> tuple[bool, str]:
    """
    Capability verifier for 'terminal_run_command'.
    Verifies process returncode == 0 and detects fatal shell error signatures in stderr.
    """
    if not isinstance(tool_result, dict):
        return False, f"terminal_run_command returned non-dict result: {type(tool_result).__name__}"

    if tool_result.get("status") == "confirmation_required":
        return True, "Confirmation required by user policy"

    if tool_result.get("status") != "success":
        err_msg = tool_result.get("error") or "Unknown terminal execution failure"
        return False, f"Terminal execution failed: {err_msg}"

    # Check returncode if present
    returncode = tool_result.get("returncode")
    if returncode is not None and returncode != 0:
        stderr = (tool_result.get("stderr") or "").strip()
        return False, f"Command exited with non-zero returncode {returncode}: {stderr[:300]}"

    # Check stderr patterns for fatal failures even if returncode was 0 or unrecorded
    stderr = (tool_result.get("stderr") or "").strip().lower()
    stdout = (tool_result.get("stdout") or tool_result.get("result") or "").strip().lower()
    fatal_patterns = [
        "syntaxerror:",
        "command not found",
        "is not recognized as an internal or external command",
        "permission denied",
        "fatal: not a git repository",
        "traceback (most recent call last):",
    ]
    for pat in fatal_patterns:
        if pat in stderr or (pat in stdout and "error" in stdout and len(stdout) < 500):
            return False, f"Terminal output contains fatal error signature: '{pat}'"

    cmd = (tool_args.get("command") or "")[:50]
    return True, f"Terminal command '{cmd}' executed successfully (code {returncode or 0})"


def verify_edit_file(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: dict[str, Any],
) -> tuple[bool, str]:
    """
    Capability verifier for 'edit_file'.
    Verifies file presence and parses Python AST for .py files to ensure no syntax errors were introduced.
    """
    import ast

    if not isinstance(tool_result, dict):
        return False, f"edit_file returned non-dict result: {type(tool_result).__name__}"

    if tool_result.get("status") == "confirmation_required":
        return True, "Confirmation required by user policy"

    if tool_result.get("status") != "success":
        err_msg = tool_result.get("error") or "Unknown file edit failure"
        return False, f"File edit failed: {err_msg}"

    target_path_str = tool_args.get("path") or tool_result.get("path")
    if not target_path_str:
        return True, "File edit completed (path not provided in arguments)"

    target_path = Path(target_path_str)
    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path

    if not target_path.exists():
        return False, f"Edited file does not exist at '{target_path_str}'"

    # For Python source files, perform AST validation
    if target_path.suffix.lower() == ".py":
        try:
            source_code = target_path.read_text(encoding="utf-8", errors="replace")
            ast.parse(source_code, filename=str(target_path))
        except SyntaxError as syn_err:
            return False, f"AST SyntaxError in edited file '{target_path.name}' at line {syn_err.lineno}: {syn_err.msg}"
        except Exception as parse_err:
            return False, f"AST validation failed on '{target_path.name}': {parse_err}"

    return True, f"File edit verified for '{target_path.name}'"


VERIFIER_REGISTRY: dict[str, Callable[[str, dict[str, Any], dict[str, Any]], tuple[bool, str]]] = {
    "create_file_artifact": verify_create_file_artifact,
    "browser_navigate_and_read": verify_browser_navigate_and_read,
    "browser_interact": verify_browser_interact,
    "terminal_run_command": verify_terminal_run_command,
    "edit_file": verify_edit_file,
}


# ── Active Agent Loop ────────────────────────────────────────────────────────


class AgentLoop:
    """
    Active Verified Agent Loop executing the Perceive -> Reason -> Act -> Observe -> Verify state machine.
    """

    def __init__(
        self,
        aura_core: Any = None,
        goal_store: Optional[GoalStore] = None,
        emitter: Any = None,
        session_id: Optional[str] = None,
        max_steps: int = 8,
        dispatcher: Any = None,
        llm_caller: Optional[Callable[[dict[str, Any]], Awaitable[Any]]] = None,
    ) -> None:
        self.aura_core = aura_core
        self.goal_store = goal_store
        self.emitter = emitter
        self.session_id = session_id or "sess_ephemeral"
        self.max_steps = max_steps
        self.dispatcher = dispatcher
        self.llm_caller = llm_caller

    def verify(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: Any,
    ) -> tuple[bool, str]:
        """
        Execute capability-specific verification.
        Returns (is_verified: bool, reason: str).
        """
        if tool_name in VERIFIER_REGISTRY:
            return VERIFIER_REGISTRY[tool_name](tool_name, tool_args, tool_result)

        if isinstance(tool_result, dict):
            if tool_result.get("status") == "confirmation_required":
                return True, "Confirmation required by user policy"
            if tool_result.get("status") == "error":
                return False, tool_result.get("error") or "Tool returned status: error"

        return True, "No capability-specific verification required"

    def _resolve_goal(self, user_message: str) -> Goal:
        """
        Perceive phase: check if existing goal in session is in AWAITING_USER.
        If so, resumes it. Otherwise, persists a new Goal.
        """
        if self.goal_store is not None:
            try:
                existing_goals = self.goal_store.list_goals_for_session(self.session_id)
                if existing_goals:
                    last_goal = existing_goals[-1]
                    if last_goal.status == GoalStatus.AWAITING_USER:
                        logger.info(
                            f"[AgentLoop] Resuming goal [{last_goal.goal_id}] from AWAITING_USER to ACTIVE"
                        )
                        self.goal_store.update_goal_status(last_goal.goal_id, GoalStatus.ACTIVE)
                        last_goal.status = GoalStatus.ACTIVE
                        return last_goal

                new_goal = Goal.new(
                    session_id=self.session_id,
                    user_prompt=user_message,
                    max_steps=self.max_steps,
                )
                self.goal_store.create_goal(new_goal)
                return new_goal
            except Exception as ge:
                logger.warning(f"[AgentLoop] Goal store resolve failed: {ge}")

        return Goal.new(
            session_id=self.session_id,
            user_prompt=user_message,
            max_steps=self.max_steps,
        )

    async def run(
        self,
        user_message: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
        target_model: str = "openai/gpt-oss-120b",
        tools: Optional[list[dict[str, Any]]] = None,
        call_groq_streaming: Optional[Callable] = None,
        call_groq: Optional[Callable] = None,
    ) -> str:
        """
        Executes the active bounded agent loop.
        """
        goal = self._resolve_goal(user_message)
        logger.info(
            f"[AgentLoop] Starting goal [{goal.goal_id}] (session: {self.session_id}, max_steps: {goal.max_steps})"
        )

        # Invariant: Goal-scoped AgentSession instance constructed locally.
        # MUST NEVER read from, write to, or alias MasterOrchestrator._last_session.
        session = AgentSession(goal=user_message, session_id=self.session_id, goal_id=goal.goal_id)

        final_text = ""
        consecutive_failures: list[tuple[str, str]] = []
        accumulated_reasoning: list[str] = []

        for iteration in range(goal.max_steps):
            turn_label = f"Turn {iteration + 1}: Reasoning"
            turn_start = time.time()

            if self.emitter is not None:
                from core.progress_events import EventStatus, EventType, ProgressEvent
                self.emitter.emit(
                    ProgressEvent(
                        label=turn_label,
                        event_type=EventType.REACT_TURN,
                        status=EventStatus.STARTED,
                    )
                )

            # ── 1. Reason ───────────────────────────────────────────────────
            response_msg = None
            try:
                if self.llm_caller is not None:
                    res = await self.llm_caller(kwargs)
                elif call_groq_streaming is not None:
                    on_thought = (lambda tok: self.emitter.thinking(tok)) if self.emitter is not None else None
                    on_gen = (lambda tok: self.emitter.generating(tok)) if self.emitter is not None else None
                    try:
                        res = await asyncio.to_thread(
                            call_groq_streaming, kwargs, target_model, on_thought, on_gen
                        )
                    except Exception as call_err:
                        logger.warning(f"[AgentLoop] Streaming failed ({call_err}), falling back to sync")
                        if call_groq is not None:
                            res = await asyncio.to_thread(call_groq, kwargs, "qwen/qwen3.6-27b")
                        else:
                            raise
                elif call_groq is not None:
                    res = await asyncio.to_thread(call_groq, kwargs, target_model)
                else:
                    raise RuntimeError("No LLM caller or Groq function provided to AgentLoop")

                if res and hasattr(res, "choices") and res.choices and res.choices[0].message:
                    response_msg = res.choices[0].message
                    r_chunk = getattr(response_msg, "reasoning", None)
                    if r_chunk and isinstance(r_chunk, str) and r_chunk.strip():
                        accumulated_reasoning.append(r_chunk.strip())

            except Exception as llm_err:
                logger.error(f"[AgentLoop] LLM reasoning error at turn {iteration + 1}: {llm_err}", exc_info=True)
                # Attempt seamless recovery via Gemini provider before failing turn (only on default Groq caller path)
                gemini_turn = None
                if self.llm_caller is None:
                    gemini_turn = self._try_gemini_fallback(kwargs)
                if gemini_turn is not None:
                    logger.info(f"[AgentLoop] Seamlessly recovered turn {iteration + 1} via Gemini fallback.")
                    response_msg = gemini_turn
                else:
                    if self.emitter is not None:
                        from core.progress_events import EventStatus, EventType, ProgressEvent
                        self.emitter.emit(
                            ProgressEvent(
                                label=turn_label,
                                event_type=EventType.REACT_TURN,
                                status=EventStatus.ERROR,
                                detail=str(llm_err),
                                duration_ms=(time.time() - turn_start) * 1000,
                            )
                        )
                    if self.goal_store is not None:
                        self.goal_store.update_goal_status(goal.goal_id, GoalStatus.FAILED)
                    final_text = f"I encountered an error communicating with the reasoning model: {llm_err}"
                    break

            if response_msg is None:
                final_text = "I was unable to generate a response from the reasoning engine."
                break

            if self.emitter is not None:
                from core.progress_events import EventStatus, EventType, ProgressEvent
                self.emitter.emit(
                    ProgressEvent(
                        label=turn_label,
                        event_type=EventType.REACT_TURN,
                        status=EventStatus.DONE,
                        duration_ms=(time.time() - turn_start) * 1000,
                    )
                )

            # ── 2. Check for Tool Calls vs Final Answer ─────────────────────
            tool_calls = getattr(response_msg, "tool_calls", None)
            if not tool_calls:
                # Direct reasoning / final answer reached!
                content_text = getattr(response_msg, "content", None) or "Action completed."
                all_reasoning = "\n\n".join(accumulated_reasoning).strip()
                if all_reasoning and "<think>" not in content_text:
                    final_text = f"<think>\n{all_reasoning}\n</think>\n\n{content_text}"
                else:
                    final_text = content_text

                if self.goal_store is not None:
                    try:
                        reasoning_step = Step.new(
                            goal_id=goal.goal_id,
                            tool_name=None,
                            tool_args={},
                            status=StepStatus.VERIFIED,
                            observation=final_text,
                            verify_reason="Direct response generated",
                        )
                        self.goal_store.add_step(reasoning_step)
                        self.goal_store.update_goal_status(goal.goal_id, GoalStatus.DONE)
                    except Exception as se:
                        logger.debug(f"[AgentLoop] Reasoning step persistence error: {se}")
                return self._finalize_text(final_text, user_message, goal=goal)

            # Record assistant turn with tool calls into messages
            if isinstance(response_msg, dict):
                messages.append(response_msg)
            else:
                messages.append({
                    "role": "assistant",
                    "content": getattr(response_msg, "content", None),
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

            # If model provided thought/plan content prior to tool execution, record it as a planning step
            pre_tool_thought = getattr(response_msg, "content", None) or getattr(response_msg, "reasoning", None)
            if pre_tool_thought:
                if self.emitter is not None:
                    try:
                        self.emitter.plan("Plan-Before-Act", detail=pre_tool_thought[:200])
                    except Exception:
                        pass
                if self.goal_store is not None:
                    try:
                        plan_step = Step.new(
                            goal_id=goal.goal_id,
                            tool_name=None,
                            tool_args={},
                            status=StepStatus.VERIFIED,
                            observation=pre_tool_thought,
                            verify_reason="Plan-Before-Act deliberation",
                        )
                        self.goal_store.add_step(plan_step)
                    except Exception as se:
                        logger.debug(f"[AgentLoop] Plan step persistence error: {se}")

            # ── 3. Act, Observe, Verify for each requested tool ─────────────
            turn_confirmation_required = False

            for tool_call in tool_calls:
                fn_name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                try:
                    fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    fn_args = {}

                args_signature = json.dumps(fn_args, sort_keys=True, default=str)
                call_sig = (fn_name, args_signature)

                # Repeated Failure Guard
                if len(consecutive_failures) >= 2 and consecutive_failures[-1] == call_sig and consecutive_failures[-2] == call_sig:
                    logger.warning(
                        f"[AgentLoop] Repeated failure guard triggered for {fn_name}. Halting and requesting user guidance."
                    )
                    if self.goal_store is not None:
                        self.goal_store.update_goal_status(goal.goal_id, GoalStatus.AWAITING_USER)
                    final_text = (
                        f"Action '{fn_name}' has repeatedly failed verification with identical arguments. "
                        "I am pausing execution for your clarification before proceeding."
                    )
                    return self._finalize_text(final_text, user_message, goal=goal)

                step_rec = None
                if self.goal_store is not None:
                    try:
                        step_rec = Step.new(
                            goal_id=goal.goal_id,
                            tool_name=fn_name,
                            tool_args=fn_args,
                            status=StepStatus.IN_PROGRESS,
                        )
                        self.goal_store.add_step(step_rec)
                    except Exception as se:
                        logger.debug(f"[AgentLoop] Step init persistence error: {se}")

                tool_label = f"Turn {iteration + 1}: calling {fn_name}"
                tool_start = time.time()
                if self.emitter is not None:
                    from core.progress_events import EventStatus, EventType, ProgressEvent
                    self.emitter.emit(
                        ProgressEvent(
                            label=tool_label,
                            event_type=EventType.TOOL_CALL,
                            status=EventStatus.STARTED,
                            detail=json.dumps(fn_args),
                        )
                    )

                # Act: Dispatch
                dispatcher = self.dispatcher
                if dispatcher is None:
                    from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher
                    dispatcher = UnifiedToolDispatcher

                try:
                    tool_result = await dispatcher.dispatch(
                        fn_name, fn_args, session=session, aura_core=self.aura_core, emitter=self.emitter
                    )
                    if self.emitter is not None:
                        from core.progress_events import EventStatus, EventType, ProgressEvent
                        self.emitter.emit(
                            ProgressEvent(
                                label=f"Turn {iteration + 1}: {fn_name} done",
                                event_type=EventType.TOOL_CALL,
                                status=EventStatus.DONE,
                                duration_ms=(time.time() - tool_start) * 1000,
                            )
                        )
                except Exception as tool_err:
                    logger.error(f"[AgentLoop] Dispatch error for {fn_name}: {tool_err}", exc_info=True)
                    tool_result = {"status": "error", "error": str(tool_err)}
                    if self.emitter is not None:
                        from core.progress_events import EventStatus, EventType, ProgressEvent
                        self.emitter.emit(
                            ProgressEvent(
                                label=f"Turn {iteration + 1}: {fn_name} error",
                                event_type=EventType.TOOL_CALL,
                                status=EventStatus.ERROR,
                                detail=str(tool_err),
                                duration_ms=(time.time() - tool_start) * 1000,
                            )
                        )

                # Observe: Record raw output & truncate safely for persistence
                raw_observation = str(tool_result.get("result") or tool_result.get("error") or tool_result)
                stored_observation = raw_observation[:MAX_OBSERVATION_LENGTH]

                # Confirmation Gate handling
                if isinstance(tool_result, dict) and tool_result.get("status") == "confirmation_required":
                    if self.goal_store is not None:
                        self.goal_store.update_goal_status(goal.goal_id, GoalStatus.AWAITING_USER)
                    if step_rec and self.goal_store is not None:
                        self.goal_store.update_step_status(
                            step_id=step_rec.step_id,
                            status=StepStatus.OBSERVED,
                            observation=stored_observation,
                            verify_reason="Confirmation ticket pending user approval",
                        )
                    ticket_id = tool_result.get("ticket_id") or "pending"
                    turn_confirmation_required = True
                    final_text = (
                        tool_result.get("prompt")
                        or (
                            f"Action '{fn_name}' requires your confirmation before proceeding.\n"
                            f"Confirmation Ticket: {ticket_id}\n"
                            f"Details: {tool_result.get('message') or 'High risk action gated.'}"
                        )
                    )
                    break

                # Verify: Run capability-specific verification
                is_verified, verify_reason = self.verify(fn_name, fn_args, tool_result)
                step_status = StepStatus.VERIFIED if is_verified else StepStatus.FAILED

                if step_rec and self.goal_store is not None:
                    try:
                        self.goal_store.update_step_status(
                            step_id=step_rec.step_id,
                            status=step_status,
                            observation=stored_observation,
                            verify_reason=verify_reason,
                        )
                    except Exception as ue:
                        logger.debug(f"[AgentLoop] Step update persistence error: {ue}")

                if is_verified:
                    consecutive_failures.clear()
                    feedback_content = tool_result
                else:
                    consecutive_failures.append(call_sig)
                    feedback_content = {
                        "status": "failed_verification",
                        "error": verify_reason,
                        "guidance": "The previous tool output failed capability verification. Please inspect the error and adjust your arguments or plan.",
                        "raw_result": tool_result,
                    }

                # Append tool result / feedback to conversation messages for next reasoning turn
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": json.dumps(feedback_content, default=str),
                })

            if turn_confirmation_required:
                return self._finalize_text(final_text, user_message, goal=goal)

            kwargs["messages"] = messages

        # If loop exited because bounded iterations were exhausted
        if not final_text:
            if self.goal_store is not None:
                self.goal_store.update_goal_status(goal.goal_id, GoalStatus.FAILED)
            steps_summary = []
            if self.goal_store is not None:
                steps = self.goal_store.get_steps_for_goal(goal.goal_id)
                for s in steps:
                    status_val = s.status.value if hasattr(s.status, "value") else str(s.status)
                    reason_info = f" ({s.verify_reason})" if s.verify_reason else ""
                    steps_summary.append(f"- Step {s.tool_name or 'reasoning'}: {status_val}{reason_info}")

            summary_str = "\n".join(steps_summary) if steps_summary else "No steps completed."
            final_text = (
                f"Goal execution reached maximum bounded iterations ({goal.max_steps}) without successful verification.\n"
                f"Attempt history:\n{summary_str}"
            )

        all_reasoning = "\n\n".join(accumulated_reasoning).strip()
        if all_reasoning and "<think>" not in final_text:
            final_text = f"<think>\n{all_reasoning}\n</think>\n\n{final_text}"

        return self._finalize_text(final_text, user_message, goal=goal)

    def _finalize_text(self, text: str, user_message: str, goal: Optional[Goal] = None) -> str:
        """Teardown completed browser sessions, record cleaned text in history, and return rendered text for UI."""
        if goal is not None:
            try:
                from browser.browser_session_manager import BrowserSessionManager
                if goal.status in (GoalStatus.DONE, GoalStatus.FAILED):
                    BrowserSessionManager.get_instance().close_session(goal.goal_id, reason="completed")
            except Exception as b_err:
                logger.debug(f"[AgentLoop] Browser session close error: {b_err}")

        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE).strip()

        if self.aura_core is not None:
            try:
                self.aura_core.add_to_conversation("user", user_message)
                self.aura_core.add_to_conversation("assistant", cleaned)
                if hasattr(self.aura_core, "_focus_postamble"):
                    text = self.aura_core._focus_postamble(user_message, text)
            except Exception as ce:
                logger.debug(f"[AgentLoop] Core conversation update error: {ce}")

        return text

    def _try_gemini_fallback(self, kwargs: dict[str, Any]) -> Optional[Any]:
        """Attempt seamless recovery via Gemini provider when primary Groq LLM fails."""
        try:
            from ai.key_pool import KeyPool
            pool = KeyPool.get_instance()
            if not pool.get_all_keys("gemini"):
                return None
            from ai.gemini_provider import GeminiProvider
            from ai.models import ChatMessage, ChatRequest
            from types import SimpleNamespace
            gp = GeminiProvider(default_model=os.environ.get("AURA_GEMINI_MODEL", "gemini-3.5-flash"))
            chat_msgs = []
            for m in kwargs.get("messages", []):
                r = m.get("role", "user") if isinstance(m, dict) else getattr(m, "role", "user")
                c = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
                if r in ("system", "user", "assistant") and c:
                    chat_msgs.append(ChatMessage(role=r, content=c))
            resp = gp.chat(ChatRequest(messages=chat_msgs, max_tokens=4096, temperature=0.5))
            if resp and resp.text:
                return SimpleNamespace(
                    role="assistant",
                    content=resp.text.strip(),
                    reasoning=None,
                    tool_calls=None,
                )
        except Exception as ge:
            logger.warning(f"[AgentLoop] Gemini fallback failed: {ge}")
        return None
