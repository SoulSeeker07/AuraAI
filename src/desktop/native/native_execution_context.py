"""
Native Execution Context
Shared execution context object that carries all state through the pipeline.

Every layer shares this single object instead of passing individual parameters.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .capability_registry import PermissionRequired
from .desktop_context import DesktopContext, get_desktop_context
from .desktop_result import DesktopResult
from .metrics import MetricsLevel, MetricsRecorder
from .native_result import NativeResult


class ExecutionStage(Enum):
    """Stage of execution in the pipeline"""

    INIT = "init"
    PERMISSION_CHECK = "permission_check"
    METRICS_START = "metrics_start"
    EXECUTE = "execute"
    VERIFY = "verify"
    EVENTS = "events"
    CONTEXT = "context"
    METRICS_FINISH = "metrics_finish"
    COMPLETE = "complete"


class ExecutionStatus(Enum):
    """Status of execution"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class NativeExecutionContext:
    """
    Shared execution context that carries all state through the pipeline.

    Every layer (Permission, Metrics, Manager, Verification, Events, Context)
    operates on this single object instead of passing individual parameters.

    This follows the same pattern as ResearchEngine in your architecture.
    """

    # Core execution state
    capability: str
    arguments: dict[str, Any]
    stage: ExecutionStage = ExecutionStage.INIT
    status: ExecutionStatus = ExecutionStatus.PENDING

    # Permission state
    permission: PermissionRequired | None = None
    permission_granted: bool = False
    permission_denied_reason: str | None = None

    # Metrics state
    metrics_recorder: MetricsRecorder | None = None
    operation_started_at: datetime | None = None
    operation_completed_at: datetime | None = None
    metrics_level: MetricsLevel = MetricsLevel.STANDARD

    # Execution state
    result: DesktopResult | NativeResult | None = None
    exception: Exception | None = None
    rollback_function: Callable[[], Any] | None = None

    # Context state
    desktop_context: DesktopContext | None = None
    context_updated: bool = False

    # Event state
    events_triggered: list[str] = field(default_factory=list)

    # Execution control
    aborted: bool = False
    abort_reason: str | None = None

    # Metadata
    capability_metadata: dict[str, Any] | None = None
    manager_name: str | None = None
    action_name: str | None = None
    category: str | None = None

    # Verification state
    verification_passed: bool = False
    verification_error: str | None = None

    def __post_init__(self):
        """Initialize context after creation"""
        if self.desktop_context is None:
            self.desktop_context = get_desktop_context()

    # ==================== State Management ====================

    def set_stage(self, stage: ExecutionStage) -> None:
        """Set current execution stage"""
        self.stage = stage

    def set_status(self, status: ExecutionStatus) -> None:
        """Set execution status"""
        self.status = status

    def abort(self, reason: str | None = None) -> None:
        """Abort execution"""
        self.aborted = True
        self.abort_reason = reason
        self.status = ExecutionStatus.CANCELLED

    # ==================== Permission Management ====================

    def grant_permission(self) -> None:
        """Grant permission for execution"""
        self.permission_granted = True
        self.permission_denied_reason = None

    def deny_permission(self, reason: str) -> None:
        """Deny permission for execution"""
        self.permission_granted = False
        self.permission_denied_reason = reason
        self.status = ExecutionStatus.FAILED

    def set_permission_required(self, permission: PermissionRequired) -> None:
        """Set the required permission for this execution"""
        self.permission = permission

    def check_permission(self) -> bool:
        """Check if permission is granted (placeholder for permission system)"""
        return self.permission_granted

    # ==================== Metrics Management ====================

    def start_timing(self) -> None:
        """Start execution timing"""
        self.operation_started_at = datetime.now()
        if self.metrics_recorder:
            self.metrics_recorder.start_operation(
                self.capability,
                getattr(self, "manager_name", "unknown"),
                getattr(self, "action_name", self.capability),
            )

    def stop_timing(self, success: bool = True, error: str | None = None) -> None:
        """Stop execution timing"""
        self.operation_completed_at = datetime.now()
        if self.metrics_recorder:
            self.metrics_recorder.record_metrics(success=success, error=error)

    def get_duration_ms(self) -> float:
        """Get execution duration in milliseconds"""
        if self.operation_started_at and self.operation_completed_at:
            delta = self.operation_completed_at - self.operation_started_at
            return delta.total_seconds() * 1000
        return 0.0

    def get_metrics(self) -> dict[str, Any] | None:
        """Get metrics dictionary"""
        if self.metrics_recorder and self.metrics_recorder.get_latest():
            return self.metrics_recorder.get_latest().to_dict()
        return None

    # ==================== Result Management ====================

    def set_result(self, result: DesktopResult | NativeResult) -> None:
        """Set the execution result"""
        self.result = result
        if hasattr(result, "status"):
            if isinstance(result.status, ExecutionStatus):
                self.status = result.status
            elif hasattr(result.status, "name") and result.status.name in ExecutionStatus.__members__:
                self.status = ExecutionStatus[result.status.name]
            else:
                self.status = ExecutionStatus.SUCCESS if getattr(result, "success", False) else ExecutionStatus.FAILED
        else:
            self.status = ExecutionStatus.SUCCESS if getattr(result, "success", False) else ExecutionStatus.FAILED

    def set_exception(self, exception: Exception) -> None:
        """Set exception that occurred during execution"""
        self.exception = exception
        self.status = ExecutionStatus.FAILED

    def set_rollback(self, rollback_function: Callable[[], Any]) -> None:
        """Set rollback function for this operation"""
        self.rollback_function = rollback_function

    # ==================== Context Management ====================

    def set_context_updated(self, updated: bool) -> None:
        """Set whether context was updated"""
        self.context_updated = updated

    # ==================== Event Management ====================

    def add_event(self, event_type: str) -> None:
        """Add an event to the event list"""
        if event_type not in self.events_triggered:
            self.events_triggered.append(event_type)

    # ==================== Verification Management ====================

    def set_verification_passed(self, passed: bool, error: str | None = None) -> None:
        """Set verification status"""
        self.verification_passed = passed
        self.verification_error = error



    # ==================== Helper Methods ====================

    def is_successful(self) -> bool:
        """Check if execution was successful"""
        return self.status == ExecutionStatus.SUCCESS

    def is_completed(self) -> bool:
        """Check if execution is completed"""
        return self.stage in [
            ExecutionStage.COMPLETE,
            ExecutionStage.FAILED,
            ExecutionStage.CANCELLED,
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for logging/diagnostics"""
        return {
            "capability": self.capability,
            "stage": self.stage.value,
            "status": self.status.value,
            "permission": self.permission.value if self.permission else None,
            "permission_granted": self.permission_granted,
            "duration_ms": self.get_duration_ms(),
            "metrics_level": self.metrics_level.value,
            "manager_name": self.manager_name,
            "category": self.category,
            "aborted": self.aborted,
            "verification_passed": self.verification_passed,
            "events_triggered": self.events_triggered,
        }

    def log_stage(self, stage: ExecutionStage, message: str | None = None) -> None:
        """Log the current stage (for diagnostics)"""
        self.stage = stage
        if message:
            print(f"[NativePipeline] Stage: {stage.value} - {message}")

    def to_diagnostics(self) -> dict[str, Any]:
        """
        Get detailed diagnostics for this execution.

        Returns:
            Dictionary with complete execution breakdown
        """
        return {
            "capability": self.capability,
            "stage": self.stage.value,
            "status": self.status.value,
            "permission": {
                "required": self.permission.value if self.permission else None,
                "granted": self.permission_granted,
                "denied_reason": self.permission_denied_reason,
            },
            "timing": {
                "duration_ms": self.get_duration_ms(),
                "started_at": (
                    self.operation_started_at.isoformat()
                    if self.operation_started_at
                    else None
                ),
                "completed_at": (
                    self.operation_completed_at.isoformat()
                    if self.operation_completed_at
                    else None
                ),
            },
            "metrics": self.get_metrics(),
            "manager": self.manager_name,
            "category": self.category,
            "rollback_available": self.rollback_function is not None,
            "verification": {
                "passed": self.verification_passed,
                "error": self.verification_error,
            },
            "events": self.events_triggered,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
        }


class ExecutionContextFactory:
    """Factory for creating execution context instances"""

    @staticmethod
    def create(
        capability: str,
        arguments: dict[str, Any] | None = None,
        metrics_level: MetricsLevel = MetricsLevel.STANDARD,
        capability_metadata: dict[str, Any] | None = None,
        manager_name: str | None = None,
    ) -> NativeExecutionContext:
        """
        Create a new execution context.

        Args:
            capability: Name of capability
            arguments: Arguments for the capability
            metrics_level: Level of detail in metrics
            capability_metadata: Metadata for the capability
            manager_name: Name of manager

        Returns:
            NativeExecutionContext instance
        """
        return NativeExecutionContext(
            capability=capability,
            arguments=arguments or {},
            metrics_level=metrics_level,
            capability_metadata=capability_metadata,
            manager_name=manager_name,
        )
