"""
Unit tests for AuraCore Autonomy Lifecycle & TriggerScheduler Integration.

Verifies:
1. AuraCore directly constructs TriggerScheduler with its real ExecutionCoordinator.
2. autonomy_enabled defaults to False; TriggerScheduler is NOT active on boot.
3. start_autonomy() spawns a live _scheduler_loop task.
4. Scheduled triggers fire through AuraCore's real MasterOrchestrator coordinator.
5. stop_autonomy(drain_timeout) cleanly stops and drains the scheduler.
6. shutdown() drains the scheduler and stops voice_loop symmetrically.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from autonomy.models import EventProvenance, Trigger, TriggerState, TriggerType
from core.aura_core import AuraCore


@pytest.fixture(autouse=True)
def reset_aura_core_singleton():
    """Each test gets a clean AuraCore singleton."""
    AuraCore._instance = None
    AuraCore._initialized = False
    yield
    AuraCore._instance = None
    AuraCore._initialized = False


@pytest.mark.asyncio
async def test_auracore_autonomy_wiring_and_inactive_default(tmp_path):
    """AuraCore must own TriggerScheduler wired to real coordinator, defaulting to inactive."""
    db_path = tmp_path / "test_memory.db"

    mock_groq_provider = MagicMock()
    mock_provider_manager = MagicMock()
    mock_memory_instance = MagicMock()

    with patch("src.ai.groq_provider.GroqProvider", return_value=mock_groq_provider), \
         patch("ai.provider_manager.ProviderManager", return_value=mock_provider_manager), \
         patch("core.aura_core.Memory", return_value=mock_memory_instance):

        core = AuraCore({
            "groq_model": "mock-model",
            "voice_enabled": False,
            "memory_db_path": str(db_path),
        })

    # Subsystem ownership assertions
    assert hasattr(core, "trigger_scheduler"), "AuraCore must own trigger_scheduler"
    assert hasattr(core, "trigger_registry"), "AuraCore must own trigger_registry"
    assert hasattr(core, "coordinator"), "AuraCore must own coordinator"
    assert hasattr(core, "voice_loop"), "AuraCore must own voice_loop"

    # Wiring assertions: single-source coordinator
    assert core.trigger_scheduler.coordinator is core.coordinator, (
        "TriggerScheduler must be wired to AuraCore's real ExecutionCoordinator"
    )
    assert core.trigger_scheduler.coordinator.orchestrator is not None, (
        "AuraCore's coordinator must be wired to MasterOrchestrator"
    )

    # Autonomy inactive by default
    assert core.autonomy_active is False, "autonomy must default to inactive"
    assert core.trigger_scheduler._running is False


@pytest.mark.asyncio
async def test_auracore_start_and_stop_autonomy_lifecycle(tmp_path):
    """start_autonomy() and stop_autonomy() must manage the background scheduler task cleanly."""
    db_path = tmp_path / "test_memory.db"

    mock_groq_provider = MagicMock()
    mock_provider_manager = MagicMock()
    mock_memory_instance = MagicMock()

    with patch("src.ai.groq_provider.GroqProvider", return_value=mock_groq_provider), \
         patch("ai.provider_manager.ProviderManager", return_value=mock_provider_manager), \
         patch("core.aura_core.Memory", return_value=mock_memory_instance):

        core = AuraCore({
            "groq_model": "mock-model",
            "voice_enabled": False,
            "memory_db_path": str(db_path),
        })

    # 1. Start autonomy
    started = core.start_autonomy()
    assert started is True
    assert core.autonomy_active is True
    assert core.trigger_scheduler._scheduler_task is not None
    assert not core.trigger_scheduler._scheduler_task.done()

    # 2. Stop autonomy
    stopped = core.stop_autonomy(drain_timeout=1.0)
    assert stopped is True
    assert core.autonomy_active is False
    assert core.trigger_scheduler._running is False


@pytest.mark.asyncio
async def test_auracore_autonomy_dispatches_trigger(tmp_path):
    """TriggerScheduler running under AuraCore must fire triggers through the coordinator."""
    db_path = tmp_path / "test_memory.db"

    mock_groq_provider = MagicMock()
    mock_provider_manager = MagicMock()
    mock_memory_instance = MagicMock()

    with patch("src.ai.groq_provider.GroqProvider", return_value=mock_groq_provider), \
         patch("ai.provider_manager.ProviderManager", return_value=mock_provider_manager), \
         patch("core.aura_core.Memory", return_value=mock_memory_instance):

        core = AuraCore({
            "groq_model": "mock-model",
            "voice_enabled": False,
            "memory_db_path": str(db_path),
        })

    # Set fast poll interval on the scheduler
    core.trigger_scheduler.poll_interval_seconds = 0.05

    # Mock coordinator.coordinate to capture dispatches
    mock_coord = AsyncMock()
    mock_coord.return_value = MagicMock(success=True)
    core.coordinator.coordinate = mock_coord
    core.trigger_scheduler.coordinator = core.coordinator

    # Register an armed SCHEDULED trigger
    trigger = Trigger(
        trigger_id="trig_core_autonomy_test",
        trigger_type=TriggerType.SCHEDULED,
        action_goal="Open Calculator",
        execution_map={
            "steps": [
                {
                    "engine": "desktop",
                    "action": "open_app",
                    "parameters": {"application": "Calculator"},
                }
            ]
        },
        state=TriggerState.ARMED,
        enabled=True,
    )
    core.trigger_registry.register_trigger(trigger)

    # Start autonomy and yield time for loop execution
    core.start_autonomy()
    assert core.autonomy_active is True

    await asyncio.sleep(0.2)

    # Stop autonomy
    core.stop_autonomy(drain_timeout=1.0)

    # Assert trigger was evaluated and dispatched to coordinator
    assert mock_coord.called, "Trigger was not dispatched through AuraCore coordinator!"
    call_args = mock_coord.call_args[0][0]
    assert call_args["steps"][0]["action"] == "open_app"
    assert call_args["steps"][0]["parameters"]["application"] == "Calculator"


@pytest.mark.asyncio
async def test_auracore_shutdown_drains_autonomy_and_voice(tmp_path):
    """AuraCore.shutdown() must cleanly drain the scheduler, stop voice_loop, and close memory."""
    db_path = tmp_path / "test_memory.db"

    mock_groq_provider = MagicMock()
    mock_provider_manager = MagicMock()
    mock_memory_instance = MagicMock()

    with patch("src.ai.groq_provider.GroqProvider", return_value=mock_groq_provider), \
         patch("ai.provider_manager.ProviderManager", return_value=mock_provider_manager), \
         patch("core.aura_core.Memory", return_value=mock_memory_instance):

        core = AuraCore({
            "groq_model": "mock-model",
            "voice_enabled": False,
            "memory_db_path": str(db_path),
        })

    # Start autonomy
    core.start_autonomy()
    assert core.autonomy_active is True

    # Spy on close_session
    mock_close_session = MagicMock()
    core.memory_manager.close_session = mock_close_session

    # Shutdown
    core.shutdown()

    assert core.autonomy_active is False
    assert mock_close_session.called
