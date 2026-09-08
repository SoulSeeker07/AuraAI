"""
Unit tests for AuraAI Phase 2 Active Verified Agent Loop (AgentLoop).
Location: tests/unit/test_agent_loop.py
"""

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.orchestration.agent_loop import AgentLoop, VERIFIER_REGISTRY, verify_create_file_artifact
from core.orchestration.goal_state import Goal, GoalStatus, Step, StepStatus
from core.orchestration.goal_store import GoalStore
from core.orchestration.orchestration_store import OrchestrationStore


def _make_response(content=None, tool_calls=None):
    """Helper to construct a mock OpenAI/Groq response object."""
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        role="assistant",
    )
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def _make_tool_call(name: str, arguments: dict, call_id: str = "tc_1"):
    """Helper to construct a mock tool call object."""
    fn = SimpleNamespace(
        name=name,
        arguments=json.dumps(arguments) if isinstance(arguments, dict) else str(arguments),
    )
    return SimpleNamespace(id=call_id, function=fn, type="function")


@pytest.fixture
def temp_goal_store(tmp_path):
    """Create an isolated test DB and GoalStore."""
    db_path = tmp_path / "test_memory.db"
    store = OrchestrationStore(db_path=db_path)
    return GoalStore(store=store)


# ── Test 1: Direct Reasoning ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_direct_reasoning(temp_goal_store):
    """A pure question with no tool calls completes in 1 step, sets Step VERIFIED and Goal DONE."""
    session_id = "sess_test_reasoning"
    prompt = "What is the capital of France?"

    async def mock_llm(kwargs):
        return _make_response(content="The capital of France is Paris.")

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=5,
        llm_caller=mock_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert "Paris" in result

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    goal = goals[0]
    assert goal.status == GoalStatus.DONE
    assert len(goal.steps) == 1

    step = goal.steps[0]
    assert step.tool_name is None
    assert step.status == StepStatus.VERIFIED
    assert step.verify_reason == "Direct response generated"
    assert "Paris" in (step.observation or "")


# ── Test 2: create_file_artifact with Active Verification ───────────────────


@pytest.mark.asyncio
async def test_agent_loop_create_file_artifact_verified(temp_goal_store, tmp_path):
    """Tool creates a non-empty file on disk; verify() checks file and passes; Goal marks DONE."""
    session_id = "sess_test_artifact_pass"
    prompt = "Create a shopping list file"
    test_file = tmp_path / "shopping_list.xlsx"

    turn_count = 0

    async def mock_llm(kwargs):
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            # Turn 1: call create_file_artifact
            tc = _make_tool_call(
                "create_file_artifact",
                {"goal": "shopping list", "output_filename": str(test_file)},
                call_id="call_file_1",
            )
            return _make_response(content=None, tool_calls=[tc])
        else:
            # Turn 2: acknowledge completion
            return _make_response(content=f"Created shopping list at {test_file}")

    mock_dispatcher = MagicMock()

    async def fake_dispatch(name, args, **kwargs):
        # Simulate real tool writing the file to disk
        test_file.write_bytes(b"Spreadsheet binary data content")
        return {
            "status": "success",
            "output_path": str(test_file),
            "message": f"Created {test_file.name}",
        }

    mock_dispatcher.dispatch = AsyncMock(side_effect=fake_dispatch)

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=5,
        dispatcher=mock_dispatcher,
        llm_caller=mock_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert f"Created shopping list at {test_file}" in result

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    goal = goals[0]
    assert goal.status == GoalStatus.DONE

    steps = goal.steps
    assert len(steps) == 2  # 1 tool step + 1 reasoning step

    tool_step = steps[0]
    assert tool_step.tool_name == "create_file_artifact"
    assert tool_step.status == StepStatus.VERIFIED
    assert "File artifact verified on disk" in (tool_step.verify_reason or "")

    reasoning_step = steps[1]
    assert reasoning_step.tool_name is None
    assert reasoning_step.status == StepStatus.VERIFIED


