"""
paused_session.py

Holds at most one in-memory paused browser session (CAPTCHA/2FA hand-back or ticket pause)
per process, with a TTL. This is what makes `resume_browser` actually
resume the SAME browser window and SAME conversation context, instead of
launching a fresh browser and hoping cookies carried over from a
completely different tab.

This only works because Aura runs as one long-lived process (same pattern
as ContextStore's singleton). If your deployment ever restarts per
request, you'd need to persist to disk instead and accept that "resume"
means reconnecting to a fresh browser at the saved URL.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TTL_SECONDS = 600  # 10 minutes, matches the old system's session TTL


@dataclass
class PausedSession:
    session: Any                       # the still-OPEN BrowserSession — do not close it
    messages: List[Dict[str, Any]]     # full conversation history so far
    goal: str
    model: str
    max_steps_remaining: int
    challenge_type: Optional[str]
    step_log: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    # Populated only when the pause is a safety-gate block (not a CAPTCHA):
    # lets confirm_ticket() replay the EXACT blocked tool call rather than
    # asking the model to re-derive one from scratch and hoping it matches.
    pending_ticket_id: Optional[str] = None
    pending_tool: Optional[Dict[str, Any]] = None


class PausedSessionStore:
    _instance: Optional["PausedSessionStore"] = None

    def __init__(self):
        self._paused: Optional[PausedSession] = None

    @classmethod
    def get_instance(cls) -> "PausedSessionStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def save(self, paused: PausedSession) -> None:
        # Only one paused session at a time. If something is already
        # paused, close its browser before replacing it — otherwise you
        # leak an open Chromium window every time a second goal pauses.
        if self._paused is not None and self._paused != paused:
            logger.warning("[PausedSessionStore] Replacing an existing paused session — closing its browser.")
            self._safe_close(self._paused)
        self._paused = paused

    def take(self) -> Optional[PausedSession]:
        """Pop and return the paused session if present and unexpired."""
        if self._paused is None:
            return None
        if time.time() - self._paused.created_at > TTL_SECONDS:
            logger.info("[PausedSessionStore] Paused session expired (TTL %ds) — closing browser.", TTL_SECONDS)
            self._safe_close(self._paused)
            self._paused = None
            return None
        paused, self._paused = self._paused, None
        return paused

    def take_for_ticket(self, ticket_id: str) -> Optional[PausedSession]:
        """
        Return the paused session ONLY if it's the one waiting on this
        exact ticket_id — otherwise leave it untouched. This matters
        because the same single slot can hold either a CAPTCHA hand-back
        or a ticket block; confirming the wrong/stale ticket_id must not
        destroy an unrelated paused session sitting there.
        """
        if self._paused is None:
            return None
        if time.time() - self._paused.created_at > TTL_SECONDS:
            self._safe_close(self._paused)
            self._paused = None
            return None
        if self._paused.pending_ticket_id != ticket_id:
            return None
        paused, self._paused = self._paused, None
        return paused

    def has_pending(self) -> bool:
        if self._paused is None:
            return False
        if time.time() - self._paused.created_at > TTL_SECONDS:
            self._safe_close(self._paused)
            self._paused = None
            return False
        return True

    @staticmethod
    def _safe_close(paused: PausedSession) -> None:
        try:
            paused.session.__exit__(None, None, None)
        except Exception as ex:
            logger.debug("[PausedSessionStore] Error closing stale session: %s", ex)
