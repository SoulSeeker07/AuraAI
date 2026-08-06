"""
Worker Manager - Central Long-Running Subsystem Worker Runtime
Location: src/core/orchestration/worker_manager.py

Tracks, registers, and controls long-running domain workers across the OS:
- DesktopWorker
- BrowserWorker
- ResearchWorker
- EngineeringWorker
- MemoryWorker

Allows deterministic zero-LLM status queries ("status?", "show active workers",
"pause engineering", "cancel worker 2", "how many tasks are running?").
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .engineering_session import EngineeringSession

logger = logging.getLogger(__name__)


@dataclass
class DomainWorker:
    """
    Generic representation of an active long-running subsystem worker.
    """

    worker_id: str
    name: str
    domain: str  # "engineering", "desktop", "browser", "research", "memory"
    status: str = "RUNNING"  # "RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"
    progress: int = 0
    current_action: str = ""
    session_ref: Any = None
    pause_cb: Callable[[], None] | None = None
    resume_cb: Callable[[], None] | None = None
    cancel_cb: Callable[[], None] | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "domain": self.domain,
            "status": self.status,
            "progress": self.progress,
            "current_action": self.current_action,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class WorkerManager:
    """
    Central Manager for active subsystem workers across Aura AI.
    Singleton pattern for system-wide state tracking.
    """

    _instance: Optional["WorkerManager"] = None

    @classmethod
    def get_instance(cls) -> "WorkerManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._workers: dict[str, DomainWorker] = {}
        self._active_sessions: dict[str, dict[str, Any]] = {
            "engineering": {},
            "browser": {},
            "research": {},
            "desktop": {},
        }

    def register_worker(self, worker: DomainWorker) -> None:
        """Register a new domain worker."""
        self._workers[worker.worker_id] = worker
        logger.info(
            f"WorkerManager: Registered worker '{worker.name}' [{worker.worker_id}] in domain '{worker.domain}'"
        )

    def unregister_worker(self, worker_id: str) -> None:
        """Unregister a domain worker."""
        if worker_id in self._workers:
            del self._workers[worker_id]
            logger.info(f"WorkerManager: Unregistered worker [{worker_id}]")

    def register_engineering_session(self, session: EngineeringSession) -> None:
        """Register an EngineeringSession as a tracked session."""
        self._active_sessions["engineering"][session.session_id] = session
        eng_worker = DomainWorker(
            worker_id=session.session_id,
            name=f"Engineering Session ({session.goal[:30]})",
            domain="engineering",
            status=(
                session.status.value
                if hasattr(session.status, "value")
                else str(session.status)
            ),
            progress=session.progress,
            current_action=session.current_action,
            session_ref=session,
            pause_cb=session.pause,
            resume_cb=session.resume,
            cancel_cb=session.cancel,
        )
        self.register_worker(eng_worker)

    def register_domain_session(
        self, domain: str, session_id: str, name: str, goal: str, **kwargs
    ) -> DomainWorker:
        """Register a generic domain session (BrowserSession, ResearchSession, DesktopSession)."""
        dom = domain.lower()
        if dom not in self._active_sessions:
            self._active_sessions[dom] = {}
        self._active_sessions[dom][session_id] = {
            "session_id": session_id,
            "goal": goal,
            "name": name,
            **kwargs,
        }

        worker = DomainWorker(
            worker_id=session_id,
            name=f"{domain.title()} Session ({goal[:30]})",
            domain=dom,
            status="RUNNING",
            progress=0,
            current_action=f"Running {domain} session...",
        )
        self.register_worker(worker)
        return worker

    def get_engineering_session(
        self, session_id: str | None = None
    ) -> EngineeringSession | None:
        """Get the active or specified EngineeringSession."""
        eng_sessions = self._active_sessions.get("engineering", {})
        if session_id and session_id in eng_sessions:
            return eng_sessions[session_id]
        if eng_sessions:
            return list(eng_sessions.values())[-1]
        return None

    def list_active_workers(self, domain: str | None = None) -> list[DomainWorker]:
        """List all active (non-completed) workers, optionally filtered by domain."""
        active = [
            w for w in self._workers.values() if w.status in ("RUNNING", "PAUSED")
        ]
        if domain:
            active = [w for w in active if w.domain.lower() == domain.lower()]
        return active

    def pause_domain(self, domain: str = "engineering") -> bool:
        """Pause all active workers in a given domain."""
        found = False
        for worker in self.list_active_workers(domain=domain):
            if worker.pause_cb:
                worker.pause_cb()
            worker.status = "PAUSED"
            worker.updated_at = datetime.now().isoformat()
            found = True
        return found

    def resume_domain(self, domain: str = "engineering") -> bool:
        """Resume all paused workers in a given domain."""
        found = False
        for worker in self._workers.values():
            if worker.domain.lower() == domain.lower() and worker.status == "PAUSED":
                if worker.resume_cb:
                    worker.resume_cb()
                worker.status = "RUNNING"
                worker.updated_at = datetime.now().isoformat()
                found = True
        return found

    def cancel_worker(self, worker_id: str) -> bool:
        """Cancel a specific worker by ID or index match."""
        # Check by exact ID
        if worker_id in self._workers:
            w = self._workers[worker_id]
            if w.cancel_cb:
                w.cancel_cb()
            w.status = "CANCELLED"
            w.updated_at = datetime.now().isoformat()
            return True

        # Check by numeric index among active workers (e.g. "worker 1")
        try:
            idx = int(worker_id.replace("worker", "").strip()) - 1
            active = self.list_active_workers()
            if 0 <= idx < len(active):
                w = active[idx]
                if w.cancel_cb:
                    w.cancel_cb()
                w.status = "CANCELLED"
                w.updated_at = datetime.now().isoformat()
                return True
        except ValueError:
            pass

        return False

    def get_status_summary(self) -> str:
        """Generate a deterministic human-readable status summary without LLM calls."""
        active = self.list_active_workers()
        if not active:
            return "No active background workers running."

        lines = [f"=== Active Workers ({len(active)}) ==="]
        for idx, w in enumerate(active, 1):
            lines.append(f"Worker {idx} [{w.domain.upper()}] - {w.name}")
            lines.append(
                f"  Status: {w.status} ({w.progress}%) | Action: {w.current_action}"
            )
            if (
                w.session_ref
                and hasattr(w.session_ref, "modified_files")
                and w.session_ref.modified_files
            ):
                lines.append(
                    f"  Modified Files: {', '.join(w.session_ref.modified_files[:3])}"
                )

        return "\n".join(lines)
