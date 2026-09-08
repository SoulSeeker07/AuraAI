import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from core.aura_core import AuraCore
from core.orchestration.agent_session import AgentSession
from core.orchestration.master_orchestrator import MasterOrchestrator


@pytest.fixture
def aura_core_instance():
    """Provides an isolated AuraCore instance for session testing."""
    core = AuraCore.get_instance()
    core.llm_enabled = True
    core.groq_client = MagicMock()
    # Bypass legacy IntentRouter fast-path and lazy init_brain to test core reasoning & tool engine directly
    core._init_brain = MagicMock()
    mock_conv = MagicMock()
    mock_conv._answer_local_intent.return_value = None
    core.conversation_engine = mock_conv
    core.reset_session()
    return core


def _create_turn_mocks():
    """Creates a 2-turn mock: turn 1 calls a tool, turn 2 returns final content."""
    tool_call = MagicMock()
    tool_call.id = "tc_1"
    tool_call.function.name = "web_search"
    tool_call.function.arguments = '{"query": "quantum computing"}'

    choice_turn1 = MagicMock()
    choice_turn1.message.tool_calls = [tool_call]
    choice_turn1.message.content = None
    resp_turn1 = MagicMock(choices=[choice_turn1])

    choice_turn2 = MagicMock()
    choice_turn2.message.tool_calls = None
    choice_turn2.message.content = "Analysis complete."
    resp_turn2 = MagicMock(choices=[choice_turn2])

    return [resp_turn1, resp_turn2]


@pytest.mark.asyncio
async def test_session_id_parameter_accepted(aura_core_instance):
    """Confirm process_request and get_ai_response accept explicit session_id without error."""
    with patch.object(aura_core_instance, "get_ai_response", new_callable=AsyncMock) as mock_get_ai:
        mock_get_ai.return_value = "Test response"
        
        resp = await aura_core_instance.process_request("analyze quantum trends", session_id="sess_gui_12345")
        assert resp == "Test response"
        mock_get_ai.assert_awaited_once()
        assert mock_get_ai.call_args.kwargs.get("session_id") == "sess_gui_12345"


@pytest.mark.asyncio
async def test_caller_session_isolation_in_agent_session(aura_core_instance):
    """
    Confirm that two callers passing distinct session_ids (e.g. GUI vs Voice)
    produce AgentSession instances with their own respective session_ids,
    and DO NOT adopt a stale _last_session from MasterOrchestrator.
    """
    core = aura_core_instance

    # Pre-populate MasterOrchestrator._last_session with a stale session
    orch = MasterOrchestrator.get_instance()
    stale_session = AgentSession(goal="stale background job", session_id="sess_stale_9999")
    orch._last_session = stale_session

    dispatched_sessions = []

    async def mock_dispatch(fn_name, fn_args, session=None, **kwargs):
        dispatched_sessions.append(session.session_id)
        return {"status": "success", "result": "mock"}

    with patch("core.tools.unified_tool_dispatcher.UnifiedToolDispatcher.dispatch", side_effect=mock_dispatch):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            # First turn: GUI caller
            mock_thread.side_effect = _create_turn_mocks()
            await core.get_ai_response("analyze trends in market data", enable_tools=True, session_id="sess_gui_1111")
            assert len(dispatched_sessions) >= 1
            assert dispatched_sessions[0] == "sess_gui_1111"
            assert dispatched_sessions[0] != "sess_stale_9999"

            # Second turn: Voice caller
            dispatched_sessions.clear()
            mock_thread.side_effect = _create_turn_mocks()
            await core.get_ai_response("synthesize findings for report", enable_tools=True, session_id="sess_voice_2222")
            assert len(dispatched_sessions) >= 1
            assert dispatched_sessions[0] == "sess_voice_2222"
            assert dispatched_sessions[0] != "sess_gui_1111"


@pytest.mark.asyncio
async def test_ephemeral_fallback_uniqueness(aura_core_instance):
    """
    Confirm that callers omitting session_id receive unique ephemeral session IDs
    per request rather than latching onto a single shared pointer.
    """
    core = aura_core_instance

    dispatched_sessions = []

    async def mock_dispatch(fn_name, fn_args, session=None, **kwargs):
        dispatched_sessions.append(session.session_id)
        return {"status": "success", "result": "mock"}

    with patch("core.tools.unified_tool_dispatcher.UnifiedToolDispatcher.dispatch", side_effect=mock_dispatch):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            # Call 1 with session_id=None
            mock_thread.side_effect = _create_turn_mocks()
            await core.get_ai_response("ephemeral request 1", enable_tools=True, session_id=None)
            id_1 = dispatched_sessions[-1]
            assert id_1.startswith("sess_ephemeral_")

            # Call 2 with session_id=None
            mock_thread.side_effect = _create_turn_mocks()
            await core.get_ai_response("ephemeral request 2", enable_tools=True, session_id=None)
            id_2 = dispatched_sessions[-1]
            assert id_2.startswith("sess_ephemeral_")

            # Must be two distinct ephemeral IDs (no singleton latching)
            assert id_1 != id_2


def test_reset_session_cleans_conversation_history(aura_core_instance):
    """Confirm reset_session() clears in-memory conversation history."""
    aura_core_instance.add_to_conversation("user", "remember me")
    aura_core_instance.add_to_conversation("assistant", "I will")
    assert len(aura_core_instance.conversation_history) == 2

    aura_core_instance.reset_session()
    assert len(aura_core_instance.conversation_history) == 0
