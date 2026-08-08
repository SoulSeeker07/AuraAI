"""
Event Bus — Decoupled Communication
===================================

Instead of:
    Execution → ArtifactManager

Use events:
    ExecutionFinished → ArtifactManager → Learning → GUI → Logger → RuntimeSession

Nothing knows who is listening.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """
    Simple publish/subscribe event bus.

    Components publish events. Other components subscribe.
    No component knows who is listening.
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe a handler to an event type."""
        self._subscribers[event_type].append(handler)
        logger.debug(f"EventBus: subscribed handler to '{event_type}'")

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Publish an event to all subscribers."""
        data = data or {}
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(data)
            except Exception as e:
                logger.error(f"EventBus: handler for '{event_type}' failed: {e}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)


# Common event types
class Events:
    """Standard event types for the ACA."""

    EXECUTION_STARTED = "execution.started"
    EXECUTION_FINISHED = "execution.finished"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    ARTIFACT_CREATED = "artifact.created"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"
    REFLECTION_COMPLETED = "reflection.completed"
    LEARNING_COMPLETED = "learning.completed"
    GOAL_UPDATED = "goal.updated"
    SESSION_UPDATED = "session.updated"


__all__ = ["EventBus", "Events"]
