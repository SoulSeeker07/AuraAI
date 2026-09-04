"""
progress_events.py

Lightweight progress/"thinking" event system for Aura.

Goal: turn the current blank wait (CLI/GUI show nothing until the final
answer) into a live stream of intermediate step events, the same way Claude's UI shows
"thinking" + tool-call steps before the final response, with a
collapse/expand toggle.

This module is transport-agnostic: it doesn't know about CLI, GUI, or voice.
It provides a place to emit ProgressEvents from inside AuraCore's
ReAct loop and MasterOrchestrator's DAG pipeline, and a place for any
number of listeners (CLI printer, GUI stream, log file, telemetry bridge)
to subscribe.

Wire-up points:
  - src/core/aura_core.py          -> ReAct loop & process_request
  - src/core/orchestration/master_orchestrator.py -> 7-stage DAG pipeline
  - src/core/tools/aura_tool_registry.py -> execute_tool() dispatch
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class EventStatus(str, Enum):
    STARTED = "started"
    PROGRESS = "progress"
    DONE = "done"
    ERROR = "error"


class EventType(str, Enum):
    """High-level category, lets CLI/GUI apply different icons/styling."""
    PLAN = "plan"           # task_decomposer / plan graph stages
    VALIDATE = "validate"   # validate_plan_graph gating
    TOOL_CALL = "tool_call"  # AuraToolRegistry.execute_tool dispatch
    REACT_TURN = "react_turn"  # AuraCore ReAct loop turn boundary
    THINKING = "thinking"   # raw reasoning tokens, if the model exposes them
    GENERATING = "generating"  # final answer/response token streaming
    APPROVAL = "approval"   # CryptographicApprovalAuthority gate/wait
    INFO = "info"           # anything else worth surfacing


@dataclass
class ProgressEvent:
    label: str                      # short human-readable line, e.g. "Calling browser_navigate_and_read"
    event_type: EventType = EventType.INFO
    status: EventStatus = EventStatus.PROGRESS
    detail: Optional[str] = None    # optional longer text (only shown when expanded)
    request_id: Optional[str] = None  # correlates events to one user request
    step_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    duration_ms: Optional[float] = None  # filled in on the matching DONE event

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "event_type": self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "detail": self.detail,
            "request_id": self.request_id,
            "step_id": self.step_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


Listener = Callable[[ProgressEvent], None]


class ProgressEmitter:
    """
    Thread-safe pub/sub for ProgressEvents.

    One instance per running request is simplest (create it in
    AuraCore.process_request(), pass it down through the call stack,
    tear it down when the response is finalized). A single process-wide
    instance also works if you filter by request_id downstream.
    """

    def __init__(self) -> None:
        self._listeners: list[Listener] = []
        self._lock = threading.Lock()
        # Optional asyncio queue, useful for feeding process_request_stream()
        self._async_queue: Optional[asyncio.Queue] = None
        self._events_history: list[ProgressEvent] = []

    def subscribe(self, callback: Listener) -> Callable[[], None]:
        """Returns an unsubscribe function."""
        with self._lock:
            self._listeners.append(callback)

        def _unsubscribe() -> None:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)

        return _unsubscribe

    def attach_async_queue(self) -> asyncio.Queue:
        """Call this from an async context (e.g. process_request_stream) to
        get a queue that fills up as events are emitted."""
        self._async_queue = asyncio.Queue()
        return self._async_queue

    @property
    def history(self) -> list[ProgressEvent]:
        with self._lock:
            return list(self._events_history)

    def emit(self, event: ProgressEvent) -> None:
        with self._lock:
            self._events_history.append(event)
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(event)
            except Exception:
                # A broken listener (e.g. GUI panel closed) should never
                # take down the actual request.
                pass
        if self._async_queue is not None:
            try:
                self._async_queue.put_nowait(event)
            except Exception:
                pass
        try:
            from gui.signals import app_signals
            level = "ERROR" if event.status == EventStatus.ERROR else "INFO"
            app_signals.log_message.emit(f"[{event.event_type.value.upper()}] {event.label}", level)
        except Exception:
            pass

    # Convenience emitters -------------------------------------------------

    def plan(self, label: str, **kw) -> None:
        self.emit(ProgressEvent(label=label, event_type=EventType.PLAN, **kw))

    def tool_call(self, label: str, **kw) -> None:
        self.emit(ProgressEvent(label=label, event_type=EventType.TOOL_CALL, **kw))

    def turn(self, label: str, **kw) -> None:
        self.emit(ProgressEvent(label=label, event_type=EventType.REACT_TURN, **kw))

    def info(self, label: str, **kw) -> None:
        self.emit(ProgressEvent(label=label, event_type=EventType.INFO, **kw))

    def validate(self, label: str, **kw) -> None:
        self.emit(ProgressEvent(label=label, event_type=EventType.VALIDATE, **kw))

    def thinking(self, token_or_thought: str, **kw) -> None:
        self.emit(ProgressEvent(label=token_or_thought, event_type=EventType.THINKING, status=EventStatus.PROGRESS, **kw))

    def generating(self, token: str, **kw) -> None:
        self.emit(ProgressEvent(label=token, event_type=EventType.GENERATING, status=EventStatus.PROGRESS, **kw))

    @contextmanager
    def track_step(
        self,
        label: str,
        event_type: EventType = EventType.INFO,
        detail: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """
        Synchronous context manager that emits STARTED on enter and DONE/ERROR on exit,
        with duration_ms filled in automatically.
        """
        step_id = uuid.uuid4().hex[:8]
        start = time.time()
        self.emit(ProgressEvent(
            label=label, event_type=event_type, status=EventStatus.STARTED,
            detail=detail, request_id=request_id, step_id=step_id,
        ))
        try:
            yield
        except Exception as exc:
            self.emit(ProgressEvent(
                label=label, event_type=event_type, status=EventStatus.ERROR,
                detail=str(exc), request_id=request_id, step_id=step_id,
                duration_ms=(time.time() - start) * 1000,
            ))
            raise
        else:
            self.emit(ProgressEvent(
                label=label, event_type=event_type, status=EventStatus.DONE,
                detail=detail, request_id=request_id, step_id=step_id,
                duration_ms=(time.time() - start) * 1000,
            ))

    @asynccontextmanager
    async def track_step_async(
        self,
        label: str,
        event_type: EventType = EventType.INFO,
        detail: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """
        Asynchronous context manager variant of track_step.
        """
        step_id = uuid.uuid4().hex[:8]
        start = time.time()
        self.emit(ProgressEvent(
            label=label, event_type=event_type, status=EventStatus.STARTED,
            detail=detail, request_id=request_id, step_id=step_id,
        ))
        try:
            yield
        except Exception as exc:
            self.emit(ProgressEvent(
                label=label, event_type=event_type, status=EventStatus.ERROR,
                detail=str(exc), request_id=request_id, step_id=step_id,
                duration_ms=(time.time() - start) * 1000,
            ))
            raise
        else:
            self.emit(ProgressEvent(
                label=label, event_type=event_type, status=EventStatus.DONE,
                detail=detail, request_id=request_id, step_id=step_id,
                duration_ms=(time.time() - start) * 1000,
            ))


# ---------------------------------------------------------------------------
# CLI renderer: subscribe this to an emitter and it prints live progress
# lines, similar to Claude's collapsed "Thinking..." indicator.
# ---------------------------------------------------------------------------

class CLIProgressRenderer:
    """
    Usage:
        emitter = ProgressEmitter()
        renderer = CLIProgressRenderer(expanded=False)
        emitter.subscribe(renderer)
        ... run the request ...
        renderer.finish()  # print a one-line summary
    """

    ICONS = {
        EventStatus.STARTED: "⏳",
        EventStatus.PROGRESS: "…",
        EventStatus.DONE: "✅",
        EventStatus.ERROR: "❌",
    }

    def __init__(self, expanded: bool = False) -> None:
        self.expanded = expanded
        self._step_count = 0
        self._start_time = time.time()
        self.history: list[ProgressEvent] = []
        # Reasoning & response streaming container state
        self._current_turn_label: str = ""
        self._current_turn_start: float = time.time()
        self._current_turn_first_token_time: Optional[float] = None
        self._thinking_buffer: list[str] = []
        self._thinking_token_count: int = 0
        self._last_thinking_render_time: float = 0.0
        self._generating_token_count: int = 0
        self._last_generating_render_time: float = 0.0
        # Background TTFT wait ticker
        self._turn_active: bool = False
        self._ticker_thread: Optional[threading.Thread] = None
        self._ticker_stop_event = threading.Event()

    def _start_ticker(self) -> None:
        if self.expanded:
            return
        self._stop_ticker()
        self._turn_active = True
        self._ticker_stop_event.clear()
        self._ticker_thread = threading.Thread(target=self._ticker_loop, daemon=True)
        self._ticker_thread.start()

    def _stop_ticker(self) -> None:
        self._turn_active = False
        self._ticker_stop_event.set()
        if self._ticker_thread and self._ticker_thread.is_alive():
            self._ticker_thread.join(timeout=0.1)
        self._ticker_thread = None

    def _ticker_loop(self) -> None:
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        while not self._ticker_stop_event.is_set() and self._turn_active:
            if self._current_turn_first_token_time is None:
                elapsed = time.time() - self._current_turn_start
                frame = spinner_frames[idx % len(spinner_frames)]
                idx += 1
                base_label = self._current_turn_label or "Reasoning"
                display_line = f"\r{frame} {base_label} (waiting for model... {elapsed:.1f}s)"
                print(f"{display_line:<60}", end="", flush=True)
            self._ticker_stop_event.wait(0.08)

    def __call__(self, event: ProgressEvent) -> None:
        self.history.append(event)
        if event.status == EventStatus.STARTED and event.event_type not in (EventType.THINKING, EventType.GENERATING):
            self._step_count += 1

        icon = self.ICONS.get(event.status, "•")

        # ── EventType.THINKING (High-frequency reasoning tokens) ──
        if event.event_type == EventType.THINKING:
            now = time.time()
            if self._current_turn_first_token_time is None:
                self._current_turn_first_token_time = now

            self._thinking_buffer.append(event.label)
            self._thinking_token_count += 1

            if not self.expanded:
                # Throttle collapsed terminal re-renders (max once per 100ms)
                if (now - self._last_thinking_render_time) >= 0.1 or (self._thinking_token_count % 15 == 0):
                    gen_elapsed = now - self._current_turn_first_token_time
                    base_label = self._current_turn_label or "Reasoning"
                    display_line = f"\r⏳ {base_label} ({self._thinking_token_count} tokens | {gen_elapsed:.1f}s streaming)"
                    print(f"{display_line:<60}", end="", flush=True)
                    self._last_thinking_render_time = now
            return

        # ── EventType.GENERATING (High-frequency response tokens) ──
        if event.event_type == EventType.GENERATING:
            now = time.time()
            if self._current_turn_first_token_time is None:
                self._current_turn_first_token_time = now

            self._generating_token_count += 1

            if not self.expanded:
                if (now - self._last_generating_render_time) >= 0.1 or (self._generating_token_count % 15 == 0):
                    gen_elapsed = now - self._current_turn_first_token_time
                    display_line = f"\r⏳ Generating response ({self._generating_token_count} tokens | {gen_elapsed:.1f}s streaming)"
                    print(f"{display_line:<60}", end="", flush=True)
                    self._last_generating_render_time = now
            return

        # ── EventType.REACT_TURN Boundaries ──
        if event.event_type == EventType.REACT_TURN:
            if event.status == EventStatus.STARTED:
                self._current_turn_label = event.label
                self._current_turn_start = time.time()
                self._current_turn_first_token_time = None
                self._thinking_buffer.clear()
                self._thinking_token_count = 0
                self._generating_token_count = 0
                self._start_ticker()

                if self.expanded:
                    print(f"⏳ [react_turn] {event.label}", flush=True)
                return

            elif event.status in (EventStatus.DONE, EventStatus.ERROR):
                self._stop_ticker()
                now = time.time()
                dur_ms = event.duration_ms if event.duration_ms is not None else (now - self._current_turn_start) * 1000
                th_cnt = self._thinking_token_count
                gen_cnt = self._generating_token_count

                # Calculate TTFT vs Streaming times
                if self._current_turn_first_token_time is not None:
                    ttft_ms = max(0.0, (self._current_turn_first_token_time - self._current_turn_start) * 1000)
                    stream_ms = max(0.0, (now - self._current_turn_first_token_time) * 1000)
                else:
                    ttft_ms = dur_ms
                    stream_ms = 0.0

                # Construct precise turn summary & detail
                timing_str = f"TTFT: {ttft_ms:.0f}ms | Streaming: {stream_ms:.0f}ms"
                if gen_cnt > 0 and th_cnt > 0:
                    turn_summary = f"{event.label} ({th_cnt} thought tokens, {gen_cnt} response tokens)"
                    event.detail = event.detail or f"{timing_str} | Thinking: {th_cnt} tokens | Generated: {gen_cnt} tokens"
                elif gen_cnt > 0:
                    turn_summary = f"{event.label.replace('Reasoning', 'Response Generated')} ({gen_cnt} tokens)"
                    event.detail = event.detail or f"{timing_str} | Generated: {gen_cnt} tokens"
                elif th_cnt > 0:
                    turn_summary = f"{event.label} ({th_cnt} thought tokens)"
                    event.detail = event.detail or f"{timing_str} | Thinking: {th_cnt} tokens"
                else:
                    turn_summary = event.label

                if self.expanded:
                    # Flush buffered thinking block cleanly before closing turn
                    if self._thinking_buffer:
                        thought_text = "".join(self._thinking_buffer).strip()
                        if thought_text:
                            print("  ┌─ 💭 Thinking Trace ───────────────────────────────────────", flush=True)
                            for line in thought_text.splitlines():
                                print(f"  │ {line}", flush=True)
                            print("  └──────────────────────────────────────────────────────────", flush=True)
                    
                    status_icon = "✅" if event.status == EventStatus.DONE else "❌"
                    print(f"{status_icon} [react_turn] {turn_summary} ({dur_ms:.0f}ms)", flush=True)
                else:
                    status_icon = "✅" if event.status == EventStatus.DONE else "❌"
                    print(f"\r{status_icon} {turn_summary:<60}", end="", flush=True)
                return

        # ── Standard Discrete Step Events (TOOL_CALL, PLAN, VALIDATE, INFO) ──
        if self.expanded:
            type_val = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
            line = f"{icon} [{type_val}] {event.label}"
            if event.detail:
                line += f" — {event.detail}"
            if event.duration_ms is not None:
                line += f" ({event.duration_ms:.0f}ms)"
            print(line, flush=True)
        else:
            clean_label = event.label[:60] if len(event.label) > 60 else event.label
            print(f"\r{icon} {clean_label:<60}", end="", flush=True)

    def render_full_trace(self) -> None:
        """Print the complete history trace cleanly."""
        print("\n" + "─" * 60)
        print("                 EXECUTION STEP TRACE")
        print("─" * 60)
        for ev in self.history:
            if ev.event_type in (EventType.THINKING, EventType.GENERATING):
                continue  # Exclude raw token fragments from high-level step trace
            icon = self.ICONS.get(ev.status, "•")
            status_val = ev.status.value if hasattr(ev.status, "value") else str(ev.status)
            type_val = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
            line = f"  {icon} [{type_val}] ({status_val}) {ev.label}"
            if ev.detail:
                line += f" -> {ev.detail}"
            if ev.duration_ms is not None:
                line += f" ({ev.duration_ms:.1f}ms)"
            print(line)
        print("─" * 60)

    def finish(self) -> None:
        self._stop_ticker()
        elapsed = time.time() - self._start_time
        if not self.expanded:
            print("\r" + " " * 75 + "\r", end="", flush=True)  # clean up status line
        print(f"✨ (Completed in {elapsed:.2f}s across {self._step_count} intermediate steps)")
