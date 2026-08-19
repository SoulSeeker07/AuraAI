"""
AuraEvent Canonical Contract & Schema Validation (M24 Phase 1)
Location: src/autonomy/events.py

Defines the immutable, strongly-typed, schema-validatable AuraEvent contract.
This is the single canonical representation for all system, hardware, and environment
telemetry ingested into the AuraAI autonomous runtime.

Architectural Invariants:
1. Facts Only: Contains raw telemetry and observations, zero decisions or intent.
2. Immutability: Frozen after construction, payload protected from in-place mutation.
3. Strict Isolation: Zero dependencies on orchestrators, capability registries, or execution engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from types import MappingProxyType
from typing import Any, Mapping
import uuid


class EventValidationError(ValueError):
    """Raised when an AuraEvent fails schema or type validation."""
    pass


class EventSource(str, Enum):
    """Standardized event sources within the Aura operating environment."""
    FILESYSTEM = "filesystem"
    PROCESS = "process"
    NETWORK = "network"
    APPLICATION = "application"
    SYSTEM = "system"
    TIMER = "timer"
    USER = "user"
    EXTERNAL = "external"

    @classmethod
    def from_value(cls, value: Any) -> "EventSource":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value.lower())
            except ValueError:
                raise EventValidationError(
                    f"Invalid EventSource '{value}'. Must be one of: {[e.value for e in cls]}"
                )
        raise EventValidationError(f"Expected EventSource or str, got {type(value).__name__}")


class EventUrgency(str, Enum):
    """Bounded urgency classification for event processing priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_value(cls, value: Any) -> "EventUrgency":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value.lower())
            except ValueError:
                raise EventValidationError(
                    f"Invalid EventUrgency '{value}'. Must be one of: {[e.value for e in cls]}"
                )
        raise EventValidationError(f"Expected EventUrgency or str, got {type(value).__name__}")


class EventType(str, Enum):
    """Standard event type vocabulary for known system signals."""
    # Filesystem
    FILESYSTEM_CREATED = "filesystem.created"
    FILESYSTEM_MODIFIED = "filesystem.modified"
    FILESYSTEM_DELETED = "filesystem.deleted"
    FILESYSTEM_MOVED = "filesystem.moved"

    # Process
    PROCESS_STARTED = "process.started"
    PROCESS_EXITED = "process.exited"
    PROCESS_CRASHED = "process.crashed"

    # Network
    NETWORK_CONNECTED = "network.connected"
    NETWORK_DISCONNECTED = "network.disconnected"
    NETWORK_REQUEST_RECEIVED = "network.request_received"

    # Application & Window
    APPLICATION_FOCUSED = "application.focused"
    APPLICATION_LAUNCHED = "application.launched"
    APPLICATION_CLOSED = "application.closed"

    # System & Hardware
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_POWER_CHANGED = "system.power_changed"
    SYSTEM_BATTERY_LOW = "system.battery_low"

    # Temporal & Scheduler
    TIMER_FIRED = "timer.fired"
    INTERVAL_TICK = "timer.interval_tick"
    CRON_TRIGGER = "timer.cron_trigger"

    # Custom
    CUSTOM = "custom"


def _freeze_payload(data: Any) -> Any:
    """Recursively freeze dictionaries into MappingProxyType and lists into tuples."""
    if isinstance(data, dict):
        return MappingProxyType({k: _freeze_payload(v) for k, v in data.items()})
    elif isinstance(data, (list, tuple)):
        return tuple(_freeze_payload(item) for item in data)
    elif isinstance(data, set):
        return frozenset(_freeze_payload(item) for item in data)
    return data


def _unfreeze_payload(data: Any) -> Any:
    """Recursively unfreeze MappingProxyType and tuples back into standard dicts and lists for serialization."""
    if isinstance(data, (Mapping, MappingProxyType)):
        return {k: _unfreeze_payload(v) for k, v in data.items()}
    elif isinstance(data, tuple):
        return [_unfreeze_payload(item) for item in data]
    elif isinstance(data, frozenset):
        return [_unfreeze_payload(item) for item in data]
    return data


def _parse_and_validate_utc_timestamp(ts_val: Any) -> str:
    """Validates and standardizes ISO 8601 timestamps to UTC ISO format."""
    if not isinstance(ts_val, str):
        raise EventValidationError(f"Timestamp must be an ISO 8601 string, got {type(ts_val).__name__}")
    
    ts_clean = ts_val.strip()
    if not ts_clean:
        raise EventValidationError("Timestamp string cannot be empty")

    try:
        # Standardize Z suffix to +00:00 for fromisoformat compatibility
        normalized = ts_clean.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            # Naive timestamps assumed UTC
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # Convert timezone aware to UTC
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    except Exception as e:
        raise EventValidationError(f"Invalid ISO 8601 timestamp '{ts_val}': {e}") from e


