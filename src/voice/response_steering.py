"""
Response Steering Controller (response.steer)
Location: src/voice/response_steering.py

Implements mid-generation and mid-speech prompt steering. Rather than simply
cancelling an active response (response.cancel), response steering captures the
safe boundary output already emitted to the user, truncates the generation, and
queues the new user instruction as a successor response incorporating previous
context.

Compatible with both:
1. Local cascade pipeline (Groq / FastClient / ContinuousVoiceLoop).
2. Streaming Realtime WebSockets (OpenAI Realtime response.steer / Gemini Live).
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Classification of mid-turn interruption intent."""
    NOOP   = "noop"        # Background noise or continuation echo to ignore
    CANCEL = "cancel"      # Hard stop: abort and remain idle or start fresh ("stop", "cancel", "nevermind")
    STEER  = "steer"       # Directional shift: redirect active response ("actually...", "wait, focus on X instead")
    PAUSE  = "pause"       # Temporarily hold speech output ("pause", "hold on", "wait a sec")
    RESUME = "resume"      # Unpause and resume queued speech ("resume", "continue", "keep going")


@dataclass
class SteerEvent:
    """Represents a steering event payload."""
    event_id: str
    previous_response_id: str
    original_goal: str
    emitted_context: str
    steering_input: str
    timestamp: float = field(default_factory=time.time)
    action: ActionType = ActionType.STEER


class SteerPolicy:
    """Classifies incoming mid-stream utterances into CANCEL, STEER, PAUSE, RESUME, or NOOP."""

    # Strict hard cancel phrases (pause removed — it is its own intent now)
    CANCEL_PHRASES = {
        "stop", "cancel", "shut up", "never mind", "nevermind",
        "quiet", "be quiet", "silence", "halt", "stop talking",
        "stop speaking", "enough", "abort",
    }

    # Pause phrases (exact match only — "hold on, only check X" must still steer)
    PAUSE_PHRASES = {
        "pause", "hold on", "hang on", "wait a sec", "wait a second",
        "give me a sec", "give me a second", "one sec", "one second",
        "hold that thought",
    }

    # Resume phrases (exact match only)
    RESUME_PHRASES = {
        "resume", "continue", "keep going", "go on", "carry on",
        "unpause", "go ahead", "you can continue",
    }

    # High-confidence explicit steering trigger prefixes
    EXPLICIT_STEER_TRIGGERS = (
        "focus on", "switch to", "change to", "only check", "skip to",
        "instead of that", "can you instead", "rather than",
        "no wait", "wait no", "actually no",
    )

    # Conversational filler/hedge words that should NEVER trigger steering on their own
    # Note: "hold on" removed as it is now in PAUSE_PHRASES
    COMMON_FILLERS = {
        "actually", "wait", "um", "uh", "well", "like", "yeah", "okay",
    }

    @classmethod
    def classify(cls, utterance: str) -> ActionType:
        """
        Confidence-gated classification of user interruption into CANCEL, STEER, PAUSE, RESUME, or NOOP.
        Fails closed on ambiguity: filler words without a distinct redirect do NOT steer.
        """
        clean = utterance.strip().lower().rstrip(".,!?")
        if not clean:
            return ActionType.NOOP

        # 1. Exact Pause & Resume matches
        if clean in cls.PAUSE_PHRASES:
            return ActionType.PAUSE
        if clean in cls.RESUME_PHRASES:
            return ActionType.RESUME

        # 2. Hard Cancel: exact phrase or starts with cancel keyword
        if clean in cls.CANCEL_PHRASES or any(clean.startswith(f"{p} ") for p in cls.CANCEL_PHRASES):
            return ActionType.CANCEL

        # 3. Filler-only guard: If the utterance is just a single filler word, fail-closed
        words = clean.split()
        if len(words) == 1 and words[0] in cls.COMMON_FILLERS:
            return ActionType.CANCEL

        # 4. High-Confidence Explicit Steering Triggers
        if any(trigger in clean for trigger in cls.EXPLICIT_STEER_TRIGGERS):
            return ActionType.STEER

        # 5. Leading filler + explicit redirected directive ("wait, actually, do X instead")
        if "instead" in clean:
            return ActionType.STEER

        # 6. Imperative action redirects ("only show me...", "actually, only analyze...", "make it...")
        # Strip leading conversational fillers to inspect the core command
        stripped_cmd = clean
        for filler in ("actually", "wait", "no wait", "hold on", "hey"):
            if stripped_cmd.startswith(f"{filler} ") or stripped_cmd.startswith(f"{filler},"):
                stripped_cmd = stripped_cmd[len(filler):].lstrip(" ,")

        if any(stripped_cmd.startswith(p) for p in ("only ", "just ", "make it ", "dont ", "do not ", "focus on ", "switch to ")):
            return ActionType.STEER

        # 7. Ambiguous / unclassified: Fail-closed to NOOP (do not steer; routes as standard turn)
        return ActionType.NOOP