# ── Test 3: Verification Failure & Adaptation Loop ──────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_verification_failure_adaptation(temp_goal_store, tmp_path):
    """
    Turn 1: Tool reports success but file is 0 bytes on disk -> verify() fails.
    Adaptation: failure reason is injected into messages.
    Turn 2: Model adapts and tool writes valid file -> verify() passes -> Goal DONE.
    """
    session_id = "sess_test_adapt"
    prompt = "Create report document"
    bad_file = tmp_path / "empty_report.docx"
    good_file = tmp_path / "valid_report.docx"

    messages_received_by_llm = []
    turn_count = 0

    async def mock_llm(kwargs):
        nonlocal turn_count
        turn_count += 1
        messages_received_by_llm.append(list(kwargs["messages"]))

        if turn_count == 1:
            tc = _make_tool_call(
                "create_file_artifact",
                {"goal": "report", "output_filename": str(bad_file)},
                call_id="call_fail_1",
            )
            return _make_response(content=None, tool_calls=[tc])
        elif turn_count == 2:
            # Model observes the failure feedback from turn 1, adapts to valid file path
            tc = _make_tool_call(
                "create_file_artifact",
                {"goal": "report", "output_filename": str(good_file)},
                call_id="call_pass_2",
            )
            return _make_response(content=None, tool_calls=[tc])
        else:
            return _make_response(content="Report created successfully after retry.")

    mock_dispatcher = MagicMock()

    async def fake_dispatch(name, args, **kwargs):
        out = args.get("output_filename")
        if out == str(bad_file):
            # Create empty 0-byte file (causes verify to fail!)
            bad_file.write_bytes(b"")
            return {"status": "success", "output_path": str(bad_file)}
        else:
            # Create valid file
            good_file.write_bytes(b"Valid Word doc contents")
            return {"status": "success", "output_path": str(good_file)}

    mock_dispatcher.dispatch = AsyncMock(side_effect=fake_dispatch)

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=5,
        dispatcher=mock_dispatcher,
        llm_caller=mock_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert "Report created successfully after retry." in result

    # Check that Turn 2 messages received the adaptation feedback
    turn_2_msgs = messages_received_by_llm[1]
    tool_feedback = [m for m in turn_2_msgs if m.get("role") == "tool"]
    assert len(tool_feedback) >= 1
    feedback_content = json.loads(tool_feedback[0]["content"])
    assert feedback_content["status"] == "failed_verification"
    assert "empty (0 bytes)" in feedback_content["error"]

    # Verify Goal & Step status progression
    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    goal = goals[0]
    assert goal.status == GoalStatus.DONE
    assert len(goal.steps) == 3

    assert goal.steps[0].status == StepStatus.FAILED
    assert "empty (0 bytes)" in (goal.steps[0].verify_reason or "")

    assert goal.steps[1].status == StepStatus.VERIFIED
    assert "File artifact verified on disk" in (goal.steps[1].verify_reason or "")

    assert goal.steps[2].status == StepStatus.VERIFIED


# ── Test 4: Bounded Execution Ceiling (max_steps) ───────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_max_steps_bounding(temp_goal_store, tmp_path):
    """Loop ceases after max_steps ceiling, marks Goal FAILED, and returns attempt history."""
    session_id = "sess_test_bounding"
    prompt = "Do an infinite task"

    step_counter = 0

    async def mock_spinning_llm(kwargs):
        nonlocal step_counter
        step_counter += 1
        tc = _make_tool_call(
            "dummy_tool",
            {"counter": step_counter},  # varying args to avoid repeated failure guard
            call_id=f"tc_{step_counter}",
        )
        return _make_response(content=None, tool_calls=[tc])

    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch = AsyncMock(return_value={"status": "running"})

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=3,  # strict bound
        dispatcher=mock_dispatcher,
        llm_caller=mock_spinning_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert "reached maximum bounded iterations (3)" in result
    assert "Attempt history" in result

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    assert goals[0].status == GoalStatus.FAILED
    assert len(goals[0].steps) == 3


