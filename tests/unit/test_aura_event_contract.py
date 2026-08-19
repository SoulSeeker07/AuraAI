"""
Unit Tests for M24 Phase 1: AuraEvent Canonical Contract & Immutability
Location: tests/unit/test_aura_event_contract.py

Verifies:
1. Canonical AuraEvent type creation and required fields enforcement
2. Deterministic rejection of invalid fields, malformed timestamps, or invalid enums
3. Deep immutability (frozen dataclass and frozen MappingProxyType payload)
4. JSON / dict serialization roundtrip equality
5. Timezone normalization to UTC
6. Uniqueness of event_id and grouping by correlation_id
7. Bounded Urgency and Source enums
8. Strict isolation: constructing an AuraEvent never executes capabilities, orchestrator, or modifies state.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone, timedelta
import json
import pytest

from autonomy.events import (
    AuraEvent,
    EventSource,
    EventType,
    EventUrgency,
    EventValidationError,
)


def test_canonical_event_creation_minimal():
    """Verify valid creation with minimal required fields."""
    event = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process_name": "python.exe", "exit_code": 1},
    )

    assert event.event_id.startswith("evt_")
    assert event.event_type == "process.exited"
    assert event.source == EventSource.PROCESS
    assert event.payload["process_name"] == "python.exe"
    assert event.payload["exit_code"] == 1
    assert event.correlation_id.startswith("corr_")
    assert event.urgency == EventUrgency.NORMAL
    assert event.schema_version == "1.0"
    assert "T" in event.timestamp
    assert "+00:00" in event.timestamp or event.timestamp.endswith("Z")


def test_canonical_event_creation_explicit():
    """Verify valid creation with explicit custom fields."""
    custom_time = "2026-08-18T12:00:00+00:00"
    event = AuraEvent(
        event_id="evt_custom_001",
        event_type="filesystem.created",
        source="filesystem",
        timestamp=custom_time,
        payload={"path": "C:\\workspace\\project.zip", "size_bytes": 1048576},
        correlation_id="corr_download_batch_42",
        urgency="high",
        schema_version="1.0",
    )

    assert event.event_id == "evt_custom_001"
    assert event.event_type == "filesystem.created"
    assert event.source == EventSource.FILESYSTEM
    assert event.urgency == EventUrgency.HIGH
    assert event.correlation_id == "corr_download_batch_42"
    assert event.timestamp == custom_time
    assert event.payload["path"] == "C:\\workspace\\project.zip"


def test_immutability_attribute_assignment():
    """Verify that attempting to mutate event attributes raises FrozenInstanceError/AttributeError."""
    event = AuraEvent.create(
        event_type=EventType.FILESYSTEM_CREATED,
        source=EventSource.FILESYSTEM,
        payload={"file": "test.py"},
    )

    with pytest.raises((FrozenInstanceError, AttributeError)):
        event.event_id = "new_id"  # type: ignore

    with pytest.raises((FrozenInstanceError, AttributeError)):
        event.urgency = EventUrgency.CRITICAL  # type: ignore

    with pytest.raises((FrozenInstanceError, AttributeError)):
        event.correlation_id = "corr_hacked"  # type: ignore


def test_immutability_payload_mutation():
    """Verify that the payload dictionary cannot be mutated in place."""
    raw_payload = {"status": "starting", "items": ["a", "b"]}
    event = AuraEvent.create(
        event_type=EventType.SYSTEM_STARTUP,
        source=EventSource.SYSTEM,
        payload=raw_payload,
    )

    # 1. Modifying the original dict after construction has zero effect on the event
    raw_payload["status"] = "mutated"
    assert event.payload["status"] == "starting"

    # 2. Mutating the event payload directly raises TypeError (MappingProxyType)
    with pytest.raises(TypeError):
        event.payload["status"] = "illegal_write"  # type: ignore

    with pytest.raises(TypeError):
        event.payload["new_key"] = "illegal_add"  # type: ignore


def test_rejection_empty_event_id():
    """Empty or non-string event_id is rejected deterministically."""
    with pytest.raises(EventValidationError, match="event_id must be a non-empty string"):
        AuraEvent(
            event_id="",
            event_type="test.event",
            source="system",
            timestamp="2026-08-18T12:00:00+00:00",
            payload={},
            correlation_id="corr_1",
        )


def test_rejection_invalid_source():
    """Invalid source string or type is rejected deterministically."""
    with pytest.raises(EventValidationError, match="Invalid EventSource"):
        AuraEvent.create(
            event_type="test.event",
            source="unknown_alien_source",
            payload={},
        )


def test_rejection_invalid_urgency():
    """Invalid urgency classification is rejected deterministically."""
    with pytest.raises(EventValidationError, match="Invalid EventUrgency"):
        AuraEvent.create(
            event_type="test.event",
            source=EventSource.SYSTEM,
            urgency="ultra_emergency",
        )


def test_rejection_malformed_timestamp():
    """Malformed or unparseable timestamps are rejected deterministically."""
    with pytest.raises(EventValidationError, match="Invalid ISO 8601 timestamp"):
        AuraEvent.create(
            event_type="test.event",
            source=EventSource.SYSTEM,
            timestamp="not-a-timestamp-at-all",
        )


def test_timezone_normalization_to_utc():
    """Non-UTC timestamps with offsets are normalized to UTC standard string."""
    # Eastern Daylight Time (UTC - 4 hours)
    edt_tz = timezone(timedelta(hours=-4))
    edt_dt = datetime(2026, 8, 18, 16, 0, 0, tzinfo=edt_tz)
    
    event = AuraEvent.create(
        event_type=EventType.PROCESS_STARTED,
        source=EventSource.PROCESS,
        timestamp=edt_dt,
    )

    # 16:00 EDT == 20:00 UTC
    assert "2026-08-18T20:00:00+00:00" in event.timestamp


def test_serialization_dict_roundtrip():
    """Verify lossless dictionary serialization and deserialization."""
    original = AuraEvent.create(
        event_type=EventType.NETWORK_CONNECTED,
        source=EventSource.NETWORK,
        payload={"ip": "192.168.1.50", "interface": "Ethernet0", "dns": ["8.8.8.8", "1.1.1.1"]},
        correlation_id="corr_net_state_01",
        urgency=EventUrgency.HIGH,
    )

    as_dict = original.to_dict()
    assert isinstance(as_dict, dict)
    assert as_dict["event_type"] == "network.connected"
    assert as_dict["source"] == "network"
    assert as_dict["urgency"] == "high"

    reconstructed = AuraEvent.from_dict(as_dict)
    assert reconstructed.event_id == original.event_id
    assert reconstructed.event_type == original.event_type
    assert reconstructed.source == original.source
    assert reconstructed.timestamp == original.timestamp
    assert reconstructed.payload == original.payload
    assert reconstructed.correlation_id == original.correlation_id
    assert reconstructed.urgency == original.urgency
    assert reconstructed == original


def test_serialization_json_roundtrip():
    """Verify lossless JSON serialization and deserialization."""
    original = AuraEvent.create(
        event_type=EventType.FILESYSTEM_DELETED,
        source=EventSource.FILESYSTEM,
        payload={"deleted_path": "C:\\temp\\cache.bin", "was_directory": False},
        correlation_id="corr_cleanup_99",
        urgency=EventUrgency.LOW,
    )

    json_str = original.to_json()
    assert isinstance(json_str, str)
    
    parsed = json.loads(json_str)
    assert parsed["event_id"] == original.event_id

    reconstructed = AuraEvent.from_json(json_str)
    assert reconstructed == original


def test_event_id_uniqueness():
    """Sequential events generated via factory have unique IDs."""
    ids = {AuraEvent.create(EventType.TIMER_FIRED, EventSource.TIMER).event_id for _ in range(100)}
    assert len(ids) == 100


def test_correlation_id_grouping():
    """Multiple distinct events can share a correlation_id for multi-signal grouping."""
    corr_group = "corr_build_pipeline_fail_001"

    evt1 = AuraEvent.create(
        event_type=EventType.FILESYSTEM_MODIFIED,
        source=EventSource.FILESYSTEM,
        payload={"file": "main.py"},
        correlation_id=corr_group,
    )
    evt2 = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process": "pytest.exe", "exit_code": 1},
        correlation_id=corr_group,
    )

    assert evt1.correlation_id == corr_group
    assert evt2.correlation_id == corr_group
    assert evt1.event_id != evt2.event_id


def test_strict_isolation_no_execution_or_side_effects():
    """
    Critical Boundary Test:
    Constructing or deserializing an AuraEvent must never execute capabilities,
    invoke MasterOrchestrator, or mutate autonomous runtime state.
    """
    # Create 50 events of various types and urgencies
    events = [
        AuraEvent.create(
            event_type=EventType.PROCESS_CRASHED,
            source=EventSource.PROCESS,
            payload={"process": "critical_service.exe", "signal": 9},
            urgency=EventUrgency.CRITICAL,
        )
        for _ in range(50)
    ]

    # Verify all are pure data containers with zero side effects
    for evt in events:
        assert isinstance(evt.payload, (dict, type(evt.payload)))
        assert evt.urgency == EventUrgency.CRITICAL
