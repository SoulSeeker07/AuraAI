"""
Unit tests for Antigravity-Style Subagent Non-Blocking Background Dispatch.
Location: tests/unit/test_subagent_dispatch.py
"""

import asyncio
import time
from typing import Any
import pytest

from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.worker_manager import WorkerManager
from core.orchestration.task_worker import CodingProfile, ResearchProfile, WorkerResult


@pytest.mark.asyncio
async def test_subagent_background_dispatch_returns_promptly():
    """
    Falsifiable test: Dispatch must be non-blocking and return in less than 50ms.
    """
    orchestrator = MasterOrchestrator.get_instance()
    
    def slow_tool(tool_name: str, params: dict):
        time.sleep(0.1)
        return "tool result"

    t0 = time.perf_counter()
    ack = orchestrator.dispatch_background_subagent(
        task_description="Analyze capability usage in codebase",
        profile="coding",
        context={"tool": "code.analyze", "params": {}},
        coordinator_callback=slow_tool,
    )
    elapsed_seconds = time.perf_counter() - t0
    elapsed_ms = elapsed_seconds * 1000

    print(f"\n[PROFILE] Subagent dispatch elapsed latency: {elapsed_ms:.2f}ms")
    assert elapsed_seconds < 0.05, f"Dispatch took {elapsed_ms:.2f}ms, expected under 50ms"

    assert ack["status"] == "DISPATCHED"
    assert "worker_id" in ack
    assert "worker_name" in ack
    assert "task" in ack
    assert isinstance(ack["task"], asyncio.Task)
    assert "You can continue chatting" in ack["message"]

    await ack["task"]


@pytest.mark.asyncio
async def test_subagent_registered_in_worker_manager():
    """
    Verify live registration and telemetry in WorkerManager.
    """
    orchestrator = MasterOrchestrator.get_instance()
    wm = WorkerManager.get_instance()

    ack = orchestrator.dispatch_background_subagent(
        task_description="Collect system diagnostics",
        profile="research",
    )

    worker_id = ack["worker_id"]
    registered = wm.get_worker(worker_id)

    assert registered is not None, f"Worker {worker_id} was not found in WorkerManager"
    assert registered.worker_id == worker_id
    assert registered.domain == "research"
    assert registered.status in ("RUNNING", "COMPLETED")

    res = await ack["task"]
    assert res.status == "SUCCESS"
    assert registered.status == "COMPLETED"
    assert registered.progress == 100


@pytest.mark.asyncio
async def test_subagent_cancellation():
    """
    Verify WorkerManager.cancel_worker cancels background subagent task cleanly.
    """
    orchestrator = MasterOrchestrator.get_instance()
    wm = WorkerManager.get_instance()

    def very_slow_tool(tool_name: str, params: dict):
        time.sleep(0.5)
        return "slow"

    ack = orchestrator.dispatch_background_subagent(
        task_description="Long running background operation",
        profile="test",
        context={"tool": "pytest"},
        coordinator_callback=very_slow_tool,
    )

    worker_id = ack["worker_id"]
    worker = wm.get_worker(worker_id)
    assert worker is not None

    cancelled = wm.cancel_worker(worker_id)
    assert cancelled is True

    try:
        await ack["task"]
    except asyncio.CancelledError:
        pass

    assert worker.status == "CANCELLED"


@pytest.mark.asyncio
async def test_process_request_async_fast_path():
    """
    Verify process_request_async returns instant ExecutionResult for background goals.
    """
    orchestrator = MasterOrchestrator.get_instance()

    t0 = time.perf_counter()
    result = await orchestrator.process_request_async(
        goal_text="run in background: verify security policies",
        parameters={"background": True, "profile": "test"},
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\n[PROFILE] process_request_async background return latency: {elapsed_ms:.2f}ms")
    assert elapsed_ms < 50.0, f"Expected under 50ms, got {elapsed_ms:.2f}ms"
    assert result.success is True
    assert result.planner == "subagent_dispatcher"
    assert "worker_id" in result.data
    assert len(result.observations) > 0
    assert "You can continue chatting" in result.observations[0]

    if result.data.get("task"):
        await result.data["task"]


@pytest.mark.asyncio
async def test_background_dispatch_respects_execution_policy():
    """
    Governance test: Background subagents must NEVER bypass ExecutionPolicy confirmation gates.
    Destructive actions (e.g. file deletion, database drop) must be rejected immediately at dispatch.
    """
    orchestrator = MasterOrchestrator.get_instance()

    # 1. Attempt dispatching a HIGH-risk destructive task directly
    ack = orchestrator.dispatch_background_subagent(
        task_description="delete all files in production repository",
        profile="coding",
        context={"tool": "file.delete", "params": {"target": "D:/Sreekanta/Production/Database.db"}},
    )

    assert ack["status"] == "REJECTED_POLICY"
    assert ack["task"] is None
    assert "requires user confirmation" in ack["error"]
    assert "Background subagents cannot execute confirmation-gated operations" in ack["message"]

    # 2. Attempt via process_request_async fast-path
    result = await orchestrator.process_request_async(
        goal_text="run in background: delete database tables",
        parameters={"background": True, "profile": "coding"},
    )

    assert result.success is False
    assert result.planner == "subagent_dispatcher"
    assert "requires user confirmation" in (result.error or "")


@pytest.mark.asyncio
async def test_task_worker_blocks_unauthorized_high_risk_tool():
    """
    Defense-in-depth: Even if a TaskWorker instance receives a tool call carrying HIGH risk,
    TaskWorker.execute_task evaluates ExecutionPolicy and halts with a policy rejection.
    """
    from core.orchestration.task_worker import TaskWorker, WorkerProfile

    dangerous_profile = WorkerProfile(
        profile_name="DangerousProfile",
        allowed_tools=["file.delete"],
    )
    worker = TaskWorker(worker_name="rogue_worker", profile=dangerous_profile)

    called = False

    def rogue_callback(tool: str, params: dict):
        nonlocal called
        called = True
        return "deleted"

    res = worker.execute_task(
        task="Delete important directory",
        context={"tool": "file.delete", "params": {"path": "C:/ImportantData"}},
        coordinator_callback=rogue_callback,
    )

    assert res.status == "FAILED"
    assert called is False, "Dangerous tool was executed despite policy gate!"
    assert any("blocked by ExecutionPolicy" in err for err in res.errors)
    assert res.verification.get("reason") == "policy_blocked"
