"""
Short-term conversational memory for AuraAI.

This is the "still talking to you" layer: a rolling window of the
*current* voice session. It's what makes follow-ups like "what about
the other one" or "make it louder" work without re-explaining context.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


class ShortTermMemory:
    """
    Sliding-window buffer for the current conversation session.
    """

    def __init__(self, max_turns: int = 12, session_timeout: float = 300.0):
        self.max_turns = max_turns
        self.session_timeout = session_timeout  # seconds of silence -> new session
        self.turns: deque[Turn] = deque()
        self.rolling_summary: str = ""
        self.last_activity: float = time.time()
        self.session_id: str = self._new_session_id()
        self._pending_summary_input: list[Turn] = []
        # M2: idempotency guard for session-close consolidation.
        # Set True once consolidation fires for this session_id.
        self.session_consolidated: bool = False

    def _new_session_id(self) -> str:
        return f"sess_{int(time.time() * 1000)}"

    def _maybe_expire_session(self) -> tuple[bool, list[Turn]]:
        """
        Check whether the inactivity gap exceeds `session_timeout`.

        Returns:
            (expired, transcript) where:
            - expired:    True if a new session was started.
            - transcript: The turns from the *expired* session (empty list if no expiry).
                          Captured BEFORE the buffer is cleared, so callers can consolidate.
        """
        if time.time() - self.last_activity > self.session_timeout:
            transcript = list(self.turns)   # capture before clearing
            self.turns.clear()
            self.rolling_summary = ""
            self.session_id = self._new_session_id()
            self.session_consolidated = False  # new session starts unconsolidated
            return True, transcript
        return False, []

    def add_user_turn(self, content: str) -> tuple[bool, list[Turn]]:
        """
        Add a user turn to the buffer.
        This is the ONLY place session expiry is checked, because a slow
        assistant execution should not wipe a session.

        Returns:
            (new_session, expired_transcript) — callers may use expired_transcript
            to trigger session-close consolidation.
        """
        new_session, expired_transcript = self._maybe_expire_session()
        self.turns.append(Turn(role="user", content=content))
        self.last_activity = time.time()

        if len(self.turns) > self.max_turns:
            self._compact()
        return new_session, expired_transcript

    def add_assistant_turn(self, content: str) -> None:
        """
        Add an assistant turn to the buffer.
        Does NOT check for session expiry, but DOES update last_activity
        so the next user turn doesn't read the execution time as "silence".
        """
        self.turns.append(Turn(role="assistant", content=content))
        self.last_activity = time.time()

        if len(self.turns) > self.max_turns:
            self._compact()

    def _compact(self):
        """Move overflow turns out so MemoryManager can summarize them."""
        while len(self.turns) > self.max_turns:
            self._pending_summary_input.append(self.turns.popleft())

    def pop_pending_summary_input(self) -> list[Turn]:
        """MemoryManager calls this, summarizes the result, then calls
        set_rolling_summary() with the output."""
        pending, self._pending_summary_input = self._pending_summary_input, []
        return pending

    def set_rolling_summary(self, summary: str):
        self.rolling_summary = summary

    def get_context_messages(self) -> list[dict]:
        """Messages ready for LLM execution."""
        messages = []
        if self.rolling_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"Earlier in this conversation: {self.rolling_summary}",
                }
            )
        messages.extend({"role": t.role, "content": t.content} for t in self.turns)
        return messages

    def get_raw_turns(self) -> list[Turn]:
        """Raw conversational history, useful for ReferenceResolver."""
        return list(self.turns)

    def pop_session_transcript(self) -> list[Turn]:
        """
        M2: Return all current turns as a snapshot for session-close consolidation.
        Does NOT clear the buffer — use this when close_session() is called explicitly
        (not on timeout, where _maybe_expire_session() captures turns before clearing).
        """
        return list(self.turns)
