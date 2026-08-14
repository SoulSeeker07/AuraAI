"""
Short-term conversational memory for AuraAI.

This is the "still talking to you" layer: a rolling window of the
*current* voice session. It's what makes follow-ups like "what about
the other one" or "make it louder" work without re-explaining context.

It deliberately knows nothing about semantics or embeddings - it's just
a deque with a silence-based session boundary. All the "remember this
forever" logic lives in long_term_memory.py.
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

    - Keeps the last `max_turns` turns verbatim (exact recall of what was
      just said - cheap, no embedding/search involved).
    - Auto-expires the session after `session_timeout` seconds of silence.
      This is the "new conversation" boundary for a voice assistant: there's
      no explicit "end chat" button like there is in a text UI, so silence
      is the signal.
    - When the buffer overflows, the oldest turns are handed off to be
      folded into a rolling summary (done by MemoryManager, which owns the
      Groq client) rather than just dropped.
    """

    def __init__(self, max_turns: int = 12, session_timeout: float = 300.0):
        self.max_turns = max_turns
        self.session_timeout = session_timeout  # seconds of silence -> new session
        self.turns: deque[Turn] = deque()
        self.rolling_summary: str = ""
        self.last_activity: float = time.time()
        self.session_id: str = self._new_session_id()
        self._pending_summary_input: list[Turn] = []

    def _new_session_id(self) -> str:
        return f"sess_{int(time.time() * 1000)}"

    def _maybe_expire_session(self) -> bool:
        """Returns True if the silence gap started a brand new session."""
        if time.time() - self.last_activity > self.session_timeout:
            self.turns.clear()
            self.rolling_summary = ""
            self.session_id = self._new_session_id()
            return True
        return False

    def add_turn(self, role: str, content: str) -> bool:
        """Add a turn to the buffer. Returns True if this started a new session."""
        new_session = self._maybe_expire_session()
        self.turns.append(Turn(role=role, content=content))
        self.last_activity = time.time()

        if len(self.turns) > self.max_turns:
            self._compact()
        return new_session

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
        """Messages ready to hand straight to Groq's chat.completions.create()."""
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
