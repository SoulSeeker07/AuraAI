"""
Unit Tests for Milestone 24: TriggerScheduler & Proactive Autonomy
Location: tests/unit/test_event_runtime.py
"""

import asyncio
os_import = __import__("os")
import sys
from pathlib import Path
import pytest
import shutil
import tempfile

sys.path.insert(0, os_import.path.abspath("src"))

from autonomy.trigger_scheduler import TriggerScheduler
from autonomy.models import ConcurrencyPolicy, EventProvenance, Trigger, TriggerState, TriggerType
from autonomy.trigger_registry import TriggerRegistry
from brain.execution_coordinator import ExecutionCoordinator
from core.orchestration.execution_policy import ExecutionPolicy


@pytest.fixture
def temp_storage():
    tmp_dir = tempfile.mkdtemp()
    storage_file = Path(tmp_dir) / "triggers.json"
    yield storage_file
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_g1_scheduled_trigger(temp_storage):
    registry = TriggerRegistry(storage_path=temp_storage)
    coordinator = ExecutionCoordinator()
    scheduler = TriggerScheduler(registry=registry, coordinator=coordinator)

    trigger = Trigger(
        trigger_id="trg_g1_scheduled",
        trigger_type=TriggerType.SCHEDULED,
        action_goal="Execute scheduled health check",
        execution_map={
            "goal": "Execute scheduled health check",
            "steps": [{"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<h1>OK</h1>"}}],
        },
        interval_seconds=0.1,
    )
    registry.register_trigger(trigger)

    await scheduler.start()
    await asyncio.sleep(0.3)
    await scheduler.stop()

    t = registry.get_trigger("trg_g1_scheduled")
    assert t is not None
    assert t.state in [TriggerState.VERIFIED, TriggerState.RUNNING, TriggerState.FIRED]
    assert t.last_provenance is not None
    assert t.last_provenance.trigger_type == TriggerType.SCHEDULED.value


@pytest.mark.asyncio
async def test_g2_system_event_trigger(temp_storage):
    registry = TriggerRegistry(storage_path=temp_storage)
    coordinator = ExecutionCoordinator()
    scheduler = TriggerScheduler(registry=registry, coordinator=coordinator)

    trigger = Trigger(
        trigger_id="trg_g2_file_event",
        trigger_type=TriggerType.SYSTEM_EVENT,
        action_goal="Process file change event",
        execution_map={
            "goal": "Process file change event",
            "steps": [{"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<h1>FileChanged</h1>"}}],
        },
        event_pattern="file.changed",
    )
    registry.register_trigger(trigger)

    await scheduler.start()
    count = await scheduler.emit_event("file.changed", {"path": "src/main.py"})
    assert count == 1

    await asyncio.sleep(0.3)
    await scheduler.stop()

    t = registry.get_trigger("trg_g2_file_event")
    assert t is not None
    assert t.state == TriggerState.VERIFIED


@pytest.mark.asyncio
async def test_g3_persistent_state_restart(temp_storage):
    # Step 1: Register trigger and save to disk
    reg1 = TriggerRegistry(storage_path=temp_storage)
    trigger = Trigger(
        trigger_id="trg_g3_persistent",
        trigger_type=TriggerType.SYSTEM_EVENT,
        action_goal="Persistent task",
        execution_map={"goal": "Persistent task", "steps": []},
        event_pattern="system.restart",
        dedup_key="dedup_persistent_001",
    )
    reg1.register_trigger(trigger)

    # Step 2: Simulate process termination & re-instantiation
    reg2 = TriggerRegistry(storage_path=temp_storage)
    t_reloaded = reg2.get_trigger("trg_g3_persistent")
    assert t_reloaded is not None
    assert t_reloaded.trigger_id == "trg_g3_persistent"
    assert t_reloaded.dedup_key == "dedup_persistent_001"
    assert t_reloaded.state == TriggerState.ARMED


@pytest.mark.asyncio
async def test_g4_event_queue(temp_storage):
    registry = TriggerRegistry(storage_path=temp_storage)
    coordinator = ExecutionCoordinator()
    scheduler = TriggerScheduler(registry=registry, coordinator=coordinator)

    t1 = Trigger("trg_q1", TriggerType.SYSTEM_EVENT, "Queue step 1", {"goal": "Q1", "steps": [{"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<h1>Q1</h1>"}}]}, event_pattern="q.event")
    t2 = Trigger("trg_q2", TriggerType.SYSTEM_EVENT, "Queue step 2", {"goal": "Q2", "steps": [{"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<h1>Q2</h1>"}}]}, event_pattern="q.event")
    registry.register_trigger(t1)
    registry.register_trigger(t2)

    await scheduler.start()
    matched = await scheduler.emit_event("q.event")
    assert matched == 2

    await asyncio.sleep(0.3)
    await scheduler.stop()

    assert registry.get_trigger("trg_q1").state in [TriggerState.VERIFIED, TriggerState.RUNNING]
    assert registry.get_trigger("trg_q2").state in [TriggerState.VERIFIED, TriggerState.RUNNING]


