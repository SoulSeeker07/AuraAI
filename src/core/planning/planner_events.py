"""
Planner Event Bus & Event Stream Definitions
Decoupled event publisher for Planner lifecycle events across all agent subsystems.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlannerEvent:
    event_type: str
    plan_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    payload: dict[str, Any] = field(default_factory=dict)


class PlannerEventBus:
    """
    Decoupled event bus for subscribing to and publishing Planner events.
    """

    def __init__(self):
        self._listeners: dict[str, list[Callable[[PlannerEvent], None]]] = {}

    def subscribe(
        self, event_type: str, callback: Callable[[PlannerEvent], None]
    ) -> None:
        """Subscribe to a specific event type or '*' for all events."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def publish(
        self, event_type: str, plan_id: str, payload: dict[str, Any] | None = None
    ) -> None:
        """Publish an event to all subscribers."""
        event = PlannerEvent(
            event_type=event_type, plan_id=plan_id, payload=payload or {}
        )
        targets = self._listeners.get(event_type, []) + self._listeners.get("*", [])

        for cb in targets:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Error in PlannerEvent listener for '{event_type}': {e}")
