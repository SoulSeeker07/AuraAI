"""
core/event_bus.py

Simple thread-safe pub/sub Event Bus for Jarvis AI.

Usage:
    from core.event_bus import EventBus

    event_bus = EventBus()

    def on_started(event):
        print(event.name, event.payload)

    event_bus.subscribe(ProcessEvent.PROCESS_STARTED, on_started)
    event_bus.publish(ProcessEvent.PROCESS_STARTED, {"pid": 123, "name": "python.exe"})
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, DefaultDict, Dict, List, Optional


@dataclass
class Event:
    """Represents a single published event."""
    name: Any                              # e.g. a ProcessEvent enum member or plain string
    payload: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """
    Thread-safe synchronous pub/sub event bus.

    - subscribe(event_name, callback): register callback(event) for event_name
    - unsubscribe(event_name, callback): remove a previously registered callback
    - publish(event_name, payload=None, **kwargs): build an Event and notify subscribers
    - clear(event_name=None): remove all subscribers for one event, or every event
    """

    def __init__(self) -> None:
        self._subscribers: DefaultDict[Any, List[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_name: Any, callback: Callable[[Event], None]) -> None:
        """Register a callback for a given event name/type."""
        with self._lock:
            self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: Any, callback: Callable[[Event], None]) -> None:
        """Remove a callback previously registered for event_name."""
        with self._lock:
            callbacks = self._subscribers.get(event_name)
            if callbacks and callback in callbacks:
                callbacks.remove(callback)

    def publish(
        self,
        event_name: Any,
        payload: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Publish an event to all subscribers of event_name.

        payload and kwargs are merged into a single dict available as event.payload.
        Subscribers are called synchronously, on the calling thread.
        """
        merged_payload: Dict[str, Any] = dict(payload) if payload else {}
        merged_payload.update(kwargs)
        event = Event(name=event_name, payload=merged_payload)

        # Snapshot the subscriber list under lock, then call callbacks outside
        # the lock so a slow/blocking subscriber doesn't stall other threads
        # trying to subscribe/publish.
        with self._lock:
            callbacks = list(self._subscribers.get(event_name, []))

        for callback in callbacks:
            try:
                callback(event)
            except Exception as exc:  # noqa: BLE001 - never let one bad subscriber break the bus
                print(f"[EventBus] Subscriber error for event '{event_name}': {exc}")

    def clear(self, event_name: Optional[Any] = None) -> None:
        """Remove all subscribers for a single event, or all events if None."""
        with self._lock:
            if event_name is None:
                self._subscribers.clear()
            else:
                self._subscribers.pop(event_name, None)

    def subscriber_count(self, event_name: Any) -> int:
        """Number of callbacks currently registered for event_name."""
        with self._lock:
            return len(self._subscribers.get(event_name, []))