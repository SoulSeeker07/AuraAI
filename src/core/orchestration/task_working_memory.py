"""
Task Working Memory (Task-Scoped Ephemeral Memory)
Location: src/core/orchestration/task_working_memory.py

Tracks step-by-step state, world observations, hypothesis, and completed actions
for the duration of a single execution goal. Discarded or committed upon task finish.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ActionRecord:
    """Record of a single executed step."""
    step_index: int
    capability: str
    target: str
    goal: str
    success: bool
    observations: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class TaskWorkingMemory:
    """
    Working memory instance created per user request session.
    """

    def __init__(self, goal: str, max_steps: int = 15):
        self.goal: str = goal
        self.max_steps: int = max_steps
        self.step_count: int = 0
        self.completed_actions: list[ActionRecord] = []
        self.current_world_state: dict[str, Any] = {}
        self.current_hypothesis: str = f"Fulfilling goal: {goal}"
        self.is_complete: bool = False
        self.success: bool = False
        self.last_error: str | None = None
        self.created_at: float = time.time()

    def record_step(
        self, capability: str, target: str, goal: str, success: bool, observations: list[str]
    ) -> None:
        """Record the outcome of a single executed action step."""
        self.step_count += 1
        rec = ActionRecord(
            step_index=self.step_count,
            capability=capability,
            target=target,
            goal=goal,
            success=success,
            observations=observations,
        )
        self.completed_actions.append(rec)
        logger.info(
            f"[TaskWorkingMemory] Step {self.step_count}: {capability} on '{target}' -> "
            f"{'SUCCESS' if success else 'FAILED'}"
        )

    def update_world_state(self, snapshot: dict[str, Any]) -> None:
        """Update working memory with latest real-world physical observation snapshot."""
        self.current_world_state.update(snapshot)

    def mark_complete(self, success: bool = True, final_observation: str | None = None) -> None:
        """Mark task execution as complete."""
        self.is_complete = True
        self.success = success
        if final_observation:
            self.current_hypothesis = final_observation

    def get_summary(self) -> dict[str, Any]:
        """Return structured summary of task working memory."""
        return {
            "goal": self.goal,
            "steps_completed": self.step_count,
            "is_complete": self.is_complete,
            "success": self.success,
            "actions": [
                {
                    "step": a.step_index,
                    "capability": a.capability,
                    "success": a.success,
                    "observations": a.observations,
                }
                for a in self.completed_actions
            ],
            "last_world_state": self.current_world_state,
        }