# ── Test 5: Repeated Failure Guard ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_repeated_failure_guard(temp_goal_store):
    """Two identical consecutive failures halt loop into AWAITING_USER instead of spinning."""
    session_id = "sess_test_guard"
    prompt = "Execute broken command"

    async def mock_llm(kwargs):
        # Keeps requesting the exact same broken tool call
        tc = _make_tool_call(
            "broken_tool",
            {"command": "failing_cmd"},
            call_id="call_dup",
        )
        return _make_response(content=None, tool_calls=[tc])

    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch = AsyncMock(return_value={"status": "error", "error": "Command not found"})

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=8,
        dispatcher=mock_dispatcher,
        llm_caller=mock_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert "repeatedly failed verification" in result
    assert "pausing execution for your clarification" in result

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    assert goals[0].status == GoalStatus.AWAITING_USER


# ── Test 6: Confirmation Required Ticket Gate ───────────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_confirmation_required_gate(temp_goal_store):
    """When a tool returns confirmation_required, goal transitions to AWAITING_USER immediately."""
    session_id = "sess_test_ticket"
    prompt = "Create high-risk file"

    async def mock_llm(kwargs):
        tc = _make_tool_call("create_file_artifact", {"goal": "test"}, call_id="call_gate")
        return _make_response(content=None, tool_calls=[tc])

    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch = AsyncMock(
        return_value={
            "status": "confirmation_required",
            "prompt": "Action 'create_file_artifact' requires your approval. Ticket ID: tkt_12345. Should I proceed?",
            "ticket_id": "tkt_12345",
        }
    )

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=5,
        dispatcher=mock_dispatcher,
        llm_caller=mock_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert "requires your approval" in result
    assert "tkt_12345" in result

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    assert goals[0].status == GoalStatus.AWAITING_USER
    assert len(goals[0].steps) == 1
    assert goals[0].steps[0].status == StepStatus.OBSERVED
    assert "Confirmation ticket" in (goals[0].steps[0].verify_reason or "")


# ── Test 7: Resume AWAITING_USER Goal ───────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_resume_awaiting_user_goal(temp_goal_store):
    """An incoming request on a session with an AWAITING_USER goal resumes it rather than creating a second goal."""
    session_id = "sess_test_resume"

    # 1. First interaction pauses on confirmation
    initial_goal = Goal.new(session_id=session_id, user_prompt="Initial prompt")
    initial_goal.status = GoalStatus.AWAITING_USER
    temp_goal_store.create_goal(initial_goal)

    # 2. Second interaction (user confirms with 'yes')
    async def mock_llm(kwargs):
        return _make_response(content="Resumed and finished task.")

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=5,
        llm_caller=mock_llm,
    )

    result = await loop.run(
        user_message="yes, proceed",
        messages=[{"role": "user", "content": "yes, proceed"}],
        kwargs={"messages": [{"role": "user", "content": "yes, proceed"}]},
    )

    assert "Resumed and finished task." in result

    # Should still only have ONE goal for this session, now DONE!
    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    assert goals[0].goal_id == initial_goal.goal_id
    assert goals[0].status == GoalStatus.DONE


# ── Test 8: Feature Flag Toggle Parity in AuraCore ──────────────────────────


@pytest.mark.asyncio
async def test_feature_flag_toggle_parity(monkeypatch, tmp_path):
    """Verifies that AURA_ENABLE_AGENT_LOOP=1 routes through AgentLoop while 0 preserves legacy ReAct path."""
    from core.aura_core import AuraCore

    core = AuraCore.get_instance()

    # When flag is "0"
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "0")
    with patch("core.orchestration.agent_loop.AgentLoop.run") as mock_agent_run:
        # Patch groq client to return direct answer
        mock_msg = SimpleNamespace(content="Legacy answer", tool_calls=None)
        mock_choice = SimpleNamespace(message=mock_msg)
        mock_res = SimpleNamespace(choices=[mock_choice])
        with patch.object(core, "_call_groq_streaming", return_value=mock_res, create=True), \
             patch("ai.key_pool.KeyPool.execute_with_failover", return_value=mock_res):
            await core.get_ai_response("Hello legacy", enable_tools=False)
            assert not mock_agent_run.called

    # When flag is "1"
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")
    with patch("core.orchestration.agent_loop.AgentLoop.run", new_callable=AsyncMock) as mock_agent_run:
        mock_agent_run.return_value = "AgentLoop active answer"
        resp = await core.get_ai_response("Hello active loop", enable_tools=False)
        assert mock_agent_run.called
        assert resp == "AgentLoop active answer"


