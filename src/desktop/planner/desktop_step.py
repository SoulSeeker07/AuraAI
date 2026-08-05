"""
Desktop Step Representation
Atomic execution step in a DesktopPlan with capability graph links and rich metrics.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepType(Enum):
    PREPARATION = "preparation"
    ACTION = "action"
    VERIFICATION = "verification"
    RECOVERY = "recovery"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


@dataclass
class DesktopStep:
    """
    Atomic step in a DesktopPlan.
    """

    step_id: str
    capability: str
    description: str
    step_type: StepType = StepType.ACTION
    status: StepStatus = StepStatus.PENDING
    arguments: dict[str, Any] = field(default_factory=dict)
    requires: list[str] = field(default_factory=list)
    verifies: list[str] = field(default_factory=list)
    rollback_capabilities: list[str] = field(default_factory=list)
    result_data: dict[str, Any] | None = None
    error_message: str | None = None

    # Execution & Metrics Metadata
    retry_count: int = 0
    max_retries: int = 1
    timeout_seconds: float = 30.0
    estimated_time_ms: float = 500.0
    actual_time_ms: float | None = None
    verification_result: dict[str, Any] | None = None
    rollback_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "capability": self.capability,
            "description": self.description,
            "step_type": self.step_type.value,
            "status": self.status.value,
            "arguments": self.arguments,
            "requires": self.requires,
            "verifies": self.verifies,
            "rollback_capabilities": self.rollback_capabilities,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "estimated_time_ms": self.estimated_time_ms,
            "actual_time_ms": self.actual_time_ms,
            "verification_result": self.verification_result,
            "rollback_result": self.rollback_result,
        }
