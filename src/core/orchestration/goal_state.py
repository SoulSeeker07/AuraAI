"""
Goal and Step State Models for AuraAI Agent Loop.
Location: src/core/orchestration/goal_state.py

Defines the core data structures and enums for tracking goals, sequential
ReAct turns (steps), observations, and capability verification outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid


class GoalStatus(str, Enum):
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"                # exhausted bounded attempts, could not verify
    AWAITING_USER = "awaiting_user"  # paused for clarification or approval ticket


class StepStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    OBSERVED = "observed"            # tool returned, not yet verified
    VERIFIED = "verified"            # observation matched expected outcome
    FAILED = "failed"                # tool errored OR verify() rejected it


@dataclass
class Step:
    step_id: str
    goal_id: str
    tool_name: Optional[str]         # None for pure-reasoning / direct answer
    tool_args: dict[str, Any]
    status: StepStatus
    observation: Optional[str] = None   # raw result, truncated for storage
    verify_reason: Optional[str] = None # WHY verify passed/failed — feeds back to LLM
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def new(
        goal_id: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[dict[str, Any]] = None,
        status: StepStatus = StepStatus.PLANNED,
        observation: Optional[str] = None,
        verify_reason: Optional[str] = None,
    ) -> Step:
        return Step(
            step_id=f"step_{uuid.uuid4().hex[:12]}",
            goal_id=goal_id,
            tool_name=tool_name,
            tool_args=tool_args if tool_args is not None else {},
            status=status,
            observation=observation,
            verify_reason=verify_reason,
        )


@dataclass
class Goal:
    goal_id: str
    session_id: str                  # caller-owned session identity (e.g. sess_gui_..., sess_voice_...)
    user_prompt: str
    status: GoalStatus
    steps: list[Step] = field(default_factory=list)
    max_steps: int = 8               # bounded execution ceiling
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def new(session_id: str, user_prompt: str, max_steps: int = 8) -> Goal:
        return Goal(
            goal_id=f"goal_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            user_prompt=user_prompt,
            status=GoalStatus.ACTIVE,
            max_steps=max_steps,
        )