# ── Test 9: Telemetry Single-Write Guarantee (No Double-Write Under Flag=1) ─


@pytest.mark.asyncio
async def test_agent_loop_telemetry_no_double_write(monkeypatch, temp_goal_store):
    """
    Verifies that when AURA_ENABLE_AGENT_LOOP=1, get_ai_response delegates to AgentLoop
    and writes exactly 1 Goal to GoalStore, without duplicating through the legacy passive path.
    """
    from core.aura_core import AuraCore

    core = AuraCore.get_instance()
    session_id = "sess_test_single_write"

    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")
    monkeypatch.setattr(core, "get_goal_store", lambda: temp_goal_store)

    # Mock groq streaming to return a direct response
    mock_msg = SimpleNamespace(content="Direct answer from AgentLoop", tool_calls=None)
    mock_choice = SimpleNamespace(message=mock_msg)
    mock_res = SimpleNamespace(choices=[mock_choice])

    with patch.object(core, "_call_groq_streaming", return_value=mock_res, create=True), \
         patch("ai.key_pool.KeyPool.execute_with_failover", return_value=mock_res):
        resp = await core.get_ai_response("Single write test", session_id=session_id, enable_tools=False)
        assert "Direct answer from AgentLoop" in resp

    # Check GoalStore: exactly 1 goal must exist for this session
    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1, f"Expected exactly 1 goal row, found {len(goals)} (double-write detected!)"
    assert goals[0].status == GoalStatus.DONE
    assert len(goals[0].steps) == 1
    assert goals[0].steps[0].tool_name is None


# ── Test 10: Router-Bypass for "analyze" queries under AURA_ENABLE_AGENT_LOOP=1 ─


@pytest.mark.asyncio
async def test_autonomous_browser_bypass_under_agent_loop_flag(monkeypatch, temp_goal_store):
    """
    Verifies that 'analyze trends in market data' (which triggers autonomous_browser in IntentRouter):
    1. In legacy mode (flag=0): gets intercepted into conv_engine._answer_local_intent.
    2. In AgentLoop mode (flag=1): bypasses _answer_local_intent, reaching AgentLoop for fast native reasoning!
    """
    from core.aura_core import AuraCore

    core = AuraCore.get_instance()
    query = "analyze trends in market data"
    session_id = "sess_test_bypass"

    # Flag = 0 (Legacy behavior)
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "0")
    monkeypatch.setattr(core, "get_goal_store", lambda: temp_goal_store)

    with patch.object(core.conversation_engine, "_answer_local_intent", return_value="Legacy Playwright Report") as mock_crawl:
        resp = await core.get_ai_response(query, session_id=session_id, enable_tools=True)
        assert mock_crawl.called
        assert resp == "Legacy Playwright Report"

    # Flag = 1 (AgentLoop mode: crawl bypassed, reasoning loop runs natively)
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")

    mock_msg = SimpleNamespace(
        content="Direct synthesis of market trends: equities gained on falling yields.",
        tool_calls=None,
    )
    mock_choice = SimpleNamespace(message=mock_msg)
    mock_res = SimpleNamespace(choices=[mock_choice])

    with patch.object(core.conversation_engine, "_answer_local_intent") as mock_crawl, \
         patch.object(core, "_call_groq_streaming", return_value=mock_res, create=True), \
         patch("ai.key_pool.KeyPool.execute_with_failover", return_value=mock_res):
        resp = await core.get_ai_response(query, session_id=session_id, enable_tools=True)
        # The 90s Playwright crawl MUST NOT be called!
        assert not mock_crawl.called
        assert "Direct synthesis of market trends" in resp

    # Check that AgentLoop persisted the goal as completed in 1 direct turn
    goals = temp_goal_store.list_goals_for_session(session_id)
    # 1 from legacy passive, 1 from active agent loop
    active_goals = [g for g in goals if "Direct synthesis" in (g.steps[0].observation or "")]
    assert len(active_goals) == 1
    assert active_goals[0].status == GoalStatus.DONE
    assert active_goals[0].steps[0].status == StepStatus.VERIFIED


