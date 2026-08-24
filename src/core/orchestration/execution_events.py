"""
Execution Events & Node State Data Contract (Core Orchestration / Qt-Free)
Location: src/core/orchestration/execution_events.py

Defines pure Python, strongly-typed execution event contracts for the
AuraAI task orchestration pipeline, execution trace model, and UI/CLI observers.

Architectural Invariants:
1. Zero Qt / PySide6 dependencies: Safe for core orchestration, headless runners, and CLI.
2. Exhaustive 6-Member State Taxonomy: Complete coverage of all SubTask lifecycle states.
3. Explicit Verification Tri-State: `verified: Optional[bool]` (None=unverified/pending, True=passed, False=failed).
4. Passive Observation: Observers (like ApprovalGateWidget and ExecutionTraceModel) receive push events without polling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class NodeState(str, Enum):
    """
    Exhaustive 6-member lifecycle status taxonomy for DAG execution nodes.
    Maps directly to SubTask.status values emitted across TaskDecomposer and MasterOrchestrator.
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

    @classmethod
    def from_str(cls, value: str | NodeState) -> "NodeState":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            val_lower = value.strip().lower()
            # Normalize legacy aliases
            if val_lower in ("success", "done", "passed"):
                return cls.COMPLETED
            if val_lower in ("fail", "error"):
                return cls.FAILED
            if val_lower in ("cancel", "aborted"):
                return cls.CANCELLED
            if val_lower in ("skip",):
                return cls.SKIPPED
            for member in cls:
                if member.value == val_lower:
                    return member
        raise ValueError(f"Unknown NodeState '{value}'. Must be one of: {[m.value for m in cls]}")


@dataclass(frozen=True)
class ExecutionEvent:
    """Base contract for all execution lifecycle telemetry events."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class SubTaskNodeInfo:
    """Immutable snapshot of a SubTask node within an execution graph."""
    task_id: str
    title: str
    required_role: str
    capability: str
    description: str = ""
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    status: NodeState = NodeState.PENDING
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphInitializedEvent(ExecutionEvent):
    """Emitted when MasterOrchestrator decomposes and initializes a new TaskGraph."""
    goal: str = ""
    session_id: str = ""
    nodes: tuple[SubTaskNodeInfo, ...] = field(default_factory=tuple)
    execution_order: tuple[tuple[str, ...], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NodeStateChangedEvent(ExecutionEvent):
    """
    Emitted on every SubTask lifecycle state transition.
    
    Attributes:
        task_id: Identifier of the executing subtask
        new_state: Target NodeState status
        old_state: Previous NodeState status if known
        result: Raw execution result object or summary dict
        error: Error message string if failed
        verified: Explicit tri-state verification flag:
                  - None  = Not yet verified / verification not applicable
                  - True  = OS-level / post-condition verification passed
                  - False = OS-level / post-condition verification failed
    """
    task_id: str = ""
    new_state: NodeState = NodeState.PENDING
    old_state: Optional[NodeState] = None
    result: Any = None
    error: Optional[str] = None
    verified: Optional[bool] = None


@dataclass(frozen=True)
class ConfirmationRequiredEvent(ExecutionEvent):
    """
    Emitted when task execution is halted on ASK_USER pending human confirmation.
    Enables ApprovalGateWidget, ExecutionTraceModel, and UI observers to react immediately.
    """
    session_id: str = ""
    task_id: str = ""
    plan_id: str = ""
    prompt: str = ""
    target: str = ""
    capability: str = ""
    remaining_task_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExecutionStartedEvent(ExecutionEvent):
    """Emitted when overall plan execution begins."""
    goal: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class ExecutionFinishedEvent(ExecutionEvent):
    """Emitted when overall plan execution finishes."""
    goal: str = ""
    session_id: str = ""
    success: bool = True
    observations: tuple[str, ...] = field(default_factory=tuple)
    error: Optional[str] = None


@dataclass(frozen=True)
class ReplanTriggeredEvent(ExecutionEvent):
    """Emitted when adaptive replanning replaces or mutates the running execution graph."""
    reason: str = ""
    old_goal: str = ""
    new_goal: str = ""
