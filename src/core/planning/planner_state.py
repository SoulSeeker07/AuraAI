"""
Planner State Machine Definitions
Explicit state lifecycle for execution plans across all agent subsystems.
"""

from datetime import datetime
from enum import Enum


class PlanState(Enum):
    """Execution plan lifecycle states."""

    CREATED = "created"
    ANALYZED = "analyzed"
    PLANNED = "planned"
    OPTIMIZED = "optimized"
    EXECUTING = "executing"
    WAITING = "waiting"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanStateTracker:
    """Tracks state transitions and history for a plan."""

    def __init__(self, initial_state: PlanState = PlanState.CREATED):
        self._current_state = initial_state
        self._history: list[tuple[PlanState, str]] = [
            (initial_state, datetime.now().isoformat())
        ]

    @property
    def current_state(self) -> PlanState:
        return self._current_state

    def transition_to(self, new_state: PlanState, reason: str | None = None) -> bool:
        """Record a state transition."""
        if self._current_state == new_state:
            return True

        self._current_state = new_state
        self._history.append((new_state, datetime.now().isoformat()))
        return True

    def get_history(self) -> list[tuple[PlanState, str]]:
        return self._history.copy()