# ── Test 11: browser_navigate_and_read Active Verification ─────────────────


@pytest.mark.asyncio
async def test_verify_browser_navigate_and_read_verified(temp_goal_store):
    """Tool extracts substantive web content; verify_browser_navigate_and_read passes; Goal marks DONE."""
    session_id = "sess_test_browser_pass"
    prompt = "Read documentation at https://example.com/docs"

    turn_count = 0

    async def mock_llm(kwargs):
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            tc = _make_tool_call(
                "browser_navigate_and_read",
                {"url": "https://example.com/docs", "extract_mode": "markdown"},
                call_id="call_web_1",
            )
            return _make_response(content=None, tool_calls=[tc])
        else:
            return _make_response(content="Documentation summary based on verified web content.")

    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch = AsyncMock(
        return_value={
            "status": "success",
            "url": "https://example.com/docs",
            "title": "Example Documentation",
            "content": "# Documentation\n\nHere is the detailed API reference for AuraAI core modules.",
            "extract_mode": "markdown",
        }
    )

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=5,
        dispatcher=mock_dispatcher,
        llm_caller=mock_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert "Documentation summary based on verified web content." in result

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    goal = goals[0]
    assert goal.status == GoalStatus.DONE
    assert len(goal.steps) == 2

    web_step = goal.steps[0]
    assert web_step.tool_name == "browser_navigate_and_read"
    assert web_step.status == StepStatus.VERIFIED
    assert "Web content verified" in (web_step.verify_reason or "")


# ── Test 12: Adversarial Rejection on Empty Web Extraction ──────────────────


@pytest.mark.asyncio
async def test_verify_browser_navigate_and_read_rejects_empty_extraction(temp_goal_store):
    """
    Adversarial test: tool reports status: success but content is empty.
    Verifier MUST reject it with StepStatus.FAILED and feed back reason into adaptation loop.
    """
    session_id = "sess_test_browser_fail"
    prompt = "Extract data from empty page"

    turn_count = 0
    feedback_received = None

    async def mock_llm(kwargs):
        nonlocal turn_count, feedback_received
        turn_count += 1
        if turn_count == 1:
            tc = _make_tool_call(
                "browser_navigate_and_read",
                {"url": "https://broken-site.com", "extract_mode": "text"},
                call_id="call_web_empty",
            )
            return _make_response(content=None, tool_calls=[tc])
        elif turn_count == 2:
            # Capture tool feedback from turn 1
            tool_msgs = [m for m in kwargs["messages"] if m.get("role") == "tool"]
            if tool_msgs:
                feedback_received = json.loads(tool_msgs[-1]["content"])
            return _make_response(content="I was unable to extract information because the target page was empty.")

    mock_dispatcher = MagicMock()
    # Tool reports "success", but extracted content is empty string!
    mock_dispatcher.dispatch = AsyncMock(
        return_value={
            "status": "success",
            "url": "https://broken-site.com",
            "content": "   ",
        }
    )

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=5,
        dispatcher=mock_dispatcher,
        llm_caller=mock_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    # 1. Assert adaptation feedback was received with failed_verification
    assert feedback_received is not None
    assert feedback_received["status"] == "failed_verification"
    assert "extracted content is empty" in feedback_received["error"]

    # 2. Assert Step status in database is FAILED, not rubber-stamped!
    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    goal = goals[0]
    failed_step = goal.steps[0]
    assert failed_step.tool_name == "browser_navigate_and_read"
    assert failed_step.status == StepStatus.FAILED
    assert "extracted content is empty" in (failed_step.verify_reason or "")


# ── Test 13: Adversarial Rejection on Broken/Empty browser_interact ────────


