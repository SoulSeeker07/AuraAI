"""
Unit tests for Antigravity-Style Subagent Isolated Multi-Turn ReAct Loop (Piece 3).
Location: tests/unit/test_subagent_react_loop.py

Tests:
1. Context isolation: worker.messages and TaskWorkingMemory remain strictly private.
2. Multi-turn LLM ReAct execution (Perceive -> Reason -> Act -> Observe -> Verify).
3. Multi-step plan execution with tool tracking.
4. Gate 2 ExecutionPolicy defense-in-depth halts closed on mid-flight unauthorized mutation.
5. Pluggable capability verification failures caught and reported.
6. Turn budget bounding (max_turns).
7. Time budget bounding (time_budget_seconds).
8. End-to-end secret redaction preservation in multi-turn results.
"""

import asyncio
import time
from typing import Any
import pytest

from core.orchestration.task_worker import (
    TaskWorker,
    WorkerProfile,
    WorkerResult,
    CodingProfile,
    TestProfile,
    ResearchProfile,
)
from core.orchestration.task_working_memory import TaskWorkingMemory


def test_subagent_react_loop_context_isolation():
    """
    Verify that TaskWorker maintains its own private messages array and
    TaskWorkingMemory without polluting global or session state.
    """
    worker = TaskWorker(worker_name="isolation_worker", profile=ResearchProfile)

    def mock_tool(name: str, params: dict):
        return "Discovered 5 references in docs/"

    res = worker.execute_task(
        task="Audit documentation coverage",
        context={"tool": "doc.query", "params": {"topic": "architecture"}},
        coordinator_callback=mock_tool,
    )

    assert res.status == "SUCCESS"
    assert len(worker.messages) >= 3  # system, user, assistant/tool
    assert worker.messages[0]["role"] == "system"
    assert "ResearchProfile" in worker.messages[0]["content"]
    assert worker.messages[1]["role"] == "user"

    # Verify working memory is populated
    assert worker.working_memory is not None
    assert isinstance(worker.working_memory, TaskWorkingMemory)
    assert worker.working_memory.goal == "Audit documentation coverage"
    assert worker.working_memory.step_count == 1
    assert worker.working_memory.completed_actions[0].capability == "doc.query"
    assert worker.working_memory.completed_actions[0].success is True


def test_subagent_react_loop_multi_turn_llm_execution():
    """
    Verify autonomous multi-turn ReAct loop driven by an isolated LLM caller:
    Turn 1: Proposes tool call (code.analyze).
    Turn 2: Receives observation and generates final completion text.
    """
    worker = TaskWorker(worker_name="llm_react_worker", profile=CodingProfile, max_turns=5)

    turn_counter = 0

    class MockToolCall:
        def __init__(self, name: str, args: dict):
            self.name = name
            self.args = args

    class MockLLMResponse:
        def __init__(self, tool_calls=None, content=None):
            self.tool_calls = tool_calls
            self.content = content

    def mock_llm_caller(messages: list[dict[str, Any]]):
        nonlocal turn_counter
        turn_counter += 1
        if turn_counter == 1:
            # Turn 1: request code analysis
            return MockLLMResponse(
                tool_calls=[MockToolCall("code.analyze", {"path": "src/core"})]
            )
        else:
            # Turn 2: inspect observations and finish
            return MockLLMResponse(content="Codebase structure verified clean.")

    def mock_coordinator(name: str, params: dict):
        return "src/core contains 15 modules with valid imports"

    res = worker.execute_task(
        task="Analyze core module structure",
        context={"llm_caller": mock_llm_caller},
        coordinator_callback=mock_coordinator,
    )

    assert res.status == "SUCCESS"
    assert res.actions_taken == 1
    assert any("Codebase structure verified clean" in obs for obs in res.observations)
    assert worker.working_memory.step_count == 1
    assert worker.working_memory.is_complete is True


