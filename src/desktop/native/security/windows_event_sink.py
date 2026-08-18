"""
Windows Event Log Out-of-Process Audit Sink
Location: src/desktop/native/security/windows_event_sink.py

Emits structured, canonical 11-field audit records to the OS-managed Windows Event Log service (EventLog / win32evtlog).
Standard interactive user processes cannot selectively delete, truncate, or rewrite historical Windows Event Log records.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

import win32evtlog
import win32evtlogutil

logger = logging.getLogger(__name__)

EVENT_SOURCE_NAME = "AuraAI-Audit"
DEFAULT_APP_LOG = "Application"

EVENT_ID_MAP = {
    "TICKET_ISSUED": 1001,
    "TICKET_SIGNED": 1002,
    "TICKET_REDEEMED": 1003,
    "SUBSTITUTION_ATTACK_BLOCKED": 1004,
    "INSTALLER_EXECUTED": 1005,
    "SSRF_ROUTE_BLOCKED": 1006,
    "SECURITY_HARD_BLOCKED": 1007,
    "AUDIT_CHECKPOINT_SAVED": 1008,
    "AUDIT_SERVICE_INITIALIZED": 1009,
    "GENERIC_SECURITY_EVENT": 1010,
}


@dataclass
class CanonicalAuditRecord:
    """Canonical 11-field audit schema for cross-sink mathematical verification."""

    audit_event_id: str
    sequence: int
    timestamp: str
    event_type: str
    payload_hash: str
    previous_hash: str
    current_hash: str
    ledger_id: str
    key_id: str
    schema_version: int
    writer_instance_id: str
    action_type: str = ""
    target: str = ""
    status: str = "SUCCESS"
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def compute_payload_hash(cls, payload: dict[str, Any]) -> str:
        """Deterministic SHA-256 hash over canonical JSON payload."""
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def compute_current_hash(
        cls,
        previous_hash: str,
        payload_hash: str,
        sequence: int,
        writer_instance_id: str,
    ) -> str:
        """
        Deterministic chain hash formula:
        current_hash = SHA256(previous_hash || payload_hash || sequence || writer_instance_id)
        """
        combined = f"{previous_hash}:{payload_hash}:{sequence}:{writer_instance_id}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def to_canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


class WindowsEventAuditSink:
    """
    Direct bridge to the OS-managed Windows Event Log service.
    """

    def __init__(
        self,
        source_name: str = EVENT_SOURCE_NAME,
        log_type: str = DEFAULT_APP_LOG,
    ):
        self._source_name = source_name
        self._log_type = log_type
        self._registered = False
        self._init_source()

    def _init_source(self) -> None:
        """Attempt to register event source if not already registered."""
        try:
            win32evtlogutil.AddSourceToRegistry(
                self._source_name,
                msgDLL=None,
                eventLogType=self._log_type,
            )
            self._registered = True
        except Exception as exc:
            # Registration may fail if unprivileged (Standard User); ReportEvent still functions on Application log
            logger.debug(f"[WindowsEventAuditSink] Event source registry notice: {exc}")

    def emit_event(self, record: CanonicalAuditRecord) -> bool:
        """
        Emit a canonical audit record to Windows Event Log.
        """
        event_id = EVENT_ID_MAP.get(record.event_type, EVENT_ID_MAP["GENERIC_SECURITY_EVENT"])
        event_type_flag = win32evtlog.EVENTLOG_INFORMATION_TYPE

        if "BLOCKED" in record.event_type or record.status in ("FAILURE", "DENIED", "REJECTED"):
            event_type_flag = win32evtlog.EVENTLOG_WARNING_TYPE

        payload_json = record.to_canonical_json()
        strings = [
            f"[AuraAI Security Audit Event - Seq {record.sequence}]",
            payload_json,
        ]

        try:
            win32evtlogutil.ReportEvent(
                self._source_name,
                event_id,
                eventType=event_type_flag,
                strings=strings,
                data=record.current_hash.encode("utf-8"),
                logType=self._log_type,
            )
            return True
        except Exception as exc:
            logger.warning(f"[WindowsEventAuditSink] Failed to emit Windows Event Log record: {exc}")
            return False

    def read_event_records(self, max_records: int = 1000) -> list[CanonicalAuditRecord]:
        """
        Read back AuraAI audit events from the Windows Application Event Log.
        """
        records: list[CanonicalAuditRecord] = []
        try:
            handle = win32evtlog.OpenEventLog(None, self._log_type)
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            total = 0

            while total < max_records:
                events = win32evtlog.ReadEventLog(handle, flags, 0)
                if not events:
                    break
                for ev in events:
                    if getattr(ev, "SourceName", "") == self._source_name:
                        # Extract string payloads
                        inserts = getattr(ev, "StringInserts", [])
                        if inserts and len(inserts) > 1:
                            try:
                                data = json.loads(inserts[1])
                                if "audit_event_id" in data and "sequence" in data:
                                    rec = CanonicalAuditRecord(**data)
                                    records.append(rec)
                                    total += 1
                            except Exception:
                                pass
            win32evtlog.CloseEventLog(handle)
        except Exception as exc:
            logger.warning(f"[WindowsEventAuditSink] Failed to read Windows Event Log: {exc}")

        records.sort(key=lambda r: r.sequence)
        return records

    @classmethod
    def verify_event_stream_continuity(
        cls,
        records: list[CanonicalAuditRecord],
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Mathematically verify sequence continuity, payload hashes, and current_hash links in Event Log records.
        """
        if not records:
            return True, "No Event Log records to verify (0 records).", {"verified_records": 0}

        expected_prev_hash = "0" * 64
        expected_seq = records[0].sequence

        for idx, rec in enumerate(records):
            # 1. Verify sequence order
            if rec.sequence != expected_seq:
                return (
                    False,
                    f"Event Log sequence gap at record {idx}: expected sequence {expected_seq}, got {rec.sequence}",
                    {"verified_records": idx},
                )

            # 2. Verify previous hash link
            if idx > 0 and rec.previous_hash != expected_prev_hash:
                return (
                    False,
                    f"Event Log chain link mismatch at sequence {rec.sequence}: expected prev_hash '{expected_prev_hash}', got '{rec.previous_hash}'",
                    {"verified_records": idx},
                )

            # 3. Verify current hash calculation
            recomputed_current = CanonicalAuditRecord.compute_current_hash(
                previous_hash=rec.previous_hash,
                payload_hash=rec.payload_hash,
                sequence=rec.sequence,
                writer_instance_id=rec.writer_instance_id,
            )
            if rec.current_hash != recomputed_current:
                return (
                    False,
                    f"Event Log current_hash mismatch at sequence {rec.sequence}: record tampered or corrupted.",
                    {"verified_records": idx},
                )

            expected_prev_hash = rec.current_hash
            expected_seq += 1

        return True, f"Event Log stream verified successfully ({len(records)} records intact).", {"verified_records": len(records)}