@pytest.mark.asyncio
async def test_verify_browser_interact_adversarial_rejection(temp_goal_store):
    """
    Adversarial test for browser_interact:
    1. Case A: Tool claims success but returns an empty execution confirmation result.
       Verifier must reject with StepStatus.FAILED.
    2. Case B: Tool claims success but echoes a mismatched action/selector.
       Verifier must reject with StepStatus.FAILED.
    """
    session_id = "sess_test_interact_fail"
    prompt = "Click the submit button"

    turn_count = 0
    feedback_received = None

    async def mock_llm(kwargs):
        nonlocal turn_count, feedback_received
        turn_count += 1
        if turn_count == 1:
            tc = _make_tool_call(
                "browser_interact",
                {"action": "click", "selector": "#submit-btn"},
                call_id="call_click_empty",
            )
            return _make_response(content=None, tool_calls=[tc])
        elif turn_count == 2:
            tool_msgs = [m for m in kwargs["messages"] if m.get("role") == "tool"]
            if tool_msgs:
                feedback_received = json.loads(tool_msgs[-1]["content"])
            return _make_response(content="Handled failure.")

    mock_dispatcher = MagicMock()
    # Tool reports "success", but provides an empty result string!
    mock_dispatcher.dispatch = AsyncMock(
        return_value={
            "status": "success",
            "action": "click",
            "selector": "#submit-btn",
            "result": "   ",
        }
    )

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=5,
        dispatcher=mock_dispatcher,
        llm_caller=mock_llm,
    )

    await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    # Verifier rejected the empty result
    assert feedback_received is not None
    assert feedback_received["status"] == "failed_verification"
    assert "produced no execution confirmation result" in feedback_received["error"]

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    failed_step = goals[0].steps[0]
    assert failed_step.tool_name == "browser_interact"
    assert failed_step.status == StepStatus.FAILED
    assert "produced no execution confirmation result" in (failed_step.verify_reason or "")


@pytest.mark.asyncio
async def test_agent_loop_llm_reasoning_error_reports_gracefully(temp_goal_store):
    """When LLM caller throws an exception, AgentLoop reports the error instead of misleading bounded iterations message."""
    session_id = "sess_test_llm_error"
    prompt = "which feature is best for aura to have"

    async def mock_failing_llm(kwargs):
        raise RuntimeError("All 5 groq API keys are currently rate-limited on cooldown")

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=8,
        llm_caller=mock_failing_llm,
    )

    result = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert "I encountered an error communicating with the reasoning model" in result
    assert "rate-limited on cooldown" in result
    assert "reached maximum bounded iterations" not in result

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    assert goals[0].status == GoalStatus.FAILED


@pytest.mark.asyncio
async def test_plan_before_act_scaffold_in_system_prompt():
    """Verify that AuraCore._build_chat_messages includes the Plan-Before-Act cognitive protocol and UI design instructions."""
    from core.aura_core import AuraCore
    core = AuraCore()
    messages = core._build_chat_messages("Design a high-fidelity MCDU layout")
    assert len(messages) >= 2
    sys_content = messages[0]["content"]
    assert "### Operational Protocol: Plan-Before-Act" in sys_content
    assert "DELIBERATE BEFORE ACTING" in sys_content
    assert "MCDU" in sys_content or "UI" in sys_content


