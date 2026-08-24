"""
Autonomy Models & Event Provenance
Location: src/autonomy/models.py

Defines TriggerState, TriggerType, ConcurrencyPolicy, EventProvenance, and Trigger models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class TriggerType(str, Enum):
    SCHEDULED = "SCHEDULED"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    CONDITION = "CONDITION"


class TriggerState(str, Enum):
    REGISTERED = "REGISTERED"
    ARMED = "ARMED"
    FIRED = "FIRED"
    RUNNING = "RUNNING"
    VERIFIED = "VERIFIED"
    RETRYING = "RETRYING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ConcurrencyPolicy(str, Enum):
    COALESCE = "COALESCE"
    QUEUE = "QUEUE"
    REJECT = "REJECT"


@dataclass
class EventProvenance:
    trigger_id: str
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    dedup_key: str = ""
    trigger_type: str = TriggerType.SCHEDULED.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    fired_at: str | None = None
    execution_id: str | None = None
    result_status: str | None = None


@dataclass
class Trigger:
    trigger_id: str
    trigger_type: TriggerType
    action_goal: str
    execution_map: dict[str, Any]
    cron_schedule: str | None = None
    interval_seconds: float | None = None
    event_pattern: str | None = None
    condition_fn: str | None = None
    state: TriggerState = TriggerState.REGISTERED
    enabled: bool = True
    dedup_key: str | None = None
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.COALESCE
    last_fired_at: str | None = None
    last_provenance: EventProvenance | None = None
    auth_signature: str | None = None
    is_recurring_authorized: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type.value if isinstance(self.trigger_type, Enum) else self.trigger_type,
            "action_goal": self.action_goal,
            "execution_map": self.execution_map,
            "cron_schedule": self.cron_schedule,
            "interval_seconds": self.interval_seconds,
            "event_pattern": self.event_pattern,
            "condition_fn": self.condition_fn,
            "state": self.state.value if isinstance(self.state, Enum) else self.state,
            "enabled": self.enabled,
            "dedup_key": self.dedup_key,
            "concurrency_policy": self.concurrency_policy.value if isinstance(self.concurrency_policy, Enum) else self.concurrency_policy,
            "last_fired_at": self.last_fired_at,
            "last_provenance": self.last_provenance.__dict__ if self.last_provenance else None,
            "auth_signature": self.auth_signature,
            "is_recurring_authorized": self.is_recurring_authorized,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trigger":
        prov_dict = data.get("last_provenance")
        prov = EventProvenance(**prov_dict) if isinstance(prov_dict, dict) else None
        return cls(
            trigger_id=data["trigger_id"],
            trigger_type=TriggerType(data["trigger_type"]),
            action_goal=data["action_goal"],
            execution_map=data["execution_map"],
            cron_schedule=data.get("cron_schedule"),
            interval_seconds=data.get("interval_seconds"),
            event_pattern=data.get("event_pattern"),
            condition_fn=data.get("condition_fn"),
            state=TriggerState(data.get("state", TriggerState.REGISTERED.value)),
            enabled=data.get("enabled", True),
            dedup_key=data.get("dedup_key"),
            concurrency_policy=ConcurrencyPolicy(data.get("concurrency_policy", ConcurrencyPolicy.COALESCE.value)),
            last_fired_at=data.get("last_fired_at"),
            last_provenance=prov,
            auth_signature=data.get("auth_signature"),
            is_recurring_authorized=data.get("is_recurring_authorized", False),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
