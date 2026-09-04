"""
tests/test_progress_events.py

Unit and integration tests for the ProgressEvent emitter, CLIProgressRenderer,
and orchestration hook points.
"""

import asyncio
import pytest
import time
from core.progress_events import (
    EventStatus,
    EventType,
    ProgressEvent,
    ProgressEmitter,
    CLIProgressRenderer,
)


def test_progress_event_dataclass_and_serialization():
    ev = ProgressEvent(
        label="Test step",
        event_type=EventType.TOOL_CALL,
        status=EventStatus.STARTED,
        detail="detail payload",
        request_id="req-123",
    )
    assert ev.label == "Test step"
    assert ev.event_type == EventType.TOOL_CALL
    assert ev.status == EventStatus.STARTED
    assert ev.detail == "detail payload"
    assert ev.request_id == "req-123"
    assert len(ev.step_id) == 8
    assert ev.duration_ms is None

    d = ev.to_dict()
    assert d["label"] == "Test step"
    assert d["event_type"] == "tool_call"
    assert d["status"] == "started"
    assert d["detail"] == "detail payload"
    assert d["request_id"] == "req-123"


def test_progress_emitter_subscription_and_history():
    emitter = ProgressEmitter()
    received = []

    def on_event(event: ProgressEvent):
        received.append(event)

    unsubscribe = emitter.subscribe(on_event)

    emitter.plan("Analyzing query", detail="plan detail")
    emitter.tool_call("Calling tool", detail="tool detail")
    emitter.validate("Validating plan")
    emitter.info("Informational notice")

    assert len(received) == 4
    assert received[0].event_type == EventType.PLAN
    assert received[0].label == "Analyzing query"
    assert received[1].event_type == EventType.TOOL_CALL
    assert received[2].event_type == EventType.VALIDATE
    assert received[3].event_type == EventType.INFO

    # Check emitter history matches
    assert len(emitter.history) == 4
    assert emitter.history[0].label == "Analyzing query"

    # Test unsubscribe
    unsubscribe()
    emitter.plan("Another query")
    assert len(received) == 4
    assert len(emitter.history) == 5


def test_progress_emitter_broken_listener_resilience():
    emitter = ProgressEmitter()
    good_received = []

    def broken_listener(event: ProgressEvent):
        raise RuntimeError("I am broken")

    def good_listener(event: ProgressEvent):
        good_received.append(event)

    emitter.subscribe(broken_listener)
    emitter.subscribe(good_listener)

    # Broken listener must not raise or prevent good_listener from getting the event
    emitter.info("Test message")
    assert len(good_received) == 1
    assert good_received[0].label == "Test message"


def test_progress_emitter_track_step_success():
    emitter = ProgressEmitter()
    events = []
    emitter.subscribe(lambda ev: events.append(ev))

    with emitter.track_step("Execute database query", EventType.TOOL_CALL, detail="SELECT 1"):
        time.sleep(0.01)

    assert len(events) == 2
    started_ev, done_ev = events
    assert started_ev.status == EventStatus.STARTED
    assert started_ev.label == "Execute database query"
    assert started_ev.event_type == EventType.TOOL_CALL

    assert done_ev.status == EventStatus.DONE
    assert done_ev.label == "Execute database query"
    assert done_ev.duration_ms is not None
    assert done_ev.duration_ms > 0
    assert started_ev.step_id == done_ev.step_id


def test_progress_emitter_track_step_error():
    emitter = ProgressEmitter()
    events = []
    emitter.subscribe(lambda ev: events.append(ev))

    with pytest.raises(ValueError, match="fail test"):
        with emitter.track_step("Failing step", EventType.VALIDATE):
            raise ValueError("fail test")

    assert len(events) == 2
    started_ev, error_ev = events
    assert started_ev.status == EventStatus.STARTED
    assert error_ev.status == EventStatus.ERROR
    assert error_ev.detail == "fail test"
    assert error_ev.duration_ms is not None


@pytest.mark.asyncio
async def test_progress_emitter_track_step_async():
    emitter = ProgressEmitter()
    events = []
    emitter.subscribe(lambda ev: events.append(ev))

    async with emitter.track_step_async("Async step", EventType.REACT_TURN):
        await asyncio.sleep(0.01)

    assert len(events) == 2
    assert events[0].status == EventStatus.STARTED
    assert events[1].status == EventStatus.DONE
    assert events[1].duration_ms > 0


@pytest.mark.asyncio
async def test_progress_emitter_async_queue():
    emitter = ProgressEmitter()
    queue = emitter.attach_async_queue()

    emitter.plan("Queue plan")
    emitter.tool_call("Queue tool")

    ev1 = await queue.get()
    assert ev1.label == "Queue plan"
    assert ev1.event_type == EventType.PLAN

    ev2 = await queue.get()
    assert ev2.label == "Queue tool"
    assert ev2.event_type == EventType.TOOL_CALL