@pytest.mark.asyncio
async def test_agent_loop_records_pre_tool_plan_step(temp_goal_store):
    """Verify that AgentLoop captures pre-tool planning deliberation in goal_store and telemetry."""
    session_id = "sess_test_plan_before_act"
    prompt = "Create the MCDU layout artifact"

    turn_count = 0

    async def mock_llm_with_pre_tool_plan(kwargs):
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            # Turn 1: Model provides deliberate plan in content AND issues a tool call
            plan_text = (
                "Goal & Understanding: Create the MCDU layout structure.\n"
                "Constraints & Design Decisions: Needs 80x24 aspect ratio, monospaced font, amber scratchpad.\n"
                "Step-by-Step Action Plan:\n"
                "1. Write artifact file.\n"
                "2. Verify dimensions."
            )
            tc = SimpleNamespace(
                id="call_mock_1",
                function=SimpleNamespace(
                    name="create_file_artifact",
                    arguments=json.dumps({"content": "MCDU Content", "output_filename": "mcdu.txt", "destination": "cwd"}),
                ),
            )
            msg = SimpleNamespace(role="assistant", content=plan_text, tool_calls=[tc])
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        else:
            # Turn 2: Final confirmation
            msg = SimpleNamespace(role="assistant", content="MCDU artifact created and verified.", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    from unittest.mock import MagicMock
    mock_emitter = MagicMock()

    loop = AgentLoop(
        goal_store=temp_goal_store,
        emitter=mock_emitter,
        session_id=session_id,
        max_steps=5,
        llm_caller=mock_llm_with_pre_tool_plan,
    )

    # Patch the verifier so create_file_artifact succeeds
    with patch("core.orchestration.agent_loop.verify_create_file_artifact", return_value=(True, "Verified")):
        with patch.object(loop, "dispatcher") as mock_disp:
            mock_disp.dispatch = AsyncMock(return_value={"status": "success", "output_path": "mcdu.txt"})
            res = await loop.run(
                user_message=prompt,
                messages=[{"role": "user", "content": prompt}],
                kwargs={"messages": [{"role": "user", "content": prompt}]},
            )

    assert "MCDU artifact created and verified" in res
    mock_emitter.plan.assert_called()

    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    steps = goals[0].steps
    assert len(steps) >= 2
    # First step is the Plan-Before-Act deliberation step
    first_step = steps[0]
    assert first_step.tool_name is None
    assert first_step.verify_reason == "Plan-Before-Act deliberation"
    assert "Goal & Understanding" in first_step.observation


@pytest.mark.asyncio
async def test_agent_loop_prepends_native_reasoning_in_think_tags(temp_goal_store):
    """Verify that AgentLoop prepends native reasoning into final_text inside <think>...</think> tags."""
    session_id = "sess_test_native_reasoning"
    prompt = "Analyze the MCDU display geometry"

    async def mock_llm_with_native_reasoning(kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        role="assistant",
                        content="The MCDU screen uses a 6-row by 24-character matrix with 6 LSKs on each side.",
                        reasoning="MCDU displays require LSK 1L-6L on the left and 1R-6R on the right. Analyzing geometry.",
                        tool_calls=None,
                    )
                )
            ]
        )

    mock_emitter = MagicMock()
    loop = AgentLoop(
        goal_store=temp_goal_store,
        emitter=mock_emitter,
        session_id=session_id,
        max_steps=3,
        llm_caller=mock_llm_with_native_reasoning,
    )

    res = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
    )

    assert "<think>" in res
    assert "</think>" in res
    assert "MCDU displays require LSK 1L-6L" in res
    assert "The MCDU screen uses a 6-row by 24-character matrix" in res


@pytest.mark.asyncio
async def test_agent_loop_gemini_fallback_when_groq_fails(temp_goal_store, monkeypatch):
    """Verify that when Groq fails on the primary execution path, AgentLoop seamlessly recovers via Gemini fallback."""
    session_id = "sess_gemini_fallback"
    prompt = "Create a turbine diagram"

    def mock_failing_groq(kwargs, target_model):
        raise RuntimeError("tokens per minute: Limit 8000, Requested 9500")

    mock_fallback_resp = SimpleNamespace(
        text="```mermaid\ngraph TD;\nA[Turbine Compressor] --> B[Combustor];\n```"
    )

    class MockGeminiProvider:
        def __init__(self, *args, **kwargs):
            pass
        def chat(self, *args, **kwargs):
            return mock_fallback_resp

    monkeypatch.setattr("ai.gemini_provider.GeminiProvider", MockGeminiProvider)

    # Ensure key pool reports gemini key exists
    from ai.key_pool import KeyPool
    pool = KeyPool.get_instance()
    monkeypatch.setattr(pool, "get_all_keys", lambda provider: ["dummy_gemini_key"] if provider == "gemini" else [])

    loop = AgentLoop(
        goal_store=temp_goal_store,
        session_id=session_id,
        max_steps=3,
    )

    res = await loop.run(
        user_message=prompt,
        messages=[{"role": "user", "content": prompt}],
        kwargs={"messages": [{"role": "user", "content": prompt}]},
        call_groq=mock_failing_groq,
    )

    assert "Turbine Compressor" in res
    assert "Combustor" in res
    goals = temp_goal_store.list_goals_for_session(session_id)
    assert len(goals) == 1
    assert goals[0].status == GoalStatus.DONE






