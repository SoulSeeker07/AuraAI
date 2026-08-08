"""
Session-Scoped Confirmation
Location: src/core/orchestration/confirmation.py

An ActionPlanConfirmation is attached to an AgentSession when ExecutionPolicy
returns ASK_USER. The next user turn resolves it via MasterOrchestrator,
not via AuraCore's raw string-matching.

This means every confirmation has:
    - A parent session_id for audit
    - A typed ActionPlan it's waiting to approve
    - A 120-second TTL so stale prompts auto-expire
    - A clear resolved / answer state

Replaces: raw "yes"/"no" check in aura_core.process_request()
Scales to: "Delete 2,000 files?", "git push?", "checkout cart?" etc.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..planning.action_plan import ActionPlan


@dataclass
class ActionPlanConfirmation:
    """
    A pending user confirmation attached to an AgentSession.

    Fields
    ------
    session_id  : Parent AgentSession ID
    action_plan : The ActionPlan waiting for yes/no approval
    prompt      : Human-readable prompt shown to the user
    created_at  : monotonic timestamp (for TTL check)
    resolved    : True once the user answered
    answer      : "yes" | "no" — set when resolved
    """

    session_id: str
    action_plan: ActionPlan
    prompt: str
    created_at: float = field(default_factory=time.monotonic)
    resolved: bool = False
    answer: str | None = None
    remaining_subtasks: list[Any] = field(default_factory=list)

    _TTL_SECONDS: float = field(default=120.0, init=False, repr=False, compare=False)

    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > 120.0

    def resolve(self, user_answer: str) -> None:
        """Mark this confirmation as resolved with the user's answer."""
        self.resolved = True
        self.answer = user_answer.strip().lower()

    @property
    def is_yes(self) -> bool:
        return self.answer in [
            "yes",
            "y",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
            "open",
            "another",
        ]

    @property
    def is_no(self) -> bool:
        return self.answer in [
            "no",
            "n",
            "nope",
            "nah",
            "cancel",
            "stop",
            "don't",
            "dont",
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "plan_id": self.action_plan.plan_id,
            "action": self.action_plan.action,
            "target": self.action_plan.target,
            "prompt": self.prompt,
            "resolved": self.resolved,
            "answer": self.answer,
            "expired": self.is_expired(),
        }
