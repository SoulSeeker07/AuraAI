from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

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

    def unsubscribe(self, event_name: str, callback: EventCallback) -> None:
        lst = self._listeners.get(event_name, [])
        if callback in lst:
            lst.remove(callback)

    def publish(self, event_name: str, **payload: Any) -> None:
        event = Event(event_name, payload)
        for callback in list(self._listeners.get(event_name, [])):
            try:
                callback(event)
            except Exception:
                # swallow - listeners should handle logging
                pass
