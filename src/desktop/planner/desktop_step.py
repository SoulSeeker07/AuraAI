"""
Desktop Step Representation
Atomic execution step in a DesktopPlan with capability graph links.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


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
    arguments: Dict[str, Any] = field(default_factory=dict)
    requires: List[str] = field(default_factory=list)
    verifies: List[str] = field(default_factory=list)
    rollback_capabilities: List[str] = field(default_factory=list)
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
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
        }
