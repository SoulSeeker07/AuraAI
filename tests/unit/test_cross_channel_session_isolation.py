"""
Regression Tests: Cross-Channel Session Isolation & _last_session Pollution Guard
Location: tests/unit/test_cross_channel_session_isolation.py

Verifies that background autonomous triggers and daemons running through MasterOrchestrator
do not pollute or overwrite self._last_session, preventing interactive users from
inadvertently authorizing unvetted background trigger actions.
"""

from unittest.mock import MagicMock
import pytest

from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.request_source import RequestSource
from core.orchestration.agent_session import AgentSession
from core.orchestration.confirmation import ActionPlanConfirmation
from core.planning.action_plan import ActionPlan
from core.planning.execution_result import ExecutionResult
from core.backends.backend_registry import BackendRegistry


def create_mock_backend(planner: str = "desktop", goal: str = "test", success: bool = True, policy_action: str = "launch_new"):
    backend = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "describe", "health_check"])
    backend.name = "mock_backend"
    res = ExecutionResult(
        success=success,
        planner=planner,
        goal=goal,
        observations=["Executed successfully" if success else "Requires confirmation"],
        data={"policy_action": policy_action, "action_target": "notepad", "capability": "app_open"},
    )
    backend.execute.return_value = res
    backend.execute_plan.return_value = res
    return backend


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Ensure clean orchestrator singleton before and after each test."""
    MasterOrchestrator.reset_instance()
    BackendRegistry.reset_instance()
    yield
    MasterOrchestrator.reset_instance()
    BackendRegistry.reset_instance()


@pytest.mark.asyncio
async def test_autonomous_trigger_does_not_overwrite_last_session():
    """Verify that a TRIGGER_AUTONOMOUS run does not overwrite self._last_session."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)
    assert orchestrator._last_session is None

    mock_backend = create_mock_backend(goal="Autonomous background trigger")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    # 1. Run a simulated autonomous trigger goal
    res = await orchestrator.process_request_async(
        goal_text="Open Notepad",
        source=RequestSource.TRIGGER_AUTONOMOUS,
    )
    assert res.success is True

    # 2. _last_session MUST remain None (not polluted by autonomous trigger)
    assert orchestrator._last_session is None
    assert orchestrator.check_pending_confirmation() is None


@pytest.mark.asyncio
async def test_human_interactive_session_properly_sets_last_session():
    """Verify that default HUMAN_INTERACTIVE requests set self._last_session."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    mock_backend = create_mock_backend(goal="Open Notepad")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    await orchestrator.process_request_async(
        goal_text="Open Notepad",
        # Defaults to RequestSource.HUMAN_INTERACTIVE
    )

    # _last_session MUST be set to the human session
    assert orchestrator._last_session is not None
    assert orchestrator._last_session.goal == "Open Notepad"


@pytest.mark.asyncio
async def test_background_trigger_cannot_leak_confirmation_to_human_channel():
    """
    Critical Security Regression Test:
    Simulates a background trigger that halts on ASK_USER confirmation, asserts that
    a confirmation was populated on the trigger's local session, and proves that
    self._last_session is preserved and an interactive 'yes' cannot resolve the trigger.
    """
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    # 1. Human establishes an interactive session (no pending confirmation)
    human_session = AgentSession(goal="Human goal: check weather")
    orchestrator._last_session = human_session
    assert orchestrator.check_pending_confirmation() is None

    # 2. Trigger fires in background with action that returns policy_action="ask_user"
    mock_ask_backend = create_mock_backend(goal="Trigger action", success=False, policy_action="ask_user")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_ask_backend)

    trigger_session = AgentSession(goal="Open Notepad")
    res = await orchestrator.process_request_async(
        goal_text="Open Notepad",
        source=RequestSource.TRIGGER_AUTONOMOUS,
        session=trigger_session,
    )
    assert res.success is False

    # 3. Prove that the trigger session was suspended with an approval ticket
    assert trigger_session.data.get("is_suspended") is True
    assert trigger_session.data.get("suspended_ticket_id") is not None
    assert str(trigger_session.data.get("suspended_ticket_id")).startswith("tkt_")

    # 4. Prove that self._last_session was NOT overwritten (remains the human session)
    assert orchestrator._last_session is human_session
    assert orchestrator._last_session is not trigger_session
    assert orchestrator._last_session.goal == "Human goal: check weather"

    # 5. check_pending_confirmation() must return None (human channel has no pending confirmation)
    assert orchestrator.check_pending_confirmation() is None

    # 6. An interactive 'yes' from the user must return None and NOT execute the trigger confirmation
    resolved = orchestrator.resolve_pending_confirmation("yes")
    assert resolved is None
    assert trigger_session.data.get("is_suspended") is True



@pytest.mark.asyncio
async def test_human_confirmation_not_clobbered_by_subsequent_trigger():
    """
    Verify that an active pending human confirmation is NOT overwritten or cleared
    by a subsequent background autonomous trigger run.
    """
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    # 1. Human request generates a pending confirmation
    mock_ask_backend = create_mock_backend(goal="Open another Notepad", success=False, policy_action="ask_user")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_ask_backend)

    human_res = await orchestrator.process_request_async(
        goal_text="Open Notepad",
        source=RequestSource.HUMAN_INTERACTIVE,
    )
    assert human_res.success is False
    human_conf = orchestrator.check_pending_confirmation()
    assert human_conf is not None
    # Exact pinned assertions
    assert human_conf.action_plan.action == "app_open"
    assert human_conf.action_plan.target == "notepad"

    # 2. Background autonomous trigger runs
    mock_ok_backend = create_mock_backend(goal="Background sync", success=True, policy_action="launch_new")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_ok_backend)

    trigger_res = await orchestrator.process_request_async(
        goal_text="Sync background data",
        source=RequestSource.TRIGGER_AUTONOMOUS,
    )
    assert trigger_res.success is True

    # 3. Human's pending confirmation MUST still be active and intact on _last_session
    active_conf = orchestrator.check_pending_confirmation()
    assert active_conf is human_conf
    assert active_conf.resolved is False
    assert active_conf.action_plan.action == "app_open"
    assert active_conf.action_plan.target == "notepad"
