"""
Unit tests for passive Goal and Step telemetry tracking across AuraCore.
Location: tests/unit/test_passive_goal_telemetry.py
"""

import sqlite3
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.aura_core import AuraCore
from core.orchestration.goal_state import GoalStatus, StepStatus
from core.orchestration.goal_store import GoalStore


@pytest.fixture
def temp_goal_store(tmp_path):
    """Provides an isolated GoalStore for testing."""
    db_file = tmp_path / "sandbox_Memory.db"
    return GoalStore(db_path=db_file)


@pytest.fixture
def aura_core_with_temp_store(temp_goal_store):
    """Provides an isolated AuraCore instance wired to the temp GoalStore."""
    core = AuraCore.get_instance()
    core.llm_enabled = True
    core.groq_client = MagicMock()
    core._init_brain = MagicMock()
    mock_conv = MagicMock()
    mock_conv._answer_local_intent.return_value = None
    core.conversation_engine = mock_conv
    core.goal_store = temp_goal_store
    core.reset_session()
    return core, temp_goal_store


def _create_tool_turn_mocks():
    """Turn 1 calls web_search, Turn 2 returns final response."""
    tool_call = MagicMock()
    tool_call.id = "tc_telemetry_1"
    tool_call.function.name = "web_search"
    tool_call.function.arguments = '{"query": "superconductors"}'

    choice1 = MagicMock()
    choice1.message.tool_calls = [tool_call]
    choice1.message.content = None
    resp1 = MagicMock(choices=[choice1])

    choice2 = MagicMock()
    choice2.message.tool_calls = None
    choice2.message.content = "Research synthesis on superconductors."
    resp2 = MagicMock(choices=[choice2])

    return [resp1, resp2]


@pytest.mark.asyncio
async def test_react_tool_execution_passive_telemetry(aura_core_with_temp_store):
    """
    Confirm that an execution with tool calling creates a Goal, Step(s) with observed outputs,
    and finishes with GoalStatus.DONE in the store.
    """
    core, store = aura_core_with_temp_store

    async def mock_dispatch(fn_name, fn_args, session=None, **kwargs):
        return {"status": "success", "results": ["article 1", "article 2"]}

    with patch("core.tools.unified_tool_dispatcher.UnifiedToolDispatcher.dispatch", side_effect=mock_dispatch):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.side_effect = _create_tool_turn_mocks()
            resp = await core.get_ai_response(
                "research superconductors",
                enable_tools=True,
                session_id="sess_gui_tel_1",
            )
            assert "superconductors" in resp

    goals = store.list_goals_for_session("sess_gui_tel_1")
    assert len(goals) == 1
    g = goals[0]
    assert g.user_prompt == "research superconductors"
    assert g.status == GoalStatus.DONE
    assert len(g.steps) >= 1

    # First step should be the tool call
    tool_step = g.steps[0]
    assert tool_step.tool_name == "web_search"
    assert tool_step.tool_args == {"query": "superconductors"}
    assert tool_step.status == StepStatus.OBSERVED
    assert "article 1" in tool_step.observation


@pytest.mark.asyncio
async def test_confirmation_required_sets_awaiting_user(aura_core_with_temp_store):
    """
    Confirm that when a tool returns confirmation_required,
    the Goal status is updated to AWAITING_USER.
    """
    core, store = aura_core_with_temp_store

    tool_call = MagicMock()
    tool_call.id = "tc_conf_1"
    tool_call.function.name = "execute_command"
    tool_call.function.arguments = '{"command": "shutdown"}'

    choice1 = MagicMock()
    choice1.message.tool_calls = [tool_call]
    choice1.message.content = None
    resp1 = MagicMock(choices=[choice1])

    async def mock_dispatch(fn_name, fn_args, session=None, **kwargs):
        return {
            "status": "confirmation_required",
            "prompt": "Action requires human confirmation. Confirm with yes.",
            "ticket_id": "tkt_1234",
        }

    with patch("core.tools.unified_tool_dispatcher.UnifiedToolDispatcher.dispatch", side_effect=mock_dispatch):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = resp1
            resp = await core.get_ai_response(
                "reboot the server",
                enable_tools=True,
                session_id="sess_gui_conf_1",
            )
            assert "Action requires human confirmation" in resp

    goals = store.list_goals_for_session("sess_gui_conf_1")
    assert len(goals) == 1
    g = goals[0]
    assert g.status == GoalStatus.AWAITING_USER