class VoiceTurn:
    """
    State and synchronization primitives for a single conversational voice turn.
    Manages pause/resume gating without tearing down the private event loop or LLM stream.
    """

    def __init__(self, generation_id: int, response_id: str, goal: str):
        self.generation_id = generation_id
        self.response_id = response_id
        self.goal = goal
        self._pause_event = threading.Event()
        self._pause_event.set()  # set = active/running, cleared = paused
        self.paused_at: float | None = None
        self.is_aborted: bool = False
        self._watchdog_timer: Optional[threading.Timer] = None
        self._abort_callbacks: list[Callable[[], None]] = []

    def on_abort(self, cb: Callable[[], None]) -> None:
        """Register an instantaneous callback invoked when the turn is aborted."""
        if self.is_aborted:
            try:
                cb()
            except Exception:
                pass
        else:
            self._abort_callbacks.append(cb)

    def request_pause(self, timeout_s: float = 45.0, on_timeout: Optional[Callable[[], None]] = None) -> None:
        """Pause audio consumption and start timeout watchdog."""
        self.paused_at = time.time()
        self._pause_event.clear()
        logger.info(f"[VoiceTurn #{self.generation_id}] Paused. Starting {timeout_s}s hold watchdog.")

        if self._watchdog_timer:
            self._watchdog_timer.cancel()
        if on_timeout:
            self._watchdog_timer = threading.Timer(timeout_s, on_timeout)
            self._watchdog_timer.daemon = True
            self._watchdog_timer.start()

    def request_resume(self) -> None:
        """Resume audio consumption and cancel hold watchdog."""
        self.paused_at = None
        if self._watchdog_timer:
            self._watchdog_timer.cancel()
            self._watchdog_timer = None
        self._pause_event.set()
        logger.info(f"[VoiceTurn #{self.generation_id}] Resumed.")

    def is_paused(self) -> bool:
        """Returns True if the turn is currently paused."""
        return not self._pause_event.is_set()

    def wait_if_paused(self, timeout: Optional[float] = None) -> bool:
        """Blocks while paused until resumed or timed out. Returns True if unpaused."""
        return self._pause_event.wait(timeout=timeout)

    def abort(self) -> None:
        """Abort the turn cleanly, fire callbacks, and release any pause wait."""
        self.is_aborted = True
        if self._watchdog_timer:
            self._watchdog_timer.cancel()
            self._watchdog_timer = None
        self._pause_event.set()
        for cb in self._abort_callbacks:
            try:
                cb()
            except Exception as e:
                logger.debug(f"[VoiceTurn] Abort callback error: {e}")
        self._abort_callbacks.clear()


