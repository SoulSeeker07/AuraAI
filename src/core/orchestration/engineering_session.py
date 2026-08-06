"""
Engineering Session & Execution State
Location: src/core/orchestration/engineering_session.py

Represents a long-running software engineering task session (EngineeringSession).
Inherits from RuntimeSession base class.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .runtime_session import RuntimeSession, RuntimeWorkerState, SessionStatus

# Backward compatibility alias
EngineeringSessionStatus = SessionStatus
WorkerState = RuntimeWorkerState


@dataclass
class EngineeringSession(RuntimeSession):
    """
    Persistent state object for a long-running software engineering session.
    """

    domain: str = "engineering"
    workspace: str = ""
    current_worker: str = "AntigravityWorker"
    modified_files: list[str] = field(default_factory=list)
    tests: dict[str, Any] = field(
        default_factory=lambda: {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    )

    def __post_init__(self):
        if not self.session_id.startswith("eng_"):
            self.session_id = f"eng_{uuid.uuid4().hex[:10]}"

    def add_modified_file(self, filepath: str) -> None:
        """Record a modified file if not already present."""
        if filepath not in self.modified_files:
            self.modified_files.append(filepath)
        self.updated_at = datetime.now().isoformat()
        self.record_timeline_event(
            "file_modified", f"Modified file: {filepath}", {"filepath": filepath}
        )

    def update_tests(
        self, passed: int, failed: int, total: int = 0, skipped: int = 0
    ) -> None:
        """Update test execution results."""
        self.tests = {
            "total": total or (passed + failed + skipped),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }
        self.updated_at = datetime.now().isoformat()
        self.record_timeline_event(
            "tests_updated",
            f"Tests: {passed}/{total or (passed+failed+skipped)} passed",
            self.tests,
        )

    def get_summary(self) -> str:
        """Generate a concise human-readable summary of current engineering session status."""
        lines = [
            f"Engineering Session: {self.session_id}",
            f"Goal: {self.goal}",
            f"Status: {self.status.value if hasattr(self.status, 'value') else self.status}",
            f"Progress: {self.progress}%",
            f"Current Action: {self.current_action}",
        ]
        if self.modified_files:
            lines.append(
                f"Modified Files ({len(self.modified_files)}): {', '.join(self.modified_files[:5])}"
            )
        if self.tests.get("total", 0) > 0:
            lines.append(
                f"Tests: {self.tests['passed']}/{self.tests['total']} passed ({self.tests['failed']} failed)"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "workspace": self.workspace,
                "current_worker": self.current_worker,
                "modified_files": self.modified_files,
                "tests": self.tests,
            }
        )
        return data
