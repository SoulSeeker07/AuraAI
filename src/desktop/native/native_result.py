"""
Native Result Object
Structured results for native operations with metadata for GUI and undo.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResultStatus(Enum):
    """Result status"""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class ActionCategory(Enum):
    """Category of action"""

    WINDOW = "window"
    CLIPBOARD = "clipboard"
    DISPLAY = "display"
    POWER = "power"
    AUDIO = "audio"
    NETWORK = "network"
    REGISTRY = "registry"
    SERVICE = "service"


@dataclass
class NativeResult:
    """
    Structured result for native operations.

    Contains the actual result, metadata for GUI, undo info, and metrics.
    """

    # Core result
    status: ResultStatus
    data: Any = None
    error: Exception | None = None

    # Metadata
    capability: str | None = None
    manager: str | None = None
    action: str | None = None
    category: ActionCategory | None = None

    # GUI visualization
    success_message: str | None = None
    warning_messages: list[str] = field(default_factory=list)
    info_messages: list[str] = field(default_factory=list)

    # Undo information
    undo_available: bool = False
    undo_data: dict[str, Any] | None = None
    rollback_function: Callable | None = None

    # Metrics
    duration_ms: float = 0.0
    permission_used: bool = False
    events_triggered: list[str] = field(default_factory=list)

    # Timestamps
    started_at: float = field(default_factory=time.time)
    completed_at: float = field(default_factory=time.time)

    def __post_init__(self):
        """Calculate duration after initialization"""
        if self.started_at and self.completed_at:
            self.duration_ms = (self.completed_at - self.started_at) * 1000

    @classmethod
    def success(
        cls,
        data: Any,
        capability: str,
        action: str,
        category: ActionCategory,
        success_message: str | None = None,
        undo_available: bool = False,
        rollback_function: Callable | None = None,
        events_triggered: list | None = None,
    ) -> "NativeResult":
        """
        Create a successful result.

        Args:
            data: Result data
            capability: Capability name
            action: Action name
            category: Action category
            success_message: Success message for GUI
            undo_available: Whether undo is available
            rollback_function: Function to call for rollback
            events_triggered: List of events triggered

        Returns:
            NativeResult with SUCCESS status
        """
        return cls(
            status=ResultStatus.SUCCESS,
            data=data,
            capability=capability,
            action=action,
            category=category,
            success_message=success_message,
            undo_available=undo_available,
            rollback_function=rollback_function,
            events_triggered=events_triggered or [],
        )

    @classmethod
    def failure(
        cls,
        error: Exception,
        capability: str,
        action: str,
        category: ActionCategory,
        message: str | None = None,
    ) -> "NativeResult":
        """
        Create a failed result.

        Args:
            error: Exception that occurred
            capability: Capability name
            action: Action name
            category: Action category
            message: Error message for GUI

        Returns:
            NativeResult with FAILURE status
        """
        return cls(
            status=ResultStatus.FAILURE,
            error=error,
            capability=capability,
            action=action,
            category=category,
            info_messages=[message or str(error)] if message else [],
        )

    @classmethod
    def partial(
        cls,
        data: Any,
        capability: str,
        action: str,
        category: ActionCategory,
        warning_messages: list[str] = None,
        success_message: str | None = None,
    ) -> "NativeResult":
        """
        Create a partial success result.

        Args:
            data: Result data (partial)
            capability: Capability name
            action: Action name
            category: Action category
            warning_messages: List of warnings
            success_message: Success message for GUI

        Returns:
            NativeResult with PARTIAL status
        """
        return cls(
            status=ResultStatus.PARTIAL,
            data=data,
            capability=capability,
            action=action,
            category=category,
            warning_messages=warning_messages or [],
            success_message=success_message,
        )

    @classmethod
    def cancelled(cls, capability: str, action: str) -> "NativeResult":
        """
        Create a cancelled result.

        Args:
            capability: Capability name
            action: Action name

        Returns:
            NativeResult with CANCELLED status
        """
        return cls(status=ResultStatus.CANCELLED, capability=capability, action=action)

    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warning_messages.append(message)

    def add_info(self, message: str) -> None:
        """Add an info message"""
        self.info_messages.append(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": str(self.error) if self.error else None,
            "capability": self.capability,
            "manager": self.manager,
            "action": self.action,
            "category": self.category.value if self.category else None,
            "success_message": self.success_message,
            "warning_messages": self.warning_messages,
            "info_messages": self.info_messages,
            "undo_available": self.undo_available,
            "undo_data": self.undo_data,
            "duration_ms": self.duration_ms,
            "permission_used": self.permission_used,
            "events_triggered": self.events_triggered,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def __repr__(self) -> str:
        return f"<NativeResult: {self.status.value} ({self.action}) in {self.duration_ms:.2f}ms>"
