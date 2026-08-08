"""
Goal Manager — Long-Term Goal Tracking
======================================

Right now Aura reasons per request. Humans don't.

"Build Aura OS" isn't a single request — it becomes a long-running goal.

Goal Manager tracks:
    Goal → Status → Progress → Active Sessions → Dependencies → Artifacts → Next Steps → Completion Criteria
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Goal:
    """A long-term goal being tracked."""

    goal_id: str = field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:8]}")
    description: str = ""
    status: str = "active"  # active, in_progress, completed, abandoned
    progress: float = 0.0
    sub_goals: list[str] = field(default_factory=list)
    active_sessions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    completion_criteria: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "status": self.status,
            "progress": self.progress,
            "sub_goals": self.sub_goals,
            "active_sessions": self.active_sessions,
            "dependencies": self.dependencies,
            "artifacts": self.artifacts,
            "next_steps": self.next_steps,
            "completion_criteria": self.completion_criteria,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class GoalManager:
    """
    Tracks long-term goals across multiple requests and sessions.

    Without this, Aura only thinks one prompt at a time.
    """

    def __init__(self):
        self._goals: dict[str, Goal] = {}

    def create_goal(
        self,
        description: str,
        completion_criteria: list[str] | None = None,
        sub_goals: list[str] | None = None,
    ) -> Goal:
        """Create a new long-term goal."""
        goal = Goal(
            description=description,
            completion_criteria=completion_criteria or [],
            sub_goals=sub_goals or [],
        )
        self._goals[goal.goal_id] = goal
        logger.info(f"GoalManager created goal [{goal.goal_id}]: '{description}'")
        return goal

    def get_goal(self, goal_id: str) -> Goal | None:
        """Get a goal by ID."""
        return self._goals.get(goal_id)

    def list_goals(self, status: str | None = None) -> list[Goal]:
        """List all goals, optionally filtered by status."""
        if status:
            return [g for g in self._goals.values() if g.status == status]
        return list(self._goals.values())

    def update_progress(self, goal_id: str, progress: float) -> None:
        """Update goal progress."""
        goal = self._goals.get(goal_id)
        if goal:
            goal.progress = min(progress, 100.0)
            goal.updated_at = datetime.now().isoformat()

    def add_session(self, goal_id: str, session_id: str) -> None:
        """Associate a runtime session with a goal."""
        goal = self._goals.get(goal_id)
        if goal and session_id not in goal.active_sessions:
            goal.active_sessions.append(session_id)
            goal.updated_at = datetime.now().isoformat()

    def add_artifact(self, goal_id: str, artifact_id: str) -> None:
        """Associate an artifact with a goal."""
        goal = self._goals.get(goal_id)
        if goal and artifact_id not in goal.artifacts:
            goal.artifacts.append(artifact_id)
            goal.updated_at = datetime.now().isoformat()

    def complete_goal(self, goal_id: str) -> None:
        """Mark a goal as completed."""
        goal = self._goals.get(goal_id)
        if goal:
            goal.status = "completed"
            goal.progress = 100.0
            goal.updated_at = datetime.now().isoformat()
            logger.info(f"GoalManager completed goal [{goal_id}]")

    def find_goal_for_request(self, user_input: str) -> Goal | None:
        """Find an active goal that matches the current request."""
        input_lower = user_input.lower()
        for goal in self._goals.values():
            if goal.status in ("active", "in_progress"):
                if goal.description.lower() in input_lower:
                    return goal
        return None


__all__ = ["GoalManager", "Goal"]