@dataclass(frozen=True, init=False)
class AuraEvent:
    """
    The canonical, immutable event envelope for AuraAI.

    Attributes:
        event_id: Unique event identifier (format: evt_<uuid4_hex>)
        event_type: Categorized event type string (e.g. 'filesystem.created', 'process.exited')
        source: Provenance source category (EventSource enum value)
        timestamp: Deterministic UTC ISO 8601 timestamp string
        payload: Immutable mapping containing raw telemetry facts
        correlation_id: Grouping identifier linking causally related events
        urgency: Processing urgency (EventUrgency enum value)
        schema_version: Schema contract version (default: '1.0')
    """
    event_id: str
    event_type: str
    source: EventSource
    timestamp: str
    payload: MappingProxyType[str, Any]
    correlation_id: str
    urgency: EventUrgency
    schema_version: str

    def __init__(
        self,
        event_id: str,
        event_type: str | EventType,
        source: EventSource | str,
        timestamp: str,
        payload: Mapping[str, Any] | dict[str, Any],
        correlation_id: str,
        urgency: EventUrgency | str = EventUrgency.NORMAL,
        schema_version: str = "1.0",
    ) -> None:
        # 1. Validate event_id
        if not isinstance(event_id, str) or not event_id.strip():
            raise EventValidationError("event_id must be a non-empty string")
        object.__setattr__(self, "event_id", event_id.strip())

        # 2. Validate event_type
        if isinstance(event_type, EventType):
            resolved_type = event_type.value
        elif isinstance(event_type, str) and event_type.strip():
            resolved_type = event_type.strip()
        else:
            raise EventValidationError("event_type must be a non-empty string or EventType enum")
        object.__setattr__(self, "event_type", resolved_type)

        # 3. Validate source
        resolved_source = EventSource.from_value(source)
        object.__setattr__(self, "source", resolved_source)

        # 4. Validate & standardize timestamp
        utc_ts = _parse_and_validate_utc_timestamp(timestamp)
        object.__setattr__(self, "timestamp", utc_ts)

        # 5. Validate & freeze payload
        if not isinstance(payload, (dict, Mapping)):
            raise EventValidationError(f"payload must be a dict/mapping, got {type(payload).__name__}")
        frozen_payload = _freeze_payload(dict(payload))
        object.__setattr__(self, "payload", frozen_payload)

        # 6. Validate correlation_id
        if not isinstance(correlation_id, str) or not correlation_id.strip():
            raise EventValidationError("correlation_id must be a non-empty string")
        object.__setattr__(self, "correlation_id", correlation_id.strip())

        # 7. Validate urgency
        resolved_urgency = EventUrgency.from_value(urgency)
        object.__setattr__(self, "urgency", resolved_urgency)

        # 8. Schema version
        if not isinstance(schema_version, str) or not schema_version.strip():
            raise EventValidationError("schema_version must be a non-empty string")
        object.__setattr__(self, "schema_version", schema_version.strip())

    @classmethod
    def create(
        cls,
        event_type: str | EventType,
        source: EventSource | str,
        payload: dict[str, Any] | Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
        urgency: EventUrgency | str = EventUrgency.NORMAL,
        timestamp: str | datetime | None = None,
        event_id: str | None = None,
        schema_version: str = "1.0",
    ) -> "AuraEvent":
        """
        Convenience factory to create a fully validated, canonical AuraEvent with safe defaults.
        """
        # Generated unique event_id if not provided
        resolved_event_id = event_id or f"evt_{uuid.uuid4().hex}"
        
        # Generated correlation_id if not provided
        resolved_corr_id = correlation_id or f"corr_{uuid.uuid4().hex}"

        # Resolve timestamp
        if timestamp is None:
            resolved_ts = datetime.now(timezone.utc).isoformat()
        elif isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                resolved_ts = timestamp.replace(tzinfo=timezone.utc).isoformat()
            else:
                resolved_ts = timestamp.astimezone(timezone.utc).isoformat()
        elif isinstance(timestamp, str):
            resolved_ts = timestamp
        else:
            raise EventValidationError(f"Invalid timestamp type: {type(timestamp).__name__}")

        resolved_payload = payload if payload is not None else {}

        return cls(
            event_id=resolved_event_id,
            event_type=event_type,
            source=source,
            timestamp=resolved_ts,
            payload=resolved_payload,
            correlation_id=resolved_corr_id,
            urgency=urgency,
            schema_version=schema_version,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "payload": _unfreeze_payload(self.payload),
            "correlation_id": self.correlation_id,
            "urgency": self.urgency.value,
            "schema_version": self.schema_version,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Serialize event to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuraEvent":
        """Reconstruct AuraEvent from a dictionary with strict validation."""
        if not isinstance(data, dict):
            raise EventValidationError(f"Expected dict for AuraEvent.from_dict, got {type(data).__name__}")

        required_keys = {"event_id", "event_type", "source", "timestamp", "payload", "correlation_id"}
        missing = required_keys - set(data.keys())
        if missing:
            raise EventValidationError(f"Missing required fields in event dictionary: {sorted(missing)}")

        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            source=data["source"],
            timestamp=data["timestamp"],
            payload=data["payload"],
            correlation_id=data["correlation_id"],
            urgency=data.get("urgency", EventUrgency.NORMAL),
            schema_version=data.get("schema_version", "1.0"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AuraEvent":
        """Deserialize event from a JSON string."""
        if not isinstance(json_str, str):
            raise EventValidationError(f"Expected string for from_json, got {type(json_str).__name__}")
        try:
            data = json.loads(json_str)
        except Exception as e:
            raise EventValidationError(f"Malformed JSON for AuraEvent: {e}") from e
        return cls.from_dict(data)

    def __repr__(self) -> str:
        return (
            f"AuraEvent(id='{self.event_id}', type='{self.event_type}', "
            f"source='{self.source.value}', urgency='{self.urgency.value}', "
            f"corr='{self.correlation_id}', ts='{self.timestamp}')"
        )
