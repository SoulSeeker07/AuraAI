"""
World Timeline Engine
Location: src/core/orchestration/world_timeline.py

Tracks chronological events across the desktop and browser OS lifecycle:
process starts/closes, tab activations/closes, desktop actions, and session milestones.
Enables queries like 'What changed in the last 15 minutes?' or 'What have you done this session?'.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .ownership_tracker import ResourceOwner

logger = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    """Represents a single chronological event on the OS timeline."""
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    time_epoch: float = field(default_factory=time.time)
    event_type: str = "desktop_action"  # "process_start", "process_close", "tab_open", "tab_focus", "tab_close", "desktop_action"
    description: str = ""
    resource_id: str = ""
    owner: str = ResourceOwner.AURA.value
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "time_epoch": self.time_epoch,
            "event_type": self.event_type,
            "description": self.description,
            "resource_id": self.resource_id,
            "owner": self.owner,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


class WorldTimeline:
    """
    Chronological event log tracking OS and browser state changes over time.
    """

    _instance: WorldTimeline | None = None

    def __init__(self):
        self._events: list[TimelineEvent] = []
        self._logger = logging.getLogger(__name__)

    @classmethod
    def get_instance(cls) -> WorldTimeline:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def record_event(
        self,
        event_type: str,
        description: str,
        resource_id: str = "",
        owner: str = ResourceOwner.AURA.value,
        session_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        """
        Record a new timeline event.
        """
        evt = TimelineEvent(
            event_type=event_type,
            description=description,
            resource_id=resource_id,
            owner=owner,
            session_id=session_id,
            metadata=metadata or {},
        )
        self._events.append(evt)
        self._logger.info(f"TimelineEvent [{event_type}]: {description}")
        return evt

    def get_recent_events(
        self, minutes: int = 15, session_id: str | None = None
    ) -> list[TimelineEvent]:
        """
        Retrieve events recorded within the specified time window or session.
        """
        cutoff = time.time() - (minutes * 60)
        results: list[TimelineEvent] = []
        for evt in self._events:
            if evt.time_epoch >= cutoff:
                if session_id is None or evt.session_id == session_id:
                    results.append(evt)
        return results

    def format_summary(self, minutes: int = 15, session_id: str | None = None) -> str:
        """
        Format a human-readable summary of recent timeline events.
        """
        recent = self.get_recent_events(minutes=minutes, session_id=session_id)
        if not recent:
            return f"No desktop timeline events recorded in the last {minutes} minutes."

        lines = [f"Timeline Summary (Last {minutes} minutes):"]
        for evt in recent:
            ts_short = evt.timestamp.split("T")[-1][:8] if "T" in evt.timestamp else evt.timestamp
            lines.append(f"• [{ts_short}] ({evt.event_type}): {evt.description} (Owner: {evt.owner})")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear timeline events."""
        self._events.clear()
