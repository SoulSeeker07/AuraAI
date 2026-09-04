import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from brain.models import ConversationContext, ConversationResult, Intent
from brain.conversation_engine import ConversationEngine
from core.planning.execution_result import ExecutionResult
from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher
from core.orchestration.agent_session import AgentSession
from core.orchestration.task_decomposer import TaskGraph, PlannerRole


@pytest.mark.asyncio
async def test_conversation_engine_forwards_engineering_to_master_orchestrator():
    """Verify that ConversationEngine._process_autonomous_engineering forwards to MasterOrchestrator.process_request_async."""
    mock_memory = MagicMock()
    mock_provider = MagicMock()

    engine = ConversationEngine(
        memory=mock_memory,
        provider_manager=mock_provider,
        model="qwen/qwen3.8-27b",
    )

    fake_exec_result = ExecutionResult(
        success=True,
        planner="coding",
        goal="implement weather widget",
        observations=["Created src/gui/widgets/weather_widget.py", "Syntax check PASSED (py_compile)"],
        data={"backend": "coding"},
    )

    with patch("core.orchestration.MasterOrchestrator.get_instance") as mock_get_orch:
        mock_orch = MagicMock()
        mock_orch.process_request_async = AsyncMock(return_value=fake_exec_result)
        mock_get_orch.return_value = mock_orch

        ctx = ConversationContext(
            user_input="implement weather widget",
            intent=Intent("autonomous_engineering"),
            messages=[],
            attachments=[],
        )

        res = await engine._process_autonomous_engineering(ctx)

        # 1. Must delegate to orchestrator with clean goal text
        mock_orch.process_request_async.assert_awaited_once_with("implement weather widget")

        # 2. Must return ConversationResult wrapping real orchestrator observations
        assert isinstance(res, ConversationResult)
        assert res.used_provider is True
        assert res.provider == "master_orchestrator"
        assert "Created src/gui/widgets/weather_widget.py" in res.text
        assert "PASSED" in res.text


@pytest.mark.asyncio
async def test_conversation_engine_process_dispatches_engineering_to_forwarder():
    """Verify that ConversationEngine.process() with an autonomous_engineering intent awaits the forwarder."""
    mock_memory = MagicMock()
    mock_provider = MagicMock()

    engine = ConversationEngine(
        memory=mock_memory,
        provider_manager=mock_provider,
        model="qwen/qwen3.8-27b",
    )

    fake_exec_result = ExecutionResult(
        success=True,
        planner="coding",
        goal="fix bug in main.py",
        observations=["Patched error handler in main.py"],
        data={"backend": "coding"},
    )

    with patch.object(engine.intent_router, "detect", return_value=Intent("autonomous_engineering")):
        with patch("core.orchestration.MasterOrchestrator.get_instance") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.process_request_async = AsyncMock(return_value=fake_exec_result)
            mock_get_orch.return_value = mock_orch

            res = await engine.process("fix bug in main.py")

            assert isinstance(res, ConversationResult)
            assert mock_orch.process_request_async.await_count == 1
            assert "Patched error handler in main.py" in res.text


