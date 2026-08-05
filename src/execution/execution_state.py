"""
Tool Execution Engine - Execution State Tracking

This module tracks the state of all tool executions, providing a unified view
of running and completed tasks.
"""

import threading
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(Enum):
    """Execution status values."""

    PENDING = "pending"
    VALIDATING = "validating"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionState:
    """Tracks the state of a single execution."""

    def __init__(
        self,
        execution_id: str,
        tool_name: str,
        tool_category: str,
        parameters: dict[str, Any],
    ):
        self.execution_id = execution_id
        self.tool_name = tool_name
        self.tool_category = tool_category
        self.parameters = parameters
        self.status = ExecutionStatus.PENDING
        self.status_history: list[dict[str, Any]] = []
        self.progress = 0.0  # 0.0 to 100.0
        self.current_step: str | None = None
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.total_time: float | None = None
        self.result: Any | None = None
        self.error: Exception | None = None
        self.cancellation_token: threading.Event | None = None
        self.permissions_requested: list[str] = []
        self.permissions_granted: list[str] = []
        self.permissions_denied: list[str] = []
        self.risk_level: str | None = None
        self.timeout_seconds: int | None = None
        self.warning_messages: list[str] = []
        self.logs: list[str] = []
        self.metadata: dict[str, Any] = {}
        self.affected_files: list[str] = []
        self.affected_directories: list[str] = []
        self.next_suggestions: list[str] = []
        self._lock = threading.RLock()

    def start(self) -> None:
        """Mark execution as started."""
        with self._lock:
            self.status = ExecutionStatus.RUNNING
            self.start_time = datetime.now()
            self._add_status_history("started")

    def complete(self, result: Any = None) -> None:
        """Mark execution as completed."""
        with self._lock:
            self.status = ExecutionStatus.COMPLETED
            self.end_time = datetime.now()
            if self.start_time:
                self.total_time = (self.end_time - self.start_time).total_seconds()
            self.result = result
            self._add_status_history("completed", progress=100.0)

    def fail(self, error: Exception) -> None:
        """Mark execution as failed."""
        with self._lock:
            self.status = ExecutionStatus.FAILED
            self.end_time = datetime.now()
            if self.start_time:
                self.total_time = (self.end_time - self.start_time).total_seconds()
            self.error = error
            self._add_status_history("failed", progress=self.progress)

    def cancel(self) -> None:
        """Mark execution as cancelled."""
        with self._lock:
            self.status = ExecutionStatus.CANCELLED
            self.end_time = datetime.now()
            if self.start_time:
                self.total_time = (self.end_time - self.start_time).total_seconds()
            self._add_status_history("cancelled", progress=self.progress)

    def timeout(self) -> None:
        """Mark execution as timeout."""
        with self._lock:
            self.status = ExecutionStatus.TIMEOUT
            self.end_time = datetime.now()
            if self.start_time:
                self.total_time = (self.end_time - self.start_time).total_seconds()
            self._add_status_history("timeout", progress=self.progress)

    def update_progress(self, progress: float, step: str = None) -> None:
        """Update execution progress."""
        with self._lock:
            self.progress = max(0.0, min(100.0, progress))
            self.current_step = step
            self._add_status_history("progress_update", progress=self.progress)

    def add_log(self, message: str) -> None:
        """Add a log message."""
        with self._lock:
            self.logs.append(f"{datetime.now().isoformat()} - {message}")

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        with self._lock:
            self.warning_messages.append(message)

    def request_permission(self, permission: str) -> None:
        """Record a permission request."""
        with self._lock:
            self.permissions_requested.append(permission)

    def grant_permission(self, permission: str) -> None:
        """Record a permission grant."""
        with self._lock:
            self.permissions_granted.append(permission)

    def deny_permission(self, permission: str) -> None:
        """Record a permission denial."""
        with self._lock:
            self.permissions_denied.append(permission)

    def set_cancellation_token(self, token: threading.Event) -> None:
        """Set the cancellation token."""
        with self._lock:
            self.cancellation_token = token

    def check_cancellation(self) -> bool:
        """Check if execution should be cancelled."""
        with self._lock:
            return self.cancellation_token and self.cancellation_token.is_set()

    def set_timeout(self, timeout_seconds: int) -> None:
        """Set the timeout for this execution."""
        with self._lock:
            self.timeout_seconds = timeout_seconds

    def _add_status_history(
        self, status: str, progress: float = None, details: dict[str, Any] = None
    ) -> None:
        """Add an entry to status history."""
        with self._lock:
            history_entry = {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "progress": progress or self.progress,
                "current_step": self.current_step,
                "details": details or {},
            }
            self.status_history.append(history_entry)

    def to_dict(self) -> dict[str, Any]:
        """Convert execution state to dictionary."""
        with self._lock:
            return {
                "execution_id": self.execution_id,
                "tool_name": self.tool_name,
                "tool_category": self.tool_category,
                "status": self.status.value,
                "progress": self.progress,
                "current_step": self.current_step,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "total_time": self.total_time,
                "has_result": self.result is not None,
                "has_error": self.error is not None,
                "error_type": type(self.error).__name__ if self.error else None,
                "permissions_requested": len(self.permissions_requested),
                "permissions_granted": len(self.permissions_granted),
                "permissions_denied": len(self.permissions_denied),
                "warning_count": len(self.warning_messages),
                "log_count": len(self.logs),
                "risk_level": self.risk_level,
                "metadata": self.metadata,
            }


