from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from core.logger import get_logger

logger = get_logger("event_bus")

EventCallback = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class EventBus:
    def __init__(self):
        self._listeners: dict[str, list[EventCallback]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        self._listeners[event_name].append(callback)
        logger.debug("Subscribed listener to event: %s", event_name)

    def unsubscribe(self, event_name: str, callback: EventCallback) -> None:
        listeners = self._listeners.get(event_name, [])
        if callback in listeners:
            listeners.remove(callback)
            logger.debug("Unsubscribed listener from event: %s", event_name)

    def publish(self, event_name: str, **payload: Any) -> None:
        event = Event(event_name, payload)
        if event_name == "live_screen.frame_captured":
            logger.debug("Event published: %s", event_name)
        else:
            logger.info("Event published: %s", event_name)

        for callback in list(self._listeners.get(event_name, [])):
            try:
                callback(event)
            except Exception:
                logger.exception("Event listener failed for event: %s", event_name)
