"""
RuntimeSession — Source of Truth for Every Execution
=====================================================

Every execution belongs to one RuntimeSession.

Examples:
    DesktopSession
    BrowserSession
    ResearchSession
    EngineeringSession
    VoiceSession

This is the source of truth for status, pause/resume, cancellation,
artifacts, and progress.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .task_graph import TaskGraph, TaskNode

logger = logging.getLogger(__name__)


@dataclass
class RuntimeSession:
    """
    A single execution session — the source of truth for status.

    Every execution belongs to exactly one RuntimeSession.
    """

    session_id: str = field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:8]}")
    goal: str = ""
    session_type: str = "standard"  # standard, desktop, browser, research, engineering, voice
    status: str = "pending"  # pending, running, paused, completed, failed, cancelled
    task_graph: TaskGraph | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    progress: float = 0.0
    current_node: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Mark the session as running."""
        self.status = "running"
        self.updated_at = datetime.now().isoformat()
        logger.info(f"RuntimeSession [{self.session_id}] started: '{self.goal}'")

    def pause(self) -> None:
        """Pause the session."""
        self.status = "paused"
        self.updated_at = datetime.now().isoformat()
        logger.info(f"RuntimeSession [{self.session_id}] paused")

    def resume(self) -> None:
        """Resume the session."""
        self.status = "running"
        self.updated_at = datetime.now().isoformat()
        logger.info(f"RuntimeSession [{self.session_id}] resumed")

    def complete(self) -> None:
        """Mark the session as completed."""
        self.status = "completed"
        self.progress = 100.0
        self.updated_at = datetime.now().isoformat()
        logger.info(f"RuntimeSession [{self.session_id}] completed")

    def fail(self, reason: str = "") -> None:
        """Mark the session as failed."""
        self.status = "failed"
        self.updated_at = datetime.now().isoformat()
        logger.warning(f"RuntimeSession [{self.session_id}] failed: {reason}")

    def cancel(self) -> None:
        """Cancel the session."""
        self.status = "cancelled"
        self.updated_at = datetime.now().isoformat()
        logger.info(f"RuntimeSession [{self.session_id}] cancelled")

    def update_progress(self, progress: float) -> None:
        """Update progress percentage."""
        self.progress = min(progress, 100.0)
        self.updated_at = datetime.now().isoformat()

    # ── Artifacts ───────────────────────────────────────────────────────────

    def add_artifact(self, artifact: dict[str, Any]) -> None:
        """Add an artifact to the session."""
        if "artifact_id" not in artifact:
            artifact["artifact_id"] = f"art_{uuid.uuid4().hex[:8]}"
        if "created_at" not in artifact:
            artifact["created_at"] = datetime.now().isoformat()
        self.artifacts.append(artifact)
        self.updated_at = datetime.now().isoformat()

    def get_artifacts_by_type(self, artifact_type: str) -> list[dict[str, Any]]:
        """Get artifacts by type."""
        return [a for a in self.artifacts if a.get("type") == artifact_type]

    # ── Task Graph Integration ──────────────────────────────────────────────

    def set_task_graph(self, task_graph: TaskGraph) -> None:
        """Set the task graph for this session."""
        self.task_graph = task_graph
        self.updated_at = datetime.now().isoformat()

    def update_node_status(self, node_id: str, status: str) -> None:
        """Update the status of a node in the task graph."""
        if self.task_graph:
            node = self.task_graph.get_node(node_id)
            if node:
                node.status = status
                self.updated_at = datetime.now().isoformat()

    # ── Serialization ───────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "session_type": self.session_type,
            "status": self.status,
            "task_graph": self.task_graph.to_dict() if self.task_graph else None,
            "artifacts": self.artifacts,
            "progress": self.progress,
            "current_node": self.current_node,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


__all__ = ["RuntimeSession"]