def test_cli_progress_renderer_collapsed_and_expanded(capsys):
    emitter = ProgressEmitter()
    collapsed_renderer = CLIProgressRenderer(expanded=False)
    emitter.subscribe(collapsed_renderer)

    emitter.emit(ProgressEvent(label="Doing work", event_type=EventType.PLAN, status=EventStatus.STARTED))
    emitter.emit(ProgressEvent(label="Done work", event_type=EventType.PLAN, status=EventStatus.DONE, duration_ms=12.5))
    collapsed_renderer.finish()

    captured = capsys.readouterr()
    assert "Completed in" in captured.out
    assert "intermediate steps" in captured.out

    # Test expanded mode
    emitter_expanded = ProgressEmitter()
    expanded_renderer = CLIProgressRenderer(expanded=True)
    emitter_expanded.subscribe(expanded_renderer)

    emitter_expanded.emit(ProgressEvent(label="Analyzing", event_type=EventType.PLAN, status=EventStatus.STARTED))
    emitter_expanded.emit(ProgressEvent(label="Calling browser", event_type=EventType.TOOL_CALL, status=EventStatus.DONE, detail="url=https://example.com", duration_ms=50.0))
    expanded_renderer.finish()
    expanded_renderer.render_full_trace()

    captured_exp = capsys.readouterr()
    assert "[plan] Analyzing" in captured_exp.out
    assert "[tool_call] Calling browser" in captured_exp.out
    assert "url=https://example.com" in captured_exp.out
    assert "EXECUTION STEP TRACE" in captured_exp.out


@pytest.mark.asyncio
async def test_tool_registry_and_orchestrator_emitter_hook():
    from core.tools.aura_tool_registry import AuraToolRegistry
    from core.orchestration import MasterOrchestrator

    emitter = ProgressEmitter()
    received = []
    emitter.subscribe(lambda ev: received.append(ev))

    # Test AuraToolRegistry.execute_tool accepts emitter
    res = await AuraToolRegistry.execute_tool(
        "desktop_set_volume", {"level": 50}, emitter=emitter
    )
    assert res is not None

    # Test MasterOrchestrator.process_request_async accepts emitter
    orch = MasterOrchestrator.get_instance()
    res_orch = await orch.process_request_async(
        "what time is it", emitter=emitter
    )
    assert res_orch is not None
    # Check that master orchestrator stages emitted events
    stage_events = [ev for ev in received if ev.event_type in (EventType.PLAN, EventType.INFO, EventType.VALIDATE)]
    assert len(stage_events) > 0


def test_thinking_tokens_collapsed_and_expanded(capsys):
    # 1. Collapsed Mode
    emitter = ProgressEmitter()
    renderer_collapsed = CLIProgressRenderer(expanded=False)
    emitter.subscribe(renderer_collapsed)

    emitter.emit(ProgressEvent(label="Turn 1: Reasoning", event_type=EventType.REACT_TURN, status=EventStatus.STARTED))
    for i in range(20):
        emitter.thinking(f"token_{i} ")
    emitter.emit(ProgressEvent(label="Turn 1: Reasoning", event_type=EventType.REACT_TURN, status=EventStatus.DONE, duration_ms=100.0))
    renderer_collapsed.finish()

    out = capsys.readouterr().out
    assert "20 thought tokens" in out

    # 2. Expanded Mode
    emitter_exp = ProgressEmitter()
    renderer_exp = CLIProgressRenderer(expanded=True)
    emitter_exp.subscribe(renderer_exp)

    emitter_exp.emit(ProgressEvent(label="Turn 1: Reasoning", event_type=EventType.REACT_TURN, status=EventStatus.STARTED))
    emitter_exp.thinking("I need to check the current system volume.\nThen set it.")
    emitter_exp.emit(ProgressEvent(label="Turn 1: Reasoning", event_type=EventType.REACT_TURN, status=EventStatus.DONE, duration_ms=150.0))
    renderer_exp.finish()
    renderer_exp.render_full_trace()

    out_exp = capsys.readouterr().out
    assert "Thinking Trace" in out_exp
    assert "I need to check the current system volume." in out_exp
    assert "EXECUTION STEP TRACE" in out_exp


def test_generating_tokens_collapsed_and_expanded(capsys):
    # 1. Collapsed Mode
    emitter = ProgressEmitter()
    renderer_collapsed = CLIProgressRenderer(expanded=False)
    emitter.subscribe(renderer_collapsed)

    emitter.emit(ProgressEvent(label="Turn 3: Reasoning", event_type=EventType.REACT_TURN, status=EventStatus.STARTED))
    for i in range(25):
        emitter.generating(f"word_{i} ")
    emitter.emit(ProgressEvent(label="Turn 3: Reasoning", event_type=EventType.REACT_TURN, status=EventStatus.DONE, duration_ms=200.0))
    renderer_collapsed.finish()

    out = capsys.readouterr().out
    assert "25 tokens" in out
    assert "Response Generated" in out

    # 2. Expanded Mode with Full Trace
    emitter_exp = ProgressEmitter()
    renderer_exp = CLIProgressRenderer(expanded=True)
    emitter_exp.subscribe(renderer_exp)

    turn_ev = ProgressEvent(label="Turn 3: Reasoning", event_type=EventType.REACT_TURN, status=EventStatus.STARTED)
    emitter_exp.emit(turn_ev)
    for i in range(10):
        emitter_exp.generating(f"token_{i} ")
    emitter_exp.emit(ProgressEvent(label="Turn 3: Reasoning", event_type=EventType.REACT_TURN, status=EventStatus.DONE, duration_ms=100.0))
    renderer_exp.finish()
    renderer_exp.render_full_trace()

    out_exp = capsys.readouterr().out
    assert "Response Generated (10 tokens)" in out_exp
    assert "Generated: 10 tokens" in out_exp
