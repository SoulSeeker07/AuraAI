"""
Native Operation Metrics
Track performance and action metadata for all native operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PermissionRequired(Enum):
    """Permission level required"""

    NONE = "none"
    READ = "read"
    WRITE = "write"
    CONTROL = "control"
    ADMIN = "admin"


class MetricsLevel(Enum):
    """Level of detail in metrics"""

    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"


@dataclass
class NativeOperationMetrics:
    """
    Metrics for a native operation.

    Tracks timing, permissions, events, and other metadata
    for performance monitoring and audit trails.
    """

    # Timing
    started_at: datetime
    completed_at: datetime
    duration_ms: float

    # Operation metadata
    capability: str
    manager: str
    action: str
    category: str

    # Permission tracking
    permission_used: PermissionRequired
    permission_label: str = "Read"

    # Events triggered
    events_triggered: list[str] = field(default_factory=list)

    # Result metadata
    success: bool = True
    data_size_bytes: int | None = None

    def get_duration_formatted(self) -> str:
        """Get duration formatted as readable string"""
        if self.duration_ms < 1000:
            return f"{self.duration_ms:.2f}ms"
        elif self.duration_ms < 60000:
            return f"{self.duration_ms / 1000:.2f}s"
        else:
            return f"{self.duration_ms / 60000:.2f}m"

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "capability": self.capability,
            "manager": self.manager,
            "action": self.action,
            "category": self.category,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "duration_formatted": self.get_duration_formatted(),
            "permission_used": self.permission_used.value,
            "permission_label": self.permission_label,
            "events_triggered": self.events_triggered,
            "success": self.success,
            "data_size_bytes": self.data_size_bytes,
        }


class MetricsRecorder:
    """
    Recorder for native operation metrics.

    Provides convenience methods to record metrics for
    different operation types with minimal boilerplate.
    """

    def __init__(self, metrics_level: MetricsLevel = MetricsLevel.STANDARD):
        """
        Initialize metrics recorder.

        Args:
            metrics_level: Level of detail in metrics
        """
        self.metrics_level = metrics_level
        self._operations: list[NativeOperationMetrics] = []

    def record(
        self,
        capability: str,
        manager: str,
        action: str,
        category: str,
        permission: PermissionRequired,
        permission_label: str = "Read",
        events_triggered: list[str] | None = None,
        success: bool = True,
        data_size_bytes: int | None = None,
    ) -> NativeOperationMetrics:
        """
        Record metrics for an operation.

        Args:
            capability: Name of capability
            manager: Name of manager
            action: Specific action being performed
            category: Category of the capability
            permission: Permission level used
            permission_label: Human-readable permission label
            events_triggered: List of events triggered
            success: Whether operation succeeded
            data_size_bytes: Size of data returned (if applicable)

        Returns:
            NativeOperationMetrics instance
        """
        started_at = datetime.now()
        completed_at = started_at
        duration_ms = 0.0

        if self.metrics_level != MetricsLevel.MINIMAL:
            completed_at = datetime.now()
            duration_ms = (completed_at - started_at).total_seconds() * 1000

        metrics = NativeOperationMetrics(
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            capability=capability,
            manager=manager,
            action=action,
            category=category,
            permission_used=permission,
            permission_label=permission_label,
            events_triggered=events_triggered or [],
            success=success,
            data_size_bytes=data_size_bytes,
        )

        self._operations.append(metrics)
        return metrics

    def record_success(
        self,
        capability: str,
        manager: str,
        action: str,
        category: str,
        permission: PermissionRequired,
        events_triggered: list[str] | None = None,
        data_size_bytes: int | None = None,
    ) -> NativeOperationMetrics:
        """Record a successful operation"""
        return self.record(
            capability=capability,
            manager=manager,
            action=action,
            category=category,
            permission=permission,
            events_triggered=events_triggered,
            success=True,
            data_size_bytes=data_size_bytes,
        )

    def record_failure(
        self,
        capability: str,
        manager: str,
        action: str,
        category: str,
        permission: PermissionRequired,
        events_triggered: list[str] | None = None,
    ) -> NativeOperationMetrics:
        """Record a failed operation"""
        return self.record(
            capability=capability,
            manager=manager,
            action=action,
            category=category,
            permission=permission,
            events_triggered=events_triggered,
            success=False,
        )

    def get_latest(self) -> NativeOperationMetrics | None:
        """Get the most recently recorded operation metrics"""
        if not self._operations:
            return None
        return self._operations[-1]

    def get_history(self) -> list[NativeOperationMetrics]:
        """Get all recorded operation metrics"""
        return self._operations.copy()

    def get_summary(self) -> dict:
        """
        Get summary of all recorded operations.

        Returns:
            Dictionary with summary statistics
        """
        if not self._operations:
            return {
                "total_operations": 0,
                "successful": 0,
                "failed": 0,
                "total_duration_ms": 0.0,
            }

        total = len(self._operations)
        successful = sum(1 for op in self._operations if op.success)
        failed = total - successful
        total_duration = sum(op.duration_ms for op in self._operations)

        return {
            "total_operations": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "total_duration_ms": total_duration,
            "average_duration_ms": total_duration / total if total > 0 else 0,
        }

    def get_operations_by_capability(
        self, capability: str
    ) -> list[NativeOperationMetrics]:
        """Get all operations for a specific capability"""
        return [op for op in self._operations if op.capability == capability]

    def get_operations_by_manager(self, manager: str) -> list[NativeOperationMetrics]:
        """Get all operations for a specific manager"""
        return [op for op in self._operations if op.manager == manager]

    def get_slow_operations(
        self, threshold_ms: float = 1000.0
    ) -> list[NativeOperationMetrics]:
        """Get operations that took longer than threshold"""
        return [op for op in self._operations if op.duration_ms > threshold_ms]

    def clear(self) -> None:
        """Clear all recorded metrics"""
        self._operations.clear()


# Singleton instance
_recorder: MetricsRecorder | None = None


def get_metrics_recorder() -> MetricsRecorder:
    """Get or create the global metrics recorder singleton"""
    global _recorder
    if _recorder is None:
        _recorder = MetricsRecorder()
    return _recorder


def reset_metrics_recorder() -> None:
    """Reset the global metrics recorder"""
    global _recorder
    _recorder = None
