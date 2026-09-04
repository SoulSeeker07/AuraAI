"""
Autonomous Daemon Data Models & Lifecycle State Machine
Location: src/daemon/models.py

Defines durable states, execution records, trigger policies, and cancellation tokens.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class JobState(str, Enum):
    """Durable state machine for autonomous daemon tasks."""

    SCHEDULED = "scheduled"
    CLAIMED = "claimed"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    RECOVERY_REQUIRED = "recovery_required"


class TriggerType(str, Enum):
    """Types of triggers supported by the scheduler."""

    ONE_SHOT = "one_shot"       # Run once at specific timestamp
    INTERVAL = "interval"       # Run periodically every N seconds
    CRON = "cron"               # Standard cron expression
    CONDITION = "condition"     # Fires on boolean expression evaluation
    EVENT = "event"             # Fires on specific event bus event


class OfflineCatchupPolicy(str, Enum):
    """Behavior when a scheduled trigger is missed while daemon was offline."""

    EXECUTE_ONCE_ON_RECOVERY = "execute_once_on_recovery"  # One-shot: run once on boot
    SKIP_STALE = "skip_stale"                              # Interval: discard missed runs, align to next
    POLICY_DEFAULT = "policy_default"                      # Cron: evaluate per cron window
    MANUAL_INTERVENTION = "manual_intervention"            # High-risk: require user approval


class AutonomyRiskTier(str, Enum):
    """Autonomy governance risk classification for unattended execution."""

    LOW_IMPACT = "low_impact"                     # Allowed unattended (read-only, query, safe actions)
    CONFIRMATION_REQUIRED = "confirmation_req"   # Blocked unattended by default without explicit approval
    HIGH_RISK_GATE = "high_risk_gate"             # Requires parameter-bound, time-bound cryptographic token
    PROHIBITED = "prohibited"                     # Always blocked from unattended daemon execution


class CancellationToken:
    """Thread-safe cooperative cancellation token for running daemon jobs."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._reason: str = ""
        self._callbacks: list[Callable[[], None]] = []
        self._lock = threading.Lock()

    def cancel(self, reason: str = "User cancelled") -> None:
        with self._lock:
            self._reason = reason
            self._cancelled.set()
            for cb in self._callbacks:
                try:
                    cb()
                except Exception:
                    pass

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def reason(self) -> str:
        return self._reason

    def register_callback(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if self._cancelled.is_set():
                try:
                    callback()
                except Exception:
                    pass
            else:
                self._callbacks.append(callback)


@dataclass
class JobDefinition:
    """Durable specification for a daemon job."""

    job_id: str
    name: str
    capability: str
    goal: str
    parameters: dict[str, Any] = field(default_factory=dict)
    trigger_type: TriggerType = TriggerType.ONE_SHOT
    schedule_expression: str = ""  # Delay seconds, cron string, or condition name
    interval_seconds: float = 0.0
    timezone_name: str = "UTC"
    offline_policy: OfflineCatchupPolicy = OfflineCatchupPolicy.EXECUTE_ONCE_ON_RECOVERY
    risk_tier: AutonomyRiskTier = AutonomyRiskTier.LOW_IMPACT
    autonomy_token: str | None = None
    max_retries: int = 3
    timeout_seconds: float = 300.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "user"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "capability": self.capability,
            "goal": self.goal,
            "parameters": self.parameters,
            "trigger_type": self.trigger_type.value,
            "schedule_expression": self.schedule_expression,
            "interval_seconds": self.interval_seconds,
            "timezone_name": self.timezone_name,
            "offline_policy": self.offline_policy.value,
            "risk_tier": self.risk_tier.value,
            "autonomy_token": self.autonomy_token,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "metadata": self.metadata,
        }


@dataclass
class JobExecutionRecord:
    """Durable execution state record for a job run."""

    run_id: str
    job_id: str
    idempotency_key: str
    attempt: int
    status: JobState
    scheduled_at: str
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    checkpoint_data: dict[str, Any] = field(default_factory=dict)
    node_id: str = "local_node"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "job_id": self.job_id,
            "idempotency_key": self.idempotency_key,
            "attempt": self.attempt,
            "status": self.status.value,
            "scheduled_at": self.scheduled_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "checkpoint_data": self.checkpoint_data,
            "node_id": self.node_id,
        }