def test_subagent_react_loop_multi_step_plan_execution():
    """
    Verify multi-step plan execution across multiple tools within worker profile boundaries.
    """
    worker = TaskWorker(worker_name="plan_worker", profile=CodingProfile)
    executed_tools = []

    def mock_coordinator(name: str, params: dict):
        executed_tools.append((name, params))
        return f"Result of {name}"

    res = worker.execute_task(
        task="Refactor and test parsing utilities",
        context={
            "steps": [
                {"tool": "code.analyze", "params": {"target": "parser.py"}},
                {"tool": "ast.inspect", "params": {"node": "ParserClass"}},
            ]
        },
        coordinator_callback=mock_coordinator,
    )

    assert res.status == "SUCCESS"
    assert res.actions_taken == 2
    assert len(executed_tools) == 2
    assert executed_tools[0][0] == "code.analyze"
    assert executed_tools[1][0] == "ast.inspect"
    assert worker.working_memory.step_count == 2


def test_subagent_react_loop_gate2_blocks_mid_flight_mutation():
    """
    Verify Gate 2 Defense-in-Depth: If a multi-step sequence attempts a confirmation-gated
    HIGH-risk mutation mid-flight, TaskWorker halts closed and rejects execution.
    """
    profile = WorkerProfile(
        profile_name="AuditProfile",
        allowed_tools=["code.analyze", "file.delete"],
    )
    worker = TaskWorker(worker_name="security_audit_worker", profile=profile)

    executed_tools = []

    def mock_coordinator(name: str, params: dict):
        executed_tools.append(name)
        return "Executed"

    res = worker.execute_task(
        task="Analyze and delete temp directory",
        context={
            "steps": [
                {"tool": "code.analyze", "params": {"path": "src/"}},
                {"tool": "file.delete", "params": {"path": "C:/ImportantData"}},
            ]
        },
        coordinator_callback=mock_coordinator,
    )

    assert res.status == "FAILED"
    # Step 1 was executed, Step 2 was BLOCKED before execution
    assert executed_tools == ["code.analyze"]
    assert any("blocked by ExecutionPolicy" in err for err in res.errors)
    assert res.verification.get("reason") == "policy_blocked"


def test_subagent_react_loop_verification_failure_caught():
    """
    Verify pluggable capability verifiers (VERIFIER_REGISTRY):
    If a terminal command outputs a fatal error pattern, verification fails.
    """
    terminal_profile = WorkerProfile(
        profile_name="TerminalTestProfile",
        allowed_tools=["terminal_run_command"],
    )
    worker = TaskWorker(worker_name="verify_worker", profile=terminal_profile)

    def failing_terminal_command(name: str, params: dict):
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "fatal: not a git repository (or any of the parent directories)",
            "status": "error",
        }

    res = worker.execute_task(
        task="Check git log",
        context={
            "steps": [
                {"tool": "terminal_run_command", "params": {"command": "git status"}}
            ]
        },
        coordinator_callback=failing_terminal_command,
    )

    assert res.status == "FAILED"
    assert res.verification.get("passed") is False
    assert "Verification failed" in res.errors[0]


def test_subagent_react_loop_turn_bounding():
    """
    Verify max_turns budget bounding prevents infinite turn loops.
    """
    worker = TaskWorker(worker_name="budget_worker", profile=ResearchProfile, max_turns=2)

    res = worker.execute_task(
        task="Exhaustive search",
        context={
            "steps": [
                {"tool": "web.search", "params": {"q": "turn 1"}},
                {"tool": "web.search", "params": {"q": "turn 2"}},
                {"tool": "web.search", "params": {"q": "turn 3"}},
            ]
        },
        coordinator_callback=lambda name, params: "Search hit",
    )

    assert res.status == "FAILED"
    assert any("Turn budget of 2 turns exceeded" in err for err in res.errors)
    assert res.actions_taken == 2


