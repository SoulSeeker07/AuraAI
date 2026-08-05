"""
Native Windows Layer Events
Event system for desktop operations.
"""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .native_exceptions import EventPublishError


class EventType(Enum):
    """Native event types"""

    # Window events
    WINDOW_ACTIVATED = "window_activated"
    WINDOW_DEACTIVATED = "window_deactivated"
    WINDOW_CLOSING = "window_closing"
    WINDOW_CLOSED = "window_closed"
    WINDOW_CREATED = "window_created"
    WINDOW_MOVED = "window_moved"
    WINDOW_RESIZED = "window_resized"
    WINDOW_MINIMIZED = "window_minimized"
    WINDOW_MAXIMIZED = "window_maximized"
    WINDOW_RESTORED = "window_restored"

    # Clipboard events
    CLIPBOARD_CHANGED = "clipboard_changed"

    # Display events
    DISPLAY_CHANGED = "display_changed"
    DISPLAY_ADDED = "display_added"
    DISPLAY_REMOVED = "display_removed"
    DISPLAY_RESOLUTION_CHANGED = "display_resolution_changed"

    # Process events
    PROCESS_CREATED = "process_created"
    PROCESS_TERMINATED = "process_terminated"
    PROCESS_STARTED = "process_started"
    PROCESS_STOPPED = "process_stopped"

    # Power events
    POWER_STATE_CHANGED = "power_state_changed"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_RESTART = "system_restart"
    SYSTEM_SLEEP = "system_sleep"
    SYSTEM_LOCK = "system_lock"
    SYSTEM_LOGOFF = "system_logoff"

    # Audio events
    AUDIO_DEVICE_CHANGED = "audio_device_changed"
    AUDIO_VOLUME_CHANGED = "audio_volume_changed"

    # Network events
    NETWORK_INTERFACE_CHANGED = "network_interface_changed"
    NETWORK_CONNECTED = "network_connected"
    NETWORK_DISCONNECTED = "network_disconnected"

    # Registry events
    REGISTRY_KEY_CHANGED = "registry_key_changed"

    # Service events
    SERVICE_STATE_CHANGED = "service_state_changed"
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"

    # Desktop context events
    DESKTOP_CONTEXT_UPDATED = "desktop_context_updated"
    WORKSPACE_CHANGED = "workspace_changed"


@dataclass
class NativeEvent:
    """Native event data"""

    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    source: str = "native"
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "source": self.source,
            "data": self.data,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)

    def __repr__(self) -> str:
        return f"<NativeEvent: {self.event_type.value} at {self.timestamp:.3f}>"


class EventListener:
    """Base class for event listeners"""

    def on_event(self, event: NativeEvent) -> None:
        """Handle incoming events"""
        pass


class NativeEventBus:
    """
    Centralized event bus for native operations.
    All managers publish events through this bus.
    """

    _instance: Optional["NativeEventBus"] = None
    _listeners: list[EventListener] = []
    _event_history: list[NativeEvent] = []
    _max_history: int = 1000

    def __new__(cls) -> "NativeEventBus":
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the event bus"""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._initialized_listeners: set[EventListener] = set()
            self._lock = False

    def publish(self, event: NativeEvent) -> None:
        """Publish an event to all listeners"""
        if self._lock:
            raise EventPublishError(
                "Event bus is locked for publication", "event_publish", details=event
            )

        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Notify all listeners
        for listener in self._listeners:
            try:
                listener.on_event(event)
            except Exception as e:
                print(f"Error in event listener: {e}")

    def subscribe(self, listener: EventListener) -> None:
        """Subscribe a listener to events"""
        if listener in self._initialized_listeners:
            return
        self._listeners.append(listener)
        self._initialized_listeners.add(listener)

    def unsubscribe(self, listener: EventListener) -> None:
        """Unsubscribe a listener"""
        if listener in self._initialized_listeners:
            self._listeners.remove(listener)
            self._initialized_listeners.remove(listener)

    def get_recent_events(
        self, event_type: EventType | None = None, limit: int = 10
    ) -> list[NativeEvent]:
        """Get recent events, optionally filtered by type"""
        events = self._event_history

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history"""
        self._event_history.clear()

    def lock(self) -> None:
        """Lock the event bus for publication"""
        self._lock = True

    def unlock(self) -> None:
        """Unlock the event bus"""
        self._lock = False


# Global event bus instance
_event_bus = NativeEventBus()


def get_event_bus() -> NativeEventBus:
    """Get the global event bus instance"""
    return _event_bus
