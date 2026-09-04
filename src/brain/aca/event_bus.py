"""
Event Bus — Decoupled Communication (DEPRECATED)
================================================
NOTE: This module is deprecated. Use `core.event_bus` instead.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable
from typing import Any

from core.event_bus import Event, EventBus as CoreEventBus, Events

warnings.warn(
    "brain.aca.event_bus is deprecated and scheduled for removal; use core.event_bus instead.",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)


class EventBus:
    """
    Deprecated backward-compatibility adapter for `core.event_bus.EventBus`.
    """

    def __init__(self, core_bus: CoreEventBus | None = None):
        logger.warning(
            "[DEPRECATION] brain.aca.event_bus.EventBus is deprecated. "
            "Forwarding calls to core.event_bus.EventBus."
        )
        self._core_bus = core_bus or CoreEventBus.get_instance()
        self._adapters: dict[tuple[str, Callable], Callable] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe a handler to an event type (adapting dict payload)."""
        def _adapted_callback(event: Event) -> None:
            try:
                handler(event.payload)
            except Exception as e:
                logger.error(f"EventBus adapter: handler for '{event_type}' failed: {e}")

        self._adapters[(event_type, handler)] = _adapted_callback
        self._core_bus.subscribe(event_type, _adapted_callback)

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Publish an event to all subscribers via the core EventBus."""
        self._core_bus.publish(event_type, payload=data or {})

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        adapted = self._adapters.pop((event_type, handler), None)
        if adapted:
            self._core_bus.unsubscribe(event_type, adapted)


__all__ = ["EventBus", "Events"]

