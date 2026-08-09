"""
Working Memory Subsystem
Location: src/memory/working_memory.py

Manages active request & session context.
Tracks active task, intent, project_id, subtask progress, tool outputs,
and active constraints during execution.
Supports promotion of verified insights to long-term memory upon completion.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from .models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource


@dataclass
class WorkingMemorySession:
    """Active context for a single execution session."""

    session_id: str
    goal: str
    project_id: str = "global"
    active_intent: str = "chat"
    subtasks: list[dict[str, Any]] = field(default_factory=list)
    action_history: list[dict[str, Any]] = field(default_factory=list)
    active_constraints: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def record_action(self, action_name: str, result: Any, success: bool = True) -> None:
        """Record an execution step in working memory."""
        self.action_history.append({
            "action": action_name,
            "result": str(result)[:500],
            "success": success,
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        })
        self.updated_at = dt.datetime.now().isoformat(timespec="seconds")

    def to_memory_item(self, importance: float = 0.5) -> MemoryItem:
        """Convert working memory session state to a MemoryItem record."""
        return MemoryItem(
            type=MemoryType.WORKING,
            content=f"Session {self.session_id}: Goal='{self.goal}' Actions={len(self.action_history)}",
            importance=importance,
            project_id=self.project_id,
            topic="session_working_memory",
            provenance=MemoryProvenance(
                source_type=ProvenanceSource.RUNTIME_SESSION,
                source_id=self.session_id,
                verified=True,
            ),
            metadata={
                "session_id": self.session_id,
                "goal": self.goal,
                "subtasks_count": len(self.subtasks),
                "action_history": self.action_history,
            },
        )


class WorkingMemoryManager:
    """Manages active working memory sessions across requests."""

    def __init__(self):
        self._sessions: dict[str, WorkingMemorySession] = {}

    def get_or_create_session(self, session_id: str, goal: str, project_id: str = "global") -> WorkingMemorySession:
        if session_id not in self._sessions:
            self._sessions[session_id] = WorkingMemorySession(
                session_id=session_id,
                goal=goal,
                project_id=project_id,
            )
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> WorkingMemorySession | None:
        return self._sessions.get(session_id)

    def discard_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