class ResponseSteeringController:
    """
    Manages mid-flight prompt steering for active AI responses.
    
    Coordinates the safe truncation of active TTS and LLM streams, preserves
    partial responses heard by the user, and synthesizes successor prompts.
    """

    def __init__(
        self,
        on_steer_successor: Optional[Callable[[SteerEvent, str], None]] = None,
    ):
        self.on_steer_successor = on_steer_successor
        self._lock = threading.Lock()
        
        # State tracking
        self.active_response_id: Optional[str] = None
        self.active_goal: str = ""
        self.emitted_chunks: list[str] = []
        self._is_active: bool = False
        self._generation_counter: int = 0
        self.current_turn: Optional[VoiceTurn] = None

    def start_response(self, response_id: str, goal: str) -> VoiceTurn:
        """Register the start of an active steerable response generation."""
        with self._lock:
            self._generation_counter += 1
            self.active_response_id = response_id
            self.active_goal = goal
            self.emitted_chunks.clear()
            self._is_active = True
            self.current_turn = VoiceTurn(self._generation_counter, response_id, goal)
            logger.debug(f"[ResponseSteering] Tracking active response: {response_id} ('{goal}')")
            return self.current_turn

    def record_emitted_chunk(self, chunk: str) -> None:
        """Record a prosody chunk that has been sent to audio playback."""
        with self._lock:
            if self._is_active and chunk and chunk.strip():
                self.emitted_chunks.append(chunk.strip())

    def get_emitted_text(self) -> str:
        """Get the concatenated text emitted and heard so far."""
        with self._lock:
            return " ".join(self.emitted_chunks).strip()

    def complete_response(self, response_id: Optional[str] = None) -> None:
        """Mark the active response as completed normally."""
        with self._lock:
            if response_id is None or self.active_response_id == response_id:
                self._is_active = False
                if self.current_turn:
                    self.current_turn.abort()
                    self.current_turn = None

    def is_generating_or_speaking(self) -> bool:
        """Check if an active response is in-flight and steerable."""
        with self._lock:
            return self._is_active

    def is_paused(self) -> bool:
        """Check if the active turn is currently held in pause."""
        with self._lock:
            return self.current_turn is not None and self.current_turn.is_paused()

    def pause_current_turn(self, timeout_s: float = 45.0, on_timeout: Optional[Callable[[], None]] = None) -> bool:
        """Pause audio consumption for the current turn."""
        with self._lock:
            if self._is_active and self.current_turn:
                self.current_turn.request_pause(timeout_s=timeout_s, on_timeout=on_timeout)
                return True
            return False

    def resume_current_turn(self) -> bool:
        """Resume audio consumption for the current turn."""
        with self._lock:
            if self._is_active and self.current_turn and self.current_turn.is_paused():
                self.current_turn.request_resume()
                return True
            return False

    def steer(
        self,
        steering_input: str,
        on_abort_output: Optional[Callable[[], None]] = None,
    ) -> Optional[SteerEvent]:
        """
        Steer the active response in real-time.
        
        1. Classifies the steering utterance (CANCEL vs STEER).
        2. Halts in-flight audio playback via on_abort_output.
        3. Snapshots the safe emitted text boundary.
        4. Compiles the successor steer prompt.
        5. Calls on_steer_successor if registered.
        
        Returns:
            SteerEvent if steering succeeded, None if pure cancel or inactive.
        """
        with self._lock:
            if not self._is_active:
                logger.debug("[ResponseSteering] Steer called but no active response in-flight.")
                return None

            action = SteerPolicy.classify(steering_input)
            response_id = self.active_response_id or f"resp_{int(time.time())}"
            goal = self.active_goal
            emitted = " ".join(self.emitted_chunks).strip()
            
            # Immediately close active response session and abort previous turn
            self._is_active = False
            prev_turn = self.current_turn
            self.current_turn = None

        if prev_turn:
            prev_turn.abort()

        # 1. Abort physical audio output immediately
        if on_abort_output:
            try:
                on_abort_output()
            except Exception as exc:
                logger.warning(f"[ResponseSteering] Output abort callback notice: {exc}")

        if action == ActionType.CANCEL:
            logger.info(f"[ResponseSteering] Utterance classified as CANCEL ('{steering_input}'). Halting.")
            return None

        # 2. Build SteerEvent
        event = SteerEvent(
            event_id=f"steer_{int(time.time() * 1000)}",
            previous_response_id=response_id,
            original_goal=goal,
            emitted_context=emitted,
            steering_input=steering_input,
            action=ActionType.STEER,
        )

        # 3. Construct successor prompt
        successor_prompt = self.build_successor_prompt(event)
        logger.info(
            f"[ResponseSteering] Steer successfully queued! "
            f"Emitted cutoff: '{emitted[:60]}...' -> New direction: '{steering_input}'"
        )

        # 4. Dispatch successor if callback provided
        if self.on_steer_successor:
            self.on_steer_successor(event, successor_prompt)

        return event

    @staticmethod
    def build_successor_prompt(event: SteerEvent) -> str:
        """
        Build a high-cohesion successor prompt that informs the LLM of the redirection
        without losing awareness of what was already communicated to the user.
        """
        emitted_snippet = event.emitted_context
        if len(emitted_snippet) > 300:
            emitted_snippet = "..." + emitted_snippet[-280:]

        if emitted_snippet:
            prompt = (
                f"[SYSTEM: The user interrupted and steered your ongoing response.]\n"
                f"- Original user request: {event.original_goal}\n"
                f"- What you already said aloud before interruption: \"{emitted_snippet}\"\n"
                f"- User steering redirection: \"{event.steering_input}\"\n\n"
                f"TASK: Seamlessly acknowledge the redirection and pivot immediately to answer "
                f"the user's new instruction: '{event.steering_input}'. Do not repeat what was already said."
            )
        else:
            prompt = (
                f"[SYSTEM: User steered task from '{event.original_goal}' to '{event.steering_input}']\n"
                f"Immediately fulfill the redirected instruction: {event.steering_input}"
            )
        return prompt
