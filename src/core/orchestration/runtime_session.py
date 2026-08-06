"""
Runtime Session Base Class
Location: src/core/orchestration/runtime_session.py

Common base dataclass for all domain execution sessions across Aura AI:
- EngineeringSession
- BrowserSession
- DesktopSession
- ResearchSession

Establishes a uniform interface for session progress, worker tracking,
timeline history, artifacts, observations, and pause/resume lifecycle methods.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .artifact import Artifact
from .observation import Observation


class SessionStatus(str, Enum):
    """Lifecycle status of a RuntimeSession."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class RuntimeWorkerState:
    """State tracking for a worker within a RuntimeSession."""

    worker_id: str
    name: str
    worker_type: str
    status: str = "IDLE"
    current_action: str = ""
    progress: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "worker_type": self.worker_type,
            "status": self.status,
            "current_action": self.current_action,
            "progress": self.progress,
            "updated_at": self.updated_at,
        }


@dataclass
class RuntimeSession:
    """
    Abstract base dataclass for all domain runtime sessions.
    """

    session_id: str = field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:10]}")
    domain: str = "general"  # "engineering", "browser", "desktop", "research"
    goal: str = ""
    status: SessionStatus = SessionStatus.RUNNING
    progress: int = 0  # 0 to 100%
    current_action: str = "Initializing session..."
    workers: list[RuntimeWorkerState] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def update_progress(self, progress: int, current_action: str | None = None) -> None:
        """Update progress percentage and current action string."""
        self.progress = max(0, min(100, progress))
        if current_action:
            self.current_action = current_action
        self.updated_at = datetime.now().isoformat()
        self.record_timeline_event(
            "progress_update", f"Progress: {self.progress}% - {self.current_action}"
        )

    def add_observation(self, observation: Observation) -> None:
        """Append an observation to the session."""
        self.observations.append(observation)
        self.updated_at = datetime.now().isoformat()

    def add_artifact(self, artifact: Artifact) -> None:
        """Append an artifact to the session."""
        self.artifacts.append(artifact)
        self.updated_at = datetime.now().isoformat()

    def record_timeline_event(
        self, event_type: str, description: str, data: dict[str, Any] | None = None
    ) -> None:
        """Record an event in the session timeline."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "description": description,
            "data": data or {},
        }
        self.timeline.append(event)

    def pause(self) -> None:
        """Pause the session."""
        self.status = SessionStatus.PAUSED
        self.current_action = "Session paused by user request."
        self.updated_at = datetime.now().isoformat()
        self.record_timeline_event("pause", "Session paused")

    def resume(self) -> None:
        """Resume the session."""
        self.status = SessionStatus.RUNNING
        self.current_action = "Resuming execution..."
        self.updated_at = datetime.now().isoformat()
        self.record_timeline_event("resume", "Session resumed")

    def cancel(self) -> None:
        """Cancel the session."""
        self.status = SessionStatus.CANCELLED
        self.current_action = "Session cancelled."
        self.updated_at = datetime.now().isoformat()
        self.record_timeline_event("cancel", "Session cancelled")

    def mark_completed(self, message: str = "Completed successfully.") -> None:
        """Mark the session as completed."""
        self.status = SessionStatus.COMPLETED
        self.progress = 100
        self.current_action = message
        self.updated_at = datetime.now().isoformat()
        self.record_timeline_event("completed", message)

    def mark_failed(self, error_message: str) -> None:
        """Mark the session as failed."""
        self.status = SessionStatus.FAILED
        self.current_action = f"Failed: {error_message}"
        self.updated_at = datetime.now().isoformat()
        self.record_timeline_event("failed", error_message)

    def get_summary(self) -> str:
        """Generate human-readable summary of session status."""
        return (
            f"[{self.domain.upper()}] Session {self.session_id}\n"
            f"Goal: {self.goal}\n"
            f"Status: {self.status.value} ({self.progress}%)\n"
            f"Action: {self.current_action}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "domain": self.domain,
            "goal": self.goal,
            "status": (
                self.status.value if isinstance(self.status, Enum) else self.status
            ),
            "progress": self.progress,
            "current_action": self.current_action,
            "workers": [w.to_dict() for w in self.workers],
            "observations": [obs.to_dict() for obs in self.observations],
            "artifacts": [art.to_dict() for art in self.artifacts],
            "timeline": self.timeline,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