class ExecutionStateManager:
    """Manages all execution states for concurrent executions."""

    def __init__(self):
        self._executions: dict[str, ExecutionState] = {}
        self._lock = threading.RLock()

    def create_execution(
        self,
        execution_id: str,
        tool_name: str,
        tool_category: str,
        parameters: dict[str, Any],
    ) -> ExecutionState:
        """Create a new execution state."""
        with self._lock:
            state = ExecutionState(execution_id, tool_name, tool_category, parameters)
            self._executions[execution_id] = state
            return state

    def get_execution(self, execution_id: str) -> ExecutionState | None:
        """Get an execution state."""
        with self._lock:
            return self._executions.get(execution_id)

    def remove_execution(self, execution_id: str) -> ExecutionState | None:
        """Remove an execution state."""
        with self._lock:
            return self._executions.pop(execution_id, None)

    def update_execution(self, execution_id: str, **kwargs) -> ExecutionState | None:
        """Update an execution state."""
        with self._lock:
            state = self._executions.get(execution_id)
            if state:
                for key, value in kwargs.items():
                    if hasattr(state, key):
                        setattr(state, key, value)
            return state

    def list_executions(self) -> list[dict[str, Any]]:
        """List all executions."""
        with self._lock:
            return [state.to_dict() for state in self._executions.values()]

    def get_running_executions(self) -> list[ExecutionState]:
        """Get all currently running executions."""
        with self._lock:
            return [
                state
                for state in self._executions.values()
                if state.status
                in (
                    ExecutionStatus.RUNNING,
                    ExecutionStatus.VALIDATING,
                    ExecutionStatus.PREPARING,
                )
            ]

    def get_execution_count(self) -> int:
        """Get the total number of executions."""
        with self._lock:
            return len(self._executions)

    def cleanup_stale_executions(self, max_age_hours: int = 1) -> int:
        """Remove executions older than max_age_hours."""
        with self._lock:
            current_time = datetime.now()
            removed = 0
            for execution_id, state in list(self._executions.items()):
                if (
                    state.end_time
                    and (current_time - state.end_time).total_seconds()
                    > max_age_hours * 3600
                ):
                    self._executions.pop(execution_id, None)
                    removed += 1
            return removed

    def clear_all(self) -> None:
        """Clear all executions (for testing)."""
        with self._lock:
            self._executions.clear()