def test_subagent_react_loop_time_bounding():
    """
    Verify time_budget_seconds bounds runaway worker execution.
    """
    worker = TaskWorker(worker_name="timeout_worker", profile=ResearchProfile, time_budget_seconds=0.08)

    def slow_tool(name: str, params: dict):
        time.sleep(0.12)
        return "Done"

    res = worker.execute_task(
        task="Slow web fetch",
        context={
            "steps": [
                {"tool": "web.search", "params": {"q": "query 1"}},
                {"tool": "web.search", "params": {"q": "query 2"}},
            ]
        },
        coordinator_callback=slow_tool,
    )

    assert res.status == "FAILED"
    assert any("Time budget" in err for err in res.errors)


def test_subagent_react_loop_redaction_preservation():
    """
    Verify that credentials generated or received during multi-turn ReAct steps
    are fully redacted in WorkerResult observations and to_dict().
    """
    worker = TaskWorker(worker_name="redaction_worker", profile=CodingProfile)

    def secret_generator(name: str, params: dict):
        return "Extracted provider token gsk_secret1234567890abcdef1234567890 and AWS AKIAIOSFODNN7EXAMPLE"

    res = worker.execute_task(
        task="Read credentials file",
        context={"tool": "code.analyze", "params": {}},
        coordinator_callback=secret_generator,
    )

    assert res.status == "SUCCESS"
    assert "gsk_secret" not in str(res.observations)
    assert "AKIAIOSFODNN7EXAMPLE" not in str(res.observations)
    assert "[REDACTED_API_KEY]" in str(res.observations)

    dict_out = res.to_dict()
    assert "gsk_secret" not in str(dict_out)
    assert "AKIAIOSFODNN7EXAMPLE" not in str(dict_out)


def test_subagent_react_loop_gate2_fails_closed_on_policy_exception():
    """
    Verify Gate 2 fails closed if ExecutionPolicy throws an unexpected exception.
    The tool callback must NOT be invoked, and the subagent must record FAILED.
    """
    from unittest.mock import patch, MagicMock

    worker = TaskWorker(worker_name="fail_closed_worker", profile=CodingProfile)
    tool_executed = False

    def mock_coordinator(name: str, params: dict):
        nonlocal tool_executed
        tool_executed = True
        return "Executed"

    mock_policy = MagicMock()
    mock_policy.evaluate_action.side_effect = RuntimeError("Policy engine corrupted or unregistered engine")

    with patch("core.orchestration.execution_policy.ExecutionPolicy.get_instance", return_value=mock_policy):
        res = worker.execute_task(
            task="Perform code edit",
            context={"tool": "code.edit", "params": {"file": "critical.py"}},
            coordinator_callback=mock_coordinator,
        )

    assert not tool_executed, "Security breach: tool was executed despite ExecutionPolicy exception!"
    assert res.status == "FAILED"
    assert res.verification.get("passed") is False
    assert res.verification.get("reason") == "policy_blocked"
    assert any("ExecutionPolicy evaluation error" in err for err in res.errors)


def test_subagent_react_loop_verifier_fails_closed_on_exception():
    """
    Verify that if a capability verifier crashes/raises an exception,
    verification fails closed and the worker is marked FAILED.
    """
    from unittest.mock import patch
    from core.orchestration.agent_loop import VERIFIER_REGISTRY

    profile = WorkerProfile(
        profile_name="CrashVerifierProfile",
        allowed_tools=["mock.crashing_tool"],
    )
    worker = TaskWorker(worker_name="verifier_crash_worker", profile=profile)

    def crashing_verifier(tool_name: str, tool_params: dict, payload: Any):
        raise RuntimeError("Verifier internal panic")

    with patch.dict(VERIFIER_REGISTRY, {"mock.crashing_tool": crashing_verifier}):
        res = worker.execute_task(
            task="Test verifier crash",
            context={"tool": "mock.crashing_tool", "params": {}},
            coordinator_callback=lambda name, params: "Tool output",
        )

    assert res.status == "FAILED"
    assert res.verification.get("passed") is False
    assert any("Verifier execution error" in err for err in res.errors)