@pytest.mark.asyncio
async def test_g6_policy_enforcement(temp_storage):
    registry = TriggerRegistry(storage_path=temp_storage)
    coordinator = ExecutionCoordinator()
    scheduler = TriggerScheduler(registry=registry, coordinator=coordinator)

    # Trigger with unauthorized high-risk action
    trigger = Trigger(
        trigger_id="trg_g6_high_risk",
        trigger_type=TriggerType.SYSTEM_EVENT,
        action_goal="Execute unauthorized high risk action",
        execution_map={
            "goal": "Execute unauthorized high risk action",
            "steps": [{"engine": "desktop", "action": "file.delete", "parameters": {"target": "C:\\Windows\\System32\\kernel.dll"}}],
        },
        event_pattern="high_risk.trigger",
    )
    registry.register_trigger(trigger)

    await scheduler.start()
    await scheduler.emit_event("high_risk.trigger")
    await asyncio.sleep(0.3)
    await scheduler.stop()

    t = registry.get_trigger("trg_g6_high_risk")
    assert t is not None
    assert t.state == TriggerState.BLOCKED
    assert t.last_provenance.result_status == "BLOCKED"


@pytest.mark.asyncio
async def test_g10_duplicate_prevention(temp_storage):
    registry = TriggerRegistry(storage_path=temp_storage)
    t1 = Trigger("t1", TriggerType.SCHEDULED, "Task 1", {"goal": "T1", "steps": []}, dedup_key="unique_key_001")
    t2 = Trigger("t2", TriggerType.SCHEDULED, "Task 2", {"goal": "T2", "steps": []}, dedup_key="unique_key_001")

    res1 = registry.register_trigger(t1)
    res2 = registry.register_trigger(t2)

    assert res1 is True
    assert res2 is False
    assert registry.get_trigger("t2") is None


@pytest.mark.asyncio
async def test_g11_user_cancellation(temp_storage):
    registry = TriggerRegistry(storage_path=temp_storage)
    t1 = Trigger("t_cancel", TriggerType.SCHEDULED, "Cancel Task", {"goal": "Cancel", "steps": []})
    registry.register_trigger(t1)

    assert registry.get_trigger("t_cancel").enabled is True

    registry.set_enabled("t_cancel", False)
    assert registry.get_trigger("t_cancel").enabled is False
    assert registry.get_trigger("t_cancel").state == TriggerState.REGISTERED

    removed = registry.remove_trigger("t_cancel")
    assert removed is True
    assert registry.get_trigger("t_cancel") is None


@pytest.mark.asyncio
async def test_scheduler_loop_actually_runs_after_start(temp_storage):
    """
    Regression test for the boot() no-op bug:
    Proves that calling start() creates a live _scheduler_loop task that
    autonomously evaluates SCHEDULED triggers and dispatches to
    coordinator.coordinate() — without any manual _running flag manipulation.

    This test would have FAILED with the old EventRuntime boot() code that did:
        self.event_runtime._running = True  # pre-flip
        asyncio.create_task(self.event_runtime.start())  # start() sees _running=True, returns immediately
    """
    from unittest.mock import AsyncMock, MagicMock

    registry = TriggerRegistry(storage_path=temp_storage)

    # Mock coordinator whose .coordinate() we can assert was called
    mock_coordinator = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.execution_id = "test_exec_001"
    mock_coordinator.coordinate = AsyncMock(return_value=mock_result)

    scheduler = TriggerScheduler(
        registry=registry,
        coordinator=mock_coordinator,
        poll_interval_seconds=0.05,
    )

    trigger = Trigger(
        trigger_id="trg_loop_regression",
        trigger_type=TriggerType.SCHEDULED,
        action_goal="Prove scheduler loop runs",
        execution_map={
            "goal": "Prove scheduler loop runs",
            "steps": [],  # No policy-gated steps — goes straight to coordinator
        },
        interval_seconds=0.05,
    )
    registry.register_trigger(trigger)

    # Pre-conditions: scheduler is NOT running, no task exists
    assert scheduler._is_running is False
    assert scheduler._scheduler_task is None

    await scheduler.start()

    # Post-start: scheduler IS running and _scheduler_task is a live Task
    assert scheduler._is_running is True
    assert scheduler._scheduler_task is not None
    assert isinstance(scheduler._scheduler_task, asyncio.Task)
    assert not scheduler._scheduler_task.done()

    # Wait enough for at least one poll cycle to fire the trigger
    await asyncio.sleep(0.3)

    await scheduler.stop()

    # The scheduler loop must have autonomously fired the trigger
    # and dispatched to coordinator.coordinate()
    assert mock_coordinator.coordinate.call_count >= 1, (
        "coordinator.coordinate() was never called — _scheduler_loop did not "
        "autonomously fire the SCHEDULED trigger after start()"
    )

    # Verify the trigger transitioned through the expected states
    t = registry.get_trigger("trg_loop_regression")
    assert t is not None
    assert t.state == TriggerState.VERIFIED
    assert t.last_provenance is not None
    assert t.last_provenance.result_status == "VERIFIED"
    assert t.last_provenance.execution_id == "test_exec_001"
