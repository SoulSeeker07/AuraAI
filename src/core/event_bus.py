import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger("event_bus")

EventCallback = Callable[["Event"], None]


class Events:
    """Standard system and lifecycle event types for AuraAI."""

    EXECUTION_STARTED = "execution.started"
    EXECUTION_FINISHED = "execution.finished"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    NODE_STATE_CHANGED = "node.state_changed"
    CONFIRMATION_REQUIRED = "confirmation.required"
    TELEMETRY_UPDATE = "telemetry.update"
    ARTIFACT_CREATED = "artifact.created"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"
    REFLECTION_COMPLETED = "reflection.completed"
    LEARNING_COMPLETED = "learning.completed"
    GOAL_UPDATED = "goal.updated"
    SESSION_UPDATED = "session.updated"


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class EventBus:
    _instance: Optional["EventBus"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self):
        self._listeners: dict[str, list[EventCallback]] = defaultdict(list)

    @classmethod
    def get_instance(cls) -> "EventBus":
        """Thread-safe singleton accessor for the process-wide EventBus."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        self._listeners[event_name].append(callback)
        logger.debug("Subscribed listener to event: %s", event_name)

    def unsubscribe(self, event_name: str, callback: EventCallback) -> None:
        listeners = self._listeners.get(event_name, [])
        if callback in listeners:
            listeners.remove(callback)
            logger.debug("Unsubscribed listener from event: %s", event_name)

    def publish(self, event_name: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> None:
        combined_payload = dict(payload or {})
        combined_payload.update(kwargs)
        event = Event(event_name, combined_payload)
        if event_name == "live_screen.frame_captured":
            logger.debug("Event published: %s", event_name)
        else:
            logger.info("Event published: %s", event_name)

        for callback in list(self._listeners.get(event_name, [])):
            try:
                callback(event)
            except Exception:
                logger.exception("Event listener failed for event: %s", event_name)


__all__ = ["Event", "EventBus", "Events", "EventCallback"]
