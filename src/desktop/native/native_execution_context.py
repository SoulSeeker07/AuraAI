"""
Native Execution Context
Shared execution context object that carries all state through the pipeline.

Every layer shares this single object instead of passing individual parameters.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Dict
from datetime import datetime
from enum import Enum

from .native_models import WindowInfo, ProcessInfo, ClipboardData, DisplayInfo, AudioDevice, NetworkInterface
from .native_exceptions import NativeError, CapabilityNotFoundError
from .capability_registry import CapabilityRegistry, PermissionRequired
from .desktop_context import get_desktop_context, DesktopContext
from .metrics import MetricsRecorder, MetricsLevel
from .native_result import NativeResult, ResultStatus


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
    arguments: Dict[str, Any]
    stage: ExecutionStage = ExecutionStage.INIT
    status: ExecutionStatus = ExecutionStatus.PENDING

    # Permission state
    permission: Optional[PermissionRequired] = None
    permission_granted: bool = False
    permission_denied_reason: Optional[str] = None

    # Metrics state
    metrics_recorder: Optional[MetricsRecorder] = None
    operation_started_at: Optional[datetime] = None
    operation_completed_at: Optional[datetime] = None
    metrics_level: MetricsLevel = MetricsLevel.STANDARD

    # Execution state
    result: Optional[NativeResult] = None
    exception: Optional[Exception] = None
    rollback_function: Optional[Callable[[], Any]] = None

    # Context state
    desktop_context: Optional[DesktopContext] = None
    context_updated: bool = False

    # Event state
    events_triggered: list[str] = field(default_factory=list)

    # Execution control
    aborted: bool = False
    abort_reason: Optional[str] = None

    # Metadata
    capability_metadata: Optional[Dict[str, Any]] = None
    manager_name: Optional[str] = None
    action_name: Optional[str] = None
    category: Optional[str] = None

    # Verification state
    verification_passed: bool = False
    verification_error: Optional[str] = None

    def __post_init__(self):
        """Initialize desktop context if not provided"""
        if self.desktop_context is None:
            self.desktop_context = get_desktop_context()

    # ==================== Stage Management ====================

    def set_stage(self, stage: ExecutionStage) -> None:
        """Set the current execution stage"""
        self.stage = stage

    def advance_stage(self) -> None:
        """Advance to next stage in pipeline"""
        stages = list(ExecutionStage)
        current_index = stages.index(self.stage)
        if current_index + 1 < len(stages):
            self.stage = stages[current_index + 1]

    # ==================== Permission Management ====================

    def set_permission_required(self, permission: PermissionRequired) -> None:
        """Set the required permission for this execution"""
        self.permission = permission

    def set_permission_granted(self, granted: bool, reason: Optional[str] = None) -> None:
        """Set permission grant status"""
        self.permission_granted = granted
        self.permission_denied_reason = reason

    def check_permission(self) -> bool:
        """Check if permission is granted (placeholder for permission system)"""
        return self.permission_granted

    # ==================== Metrics Management ====================

    def start_metrics(self) -> None:
        """Start timing for the operation"""
        if self.metrics_recorder is None:
            self.metrics_recorder = MetricsRecorder(self.metrics_level)
        self.operation_started_at = datetime.now()

    def complete_metrics(self) -> None:
        """Complete timing for the operation"""
        if self.operation_started_at:
            self.operation_completed_at = datetime.now()

    def get_duration_ms(self) -> float:
        """Get duration in milliseconds"""
        if self.operation_started_at and self.operation_completed_at:
            return (self.operation_completed_at - self.operation_started_at).total_seconds() * 1000
        return 0.0

    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get metrics dictionary"""
        if self.metrics_recorder and self.metrics_recorder.get_latest():
            return self.metrics_recorder.get_latest().to_dict()
        return None

    # ==================== Result Management ====================

    def set_result(self, result: NativeResult) -> None:
        """Set the execution result"""
        self.result = result
        self.status = result.status

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

    def set_verification_passed(self, passed: bool, error: Optional[str] = None) -> None:
        """Set verification status"""
        self.verification_passed = passed
        self.verification_error = error

    # ==================== Status Management ====================

    def set_status(self, status: ExecutionStatus) -> None:
        """Set the execution status"""
        self.status = status

    def abort(self, reason: Optional[str] = None) -> None:
        """Abort execution"""
        self.aborted = True
        self.abort_reason = reason
        self.status = ExecutionStatus.CANCELLED

    # ==================== Helper Methods ====================

    def is_successful(self) -> bool:
        """Check if execution was successful"""
        return self.status == ExecutionStatus.SUCCESS

    def is_completed(self) -> bool:
        """Check if execution is completed"""
        return self.stage in [ExecutionStage.COMPLETE, ExecutionStage.FAILED, ExecutionStage.CANCELLED]

    def to_dict(self) -> Dict[str, Any]:
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

    def log_stage(self, stage: ExecutionStage, message: Optional[str] = None) -> None:
        """Log the current stage (for diagnostics)"""
        self.stage = stage
        if message:
            print(f"[NativePipeline] Stage: {stage.value} - {message}")

    def to_diagnostics(self) -> Dict[str, Any]:
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
                "started_at": self.operation_started_at.isoformat() if self.operation_started_at else None,
                "completed_at": self.operation_completed_at.isoformat() if self.operation_completed_at else None,
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
        arguments: Optional[Dict[str, Any]] = None,
        metrics_level: MetricsLevel = MetricsLevel.STANDARD,
        capability_metadata: Optional[Dict[str, Any]] = None,
        manager_name: Optional[str] = None,
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