@pytest.mark.asyncio
async def test_direct_answer_records_reasoning_step(aura_core_with_temp_store):
    """
    Confirm that a pure reasoning direct response (0 tools called) records
    a single Step with tool_name=None and finishes DONE.
    """
    core, store = aura_core_with_temp_store

    choice = MagicMock()
    choice.message.tool_calls = None
    choice.message.content = "Paris is the capital of France."
    resp = MagicMock(choices=[choice])

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = resp
        reply = await core.get_ai_response(
            "what is the capital of France?",
            enable_tools=True,
            session_id="sess_voice_direct_1",
        )
        assert "Paris" in reply

    goals = store.list_goals_for_session("sess_voice_direct_1")
    assert len(goals) == 1
    g = goals[0]
    assert g.status == GoalStatus.DONE
    assert len(g.steps) == 1
    assert g.steps[0].tool_name is None
    assert g.steps[0].status == StepStatus.VERIFIED


@pytest.mark.asyncio
async def test_passive_telemetry_failure_does_not_break_execution(aura_core_with_temp_store):
    """
    Confirm fail-safe guarantee: if GoalStore throws an exception,
    AuraCore continues normal execution and returns the response cleanly.
    """
    core, store = aura_core_with_temp_store

    # Break store methods to simulate DB error
    broken_store = MagicMock()
    broken_store.create_goal.side_effect = sqlite3.OperationalError("disk I/O error")
    broken_store.add_step.side_effect = sqlite3.OperationalError("disk I/O error")
    broken_store.update_goal_status.side_effect = sqlite3.OperationalError("disk I/O error")
    core.goal_store = broken_store

    choice = MagicMock()
    choice.message.tool_calls = None
    choice.message.content = "Everything still works fine."
    resp = MagicMock(choices=[choice])

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = resp
        reply = await core.get_ai_response(
            "test resilience",
            enable_tools=True,
            session_id="sess_gui_resilient",
        )
        assert reply == "Everything still works fine."


@pytest.mark.asyncio
async def test_fast_path_passive_telemetry(aura_core_with_temp_store):
    """
    Confirm that deterministic fast-paths passively record a Goal and Step.
    """
    core, store = aura_core_with_temp_store

    core._record_passive_fast_path(
        user_goal="what time is it",
        session_id="sess_gui_fast_1",
        action_name="local_time",
        result_text="The time is 12:00 PM",
    )

    goals = store.list_goals_for_session("sess_gui_fast_1")
    assert len(goals) == 1
    g = goals[0]
    assert g.user_prompt == "what time is it"
    assert g.status == GoalStatus.DONE
    assert len(g.steps) == 1
    assert g.steps[0].tool_name == "fast_path"
    assert g.steps[0].tool_args == {"action": "local_time"}
    assert g.steps[0].status == StepStatus.VERIFIED


@pytest.mark.asyncio
async def test_autonomous_browser_passive_telemetry_unpacks_steps(aura_core_with_temp_store):
    """
    Confirm Phase 1.5 contract: autonomous_browser unpacking persists granular
    individual Step records into GoalStore and emits progress events.
    """
    core, store = aura_core_with_temp_store

    mock_intent = MagicMock()
    mock_intent.name = "autonomous_browser"

    browser_steps = [
        {"step": 0, "tool": "navigate", "args": {"url": "https://python.org/downloads"}, "result": "Loaded page"},
        {"step": 1, "tool": "extract_text", "args": {"description": "latest release"}, "result": "Python 3.12.0"},
        {"step": 2, "tool": "done", "args": {"summary": "Found Python 3.12.0 release"}, "result": "Success"},
    ]

    mock_conv = MagicMock()
    mock_conv.intent_router.detect.return_value = mock_intent
    mock_conv._answer_local_intent.return_value = "Python 3.12.0 was released."
    mock_conv._last_browser_result = {
        "status": "SUCCESS",
        "summary": "Found Python 3.12.0 release",
        "steps": browser_steps,
    }
    core.conversation_engine = mock_conv

    mock_emitter = MagicMock()

    resp = await core.process_request(
        "search python 3.12 release notes",
        session_id="sess_gui_browser_test",
        emitter=mock_emitter,
    )
    assert resp == "Python 3.12.0 was released."

    # Progress emitter must have received started and completed events
    assert mock_emitter.emit.call_count >= 2
    started_event = mock_emitter.emit.call_args_list[0][0][0]
    assert "in progress" in started_event.label.lower()

    # GoalStore must contain the unpacked granular steps
    goals = store.list_goals_for_session("sess_gui_browser_test")
    assert len(goals) == 1
    g = goals[0]
    assert g.status == GoalStatus.DONE
    assert len(g.steps) == 3

    assert g.steps[0].tool_name == "browser.navigate"
    assert g.steps[0].tool_args == {"url": "https://python.org/downloads"}
    assert g.steps[0].status == StepStatus.VERIFIED

    assert g.steps[1].tool_name == "browser.extract_text"
    assert g.steps[1].tool_args == {"description": "latest release"}
    assert "Python 3.12.0" in g.steps[1].observation

    assert g.steps[2].tool_name == "browser.done"