@pytest.mark.asyncio
async def test_task_plan_update_logs_warning_on_absent_role_and_capability(caplog):
    """Verify that UnifiedToolDispatcher._exec_task_plan_update emits explicit logger.warning when fields are missing."""
    session = AgentSession(session_id="test_absent_fields_session")
    session.task_graph = TaskGraph(goal="Absent fields test")

    with caplog.at_level(logging.WARNING):
        res = await UnifiedToolDispatcher.dispatch(
            "task_plan_update",
            {
                "tasks": [
                    {
                        "task_id": "subtask_no_role",
                        "title": "Subtask without role or capability",
                        # required_role and capability are omitted
                    }
                ]
            },
            session=session,
        )

    assert res.get("status") == "success"
    assert "subtask_no_role" in session.task_graph.subtasks

    # Verify that explicit warnings were emitted for both omitted fields
    warnings = [rec.message for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any("missing explicit 'required_role'; defaulting to DESKTOP" in w for w in warnings)
    assert any("missing explicit 'capability'; defaulting to 'desktop.action'" in w for w in warnings)

    # Verify the created subtask has the safe defaults applied
    st = session.task_graph.subtasks["subtask_no_role"]
    assert st.required_role is PlannerRole.DESKTOP
    assert st.capability == "desktop.action"


def test_tier0_deterministic_fastpaths_remain_functional():
    """Verify that Tier 0 local hardware and time queries resolve immediately via IntentRouter and ConversationEngine."""
    mock_memory = MagicMock()
    mock_memory.summarize.return_value = "Memory active: 0 facts."
    mock_provider = MagicMock()

    engine = ConversationEngine(memory=mock_memory, provider_manager=mock_provider)

    intent_time = engine.intent_router.detect("what time is it")
    assert intent_time.name == "local_time"
    ans_time = engine._answer_local_intent(intent_time)
    assert ans_time is not None
    assert "Current time:" in ans_time

    intent_mem = engine.intent_router.detect("summarize my memory")
    assert intent_mem.name == "memory_summary"
    ans_mem = engine._answer_local_intent(intent_mem)
    assert ans_mem == "Memory active: 0 facts."


def test_intent_router_does_not_hijack_engineering_goals():
    """Verify that IntentRouter does NOT pre-emptively classify coding/engineering queries, letting them fall through to cognitive routing."""
    from brain.intent_router import IntentRouter
    router = IntentRouter(memory=MagicMock())

    engineering_queries = [
        "implement a new weather widget component",
        "please implement a weather widget",
        "can you build a weather widget for me",
        "create a dockerfile for my project",
        "write a python script to parse logs",
        "write code for an async worker",
        "fix bug in main.py",
        "refactor src/core/engine.py",
        "develop a rest api endpoint",
        "debug memory leak in cache",
        "build an autonomous coding agent",
        "create a unit test for auth module",
        "write a bash script to clean temporary directories",
        "make a backend service for user authentication",
        "repair broken test in test_runner.py",
    ]
    for q in engineering_queries:
        intent = router.detect(q)
        assert intent.name != "autonomous_engineering", f"Query '{q}' was hijacked into 'autonomous_engineering'"
        assert intent.name not in (
            "document_creation",
            "hud_overlay",
            "folder_creation",
            "open_file",
        ), f"Query '{q}' was misclassified as '{intent.name}'"
        assert intent.name in ("provider_chat", "autonomous_browser"), f"Query '{q}' routed to unexpected '{intent.name}'"


def test_intent_router_legitimate_hud_overlay_intents():
    """Verify that legitimate HUD overlay and widget display requests continue to be recognized accurately."""
    from brain.intent_router import IntentRouter
    router = IntentRouter(memory=MagicMock())

    hud_queries = [
        "show weather widget",
        "open weather widget",
        "toggle hud",
        "show task logs",
        "open personal os dashboard",
    ]
    for q in hud_queries:
        intent = router.detect(q)
        assert intent.name == "hud_overlay", f"Query '{q}' failed to route to 'hud_overlay', got '{intent.name}'"



@pytest.mark.asyncio
async def test_conversation_engine_uses_injected_orchestrator():
    """Verify that ConversationEngine uses the injected orchestrator reference rather than dynamic lookup."""
    mock_orch = MagicMock()
    mock_orch.process_request_async = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            planner="coding",
            goal="injected test",
            observations=["Injected orchestrator executed successfully"],
        )
    )

    engine = ConversationEngine(
        memory=MagicMock(),
        provider_manager=MagicMock(),
        orchestrator=mock_orch,
    )

    ctx = ConversationContext(
        user_input="injected test",
        intent=Intent("autonomous_engineering"),
        messages=[],
        attachments=[],
    )

    res = await engine._process_autonomous_engineering(ctx)
    mock_orch.process_request_async.assert_awaited_once_with("injected test")
    assert "Injected orchestrator executed successfully" in res.text


@pytest.mark.asyncio
async def test_conversation_engine_routes_via_aura_core_when_present():
    """Verify that ConversationEngine routes through AuraCore.process_request when aura_core is injected."""
    mock_aura_core = MagicMock()
    mock_aura_core.process_request = AsyncMock(return_value="AuraCore kernel processed the engineering goal.")

    engine = ConversationEngine(
        memory=MagicMock(),
        provider_manager=MagicMock(),
        aura_core=mock_aura_core,
    )

    ctx = ConversationContext(
        user_input="implement auth module",
        intent=Intent("autonomous_engineering"),
        messages=[],
        attachments=[],
    )

    res = await engine._process_autonomous_engineering(ctx)

    mock_aura_core.process_request.assert_awaited_once_with("implement auth module")
    assert isinstance(res, ConversationResult)
    assert res.used_provider is True
    assert res.provider == "aura_core"
    assert res.text == "AuraCore kernel processed the engineering goal."


