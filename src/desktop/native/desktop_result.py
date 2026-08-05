"""
Desktop Result
Future-proof result model for all desktop operations.

This replaces NativeResult with a cleaner, more extensible design.
Every desktop operation — whether from WindowManager, ClipboardManager,
Vision, Browser, or Workspace — returns a DesktopResult.

Mirrors the relationship between ResearchReport and ResearchEngine.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DesktopStatus(Enum):
    """Status of a desktop operation."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    PENDING = "pending"


@dataclass
class DesktopResult:
    """
    Structured result for all desktop operations.

    This is the unified return type for the DesktopExecutionEngine,
    exactly as ResearchReport is for ResearchEngine.

    Fields are designed to be future-proof:
    - success:      Did the operation succeed?
    - goal:         The original user goal that triggered this operation
    - capability:   Which capability was discovered and executed
    - manager:      Which manager handled the execution
    - data:         The actual return data (window list, clipboard text, etc.)
    - events:       Events published during execution
    - rollback:     Callable to revert this operation (None if not supported)
    - verification: Verification layer results
    - metrics:      Performance and timing data
    - context_changes: Changes applied to DesktopContext
    - warnings:     Non-fatal issues encountered
    """

    # Core result
    success: bool
    goal: str = ""
    capability: str = ""
    manager: str = ""
    data: Any = None
    error: str | None = None

    # Execution metadata
    status: DesktopStatus = DesktopStatus.PENDING

    # Events published during execution
    events: list[str] = field(default_factory=list)

    # Rollback support
    rollback: Callable[[], bool] | None = None
    rollback_available: bool = False

    # Verification results
    verification: dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    metrics: dict[str, Any] = field(default_factory=dict)

    # Context changes applied
    context_changes: dict[str, Any] = field(default_factory=dict)

    # Non-fatal warnings
    warnings: list[str] = field(default_factory=list)

    # Timestamps
    started_at: float = field(default_factory=time.time)
    completed_at: float = field(default_factory=time.time)

    def __post_init__(self):
        """Calculate duration after initialization."""
        if self.status == DesktopStatus.PENDING:
            self.status = (
                DesktopStatus.SUCCESS if self.success else DesktopStatus.FAILURE
            )
        if self.rollback is not None:
            self.rollback_available = True

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return (self.completed_at - self.started_at) * 1000

    # ==================== Factory Methods ====================

    @classmethod
    def create_success(
        cls,
        goal: str,
        capability: str,
        manager: str,
        data: Any = None,
        events: list[str] | None = None,
        rollback: Callable[[], bool] | None = None,
        verification: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        context_changes: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> "DesktopResult":
        """Create a successful DesktopResult."""
        return cls(
            success=True,
            goal=goal,
            capability=capability,
            manager=manager,
            data=data,
            status=DesktopStatus.SUCCESS,
            events=events or [],
            rollback=rollback,
            rollback_available=rollback is not None,
            verification=verification or {},
            metrics=metrics or {},
            context_changes=context_changes or {},
            warnings=warnings or [],
        )

    @classmethod
    def create_failure(
        cls,
        goal: str,
        capability: str,
        manager: str,
        error: str,
        events: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> "DesktopResult":
        """Create a failed DesktopResult."""
        return cls(
            success=False,
            goal=goal,
            capability=capability,
            manager=manager,
            error=error,
            status=DesktopStatus.FAILURE,
            events=events or [],
            metrics=metrics or {},
            warnings=warnings or [],
        )

    @classmethod
    def create_partial(
        cls,
        goal: str,
        capability: str,
        manager: str,
        data: Any = None,
        warnings: list[str] | None = None,
        events: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> "DesktopResult":
        """Create a partial success DesktopResult."""
        return cls(
            success=True,
            goal=goal,
            capability=capability,
            manager=manager,
            data=data,
            status=DesktopStatus.PARTIAL,
            events=events or [],
            metrics=metrics or {},
            warnings=warnings or [],
        )

    @classmethod
    def create_cancelled(
        cls,
        goal: str,
        capability: str,
        manager: str,
        reason: str = "",
    ) -> "DesktopResult":
        """Create a cancelled DesktopResult."""
        return cls(
            success=False,
            goal=goal,
            capability=capability,
            manager=manager,
            error=reason or "Operation cancelled",
            status=DesktopStatus.CANCELLED,
        )

    # ==================== Helper Methods ====================

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def add_event(self, event_type: str) -> None:
        """Add an event to the events list."""
        if event_type not in self.events:
            self.events.append(event_type)

    def add_context_change(self, key: str, value: Any) -> None:
        """Add a context change."""
        self.context_changes[key] = value

    def set_rollback(self, rollback_fn: Callable[[], bool]) -> None:
        """Set the rollback function."""
        self.rollback = rollback_fn
        self.rollback_available = True

    def execute_rollback(self) -> bool:
        """
        Execute the rollback function if available.

        Returns:
            True if rollback succeeded, False otherwise
        """
        if self.rollback is None:
            return False
        try:
            return self.rollback()
        except Exception as e:
            self.add_warning(f"Rollback failed: {e}")
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "goal": self.goal,
            "capability": self.capability,
            "manager": self.manager,
            "data": self.data,
            "error": self.error,
            "status": self.status.value,
            "events": self.events,
            "rollback_available": self.rollback_available,
            "verification": self.verification,
            "metrics": self.metrics,
            "context_changes": self.context_changes,
            "warnings": self.warnings,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
        }

    def __repr__(self) -> str:
        status_icon = "✓" if self.success else "✗"
        return (
            f"<DesktopResult: {status_icon} {self.capability} "
            f"({self.status.value}) in {self.duration_ms:.2f}ms>"
        )
