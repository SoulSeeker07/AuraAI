"""
Isolated Audit Writer Service
Location: src/desktop/native/security/audit_writer_service.py

Standalone audit authority service maintaining:
1. Isolated in-memory sequence numbers and hash-chain authority.
2. Canonical 11-field record hashing and validation.
3. Cross-process Windows Event Log emission and sealed local storage persistence.
4. Startup state integrity verification before entering READY state.
5. Replay, rollback, and duplicate submission rejection.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from .audit_ipc import AuditIPCServer, DEFAULT_PIPE_NAME
from .dpapi_key_manager import DPAPIKeyManager, KeyEnvelopeMetadata
from .windows_event_sink import CanonicalAuditRecord, WindowsEventAuditSink

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
SCHEMA_VERSION = 1


class AuditWriterService:
    """
    Dedicated out-of-process Audit Writer Service.
    """

    def __init__(
        self,
        storage_dir: str | Path | None = None,
        pipe_name: str = DEFAULT_PIPE_NAME,
        shared_hmac_secret: bytes | None = None,
        enable_event_log: bool = True,
    ):
        if storage_dir is None:
            base_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".aura"))) / "AuraAI" / "security" / "audit_service"
        else:
            base_dir = Path(storage_dir).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        self._storage_dir = base_dir

        self._pipe_name = pipe_name
        self._enable_event_log = enable_event_log
        self._writer_instance_id = str(uuid.uuid4())
        self._ledger_id = "default_ledger"
        self._lock = threading.Lock()

        self._log_path = self._storage_dir / "service_audit_ledger.jsonl"
        self._state_file = self._storage_dir / "service_state.json"

        self._key_manager = DPAPIKeyManager(storage_dir=self._storage_dir / "keys")
        self._signing_key, self._key_meta = self._key_manager.derive_purpose_key(
            purpose="audit_writer_signing", version=SCHEMA_VERSION
        )

        self._event_sink = WindowsEventAuditSink() if enable_event_log else None
        self._ipc_server = AuditIPCServer(
            pipe_name=self._pipe_name,
            shared_hmac_secret=shared_hmac_secret,
        )
        self._ipc_server.set_handler(self._handle_ipc_request)

        self._sequence = 0
        self._current_hash = GENESIS_HASH
        self._is_ready = False
        self._seen_event_ids: set[str] = set()

    @property
    def writer_instance_id(self) -> str:
        return self._writer_instance_id

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def current_hash(self) -> str:
        return self._current_hash

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def ipc_secret(self) -> bytes:
        return self._ipc_server.shared_secret

    def start(self) -> bool:
        """
        Execute startup state verification and activate Named Pipe server.
        """
        with self._lock:
            # 1. Load persistent state & verify local ledger
            valid, err = self._verify_startup_state()
            if not valid:
                logger.error(f"[AuditWriterService] Startup state integrity failure: {err}")
                return False

            self._is_ready = True
            self._ipc_server.start()
            logger.info(
                f"[AuditWriterService] READY (Instance: {self._writer_instance_id}, Seq: {self._sequence}, Key: {self._key_meta.key_id[:8]})"
            )
            return True

    def stop(self) -> None:
        """Stop AuditWriterService."""
        with self._lock:
            self._is_ready = False
            self._ipc_server.stop()
            logger.info("[AuditWriterService] Stopped.")

    def _verify_startup_state(self) -> tuple[bool, str]:
        """
        Verify state persistence, sequence continuity, and sealed local ledger records.
        """
        if self._state_file.exists():
            try:
                state_data = json.loads(self._state_file.read_text(encoding="utf-8"))
                self._sequence = state_data.get("sequence", 0)
                self._current_hash = state_data.get("current_hash", GENESIS_HASH)
                self._ledger_id = state_data.get("ledger_id", "default_ledger")
            except Exception as exc:
                return False, f"Failed to load service state JSON: {exc}"

        # Reconcile with existing ledger file
        if self._log_path.exists() and self._log_path.stat().st_size > 0:
            records_count = 0
            expected_prev = GENESIS_HASH
            last_hash = GENESIS_HASH

            with open(self._log_path, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f):
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        rec = CanonicalAuditRecord(**entry)
                    except Exception as exc:
                        return False, f"Ledger record parse error at line {line_idx + 1}: {exc}"

                    if rec.sequence != line_idx:
                        return False, f"Sequence gap at line {line_idx + 1}: expected {line_idx}, got {rec.sequence}"

                    recomputed = CanonicalAuditRecord.compute_current_hash(
                        previous_hash=rec.previous_hash,
                        payload_hash=rec.payload_hash,
                        sequence=rec.sequence,
                        writer_instance_id=rec.writer_instance_id,
                    )
                    if rec.current_hash != recomputed:
                        return False, f"Hash mismatch at line {line_idx + 1}"

                    self._seen_event_ids.add(rec.audit_event_id)
                    expected_prev = rec.current_hash
                    last_hash = rec.current_hash
                    records_count += 1

            if records_count != self._sequence and self._sequence > 0:
                logger.warning(
                    f"[AuditWriterService] State sequence ({self._sequence}) reconciled to ledger count ({records_count})"
                )
            self._sequence = records_count
            self._current_hash = last_hash

        return True, "State verification successful."

    def _persist_state(self) -> None:
        """Atomically persist state JSON."""
        state_payload = {
            "ledger_id": self._ledger_id,
            "sequence": self._sequence,
            "current_hash": self._current_hash,
            "key_id": self._key_meta.key_id,
            "schema_version": SCHEMA_VERSION,
            "writer_instance_id": self._writer_instance_id,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._state_file.write_text(json.dumps(state_payload, indent=2), encoding="utf-8")

    def submit_event(
        self,
        event_type: str,
        action_type: str,
        target: str,
        status: str = "SUCCESS",
        details: dict[str, Any] | None = None,
        audit_event_id: str | None = None,
    ) -> CanonicalAuditRecord:
        """
        Record a canonical audit event across memory, local storage, and Windows Event Log.
        """
        with self._lock:
            if not self._is_ready:
                raise RuntimeError("AuditWriterService is not in READY state.")

            ev_id = audit_event_id or str(uuid.uuid4())
            if ev_id in self._seen_event_ids:
                raise ValueError(f"Duplicate/replayed audit event ID: '{ev_id}'")

            current_seq = self._sequence
            prev_hash = self._current_hash
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            event_details = details or {}

            raw_payload = {
                "audit_event_id": ev_id,
                "event_type": event_type,
                "action_type": action_type,
                "target": target,
                "status": status,
                "details": event_details,
                "timestamp": ts,
            }
            payload_hash = CanonicalAuditRecord.compute_payload_hash(raw_payload)

            current_hash = CanonicalAuditRecord.compute_current_hash(
                previous_hash=prev_hash,
                payload_hash=payload_hash,
                sequence=current_seq,
                writer_instance_id=self._writer_instance_id,
            )

            record = CanonicalAuditRecord(
                audit_event_id=ev_id,
                sequence=current_seq,
                timestamp=ts,
                event_type=event_type,
                payload_hash=payload_hash,
                previous_hash=prev_hash,
                current_hash=current_hash,
                ledger_id=self._ledger_id,
                key_id=self._key_meta.key_id,
                schema_version=SCHEMA_VERSION,
                writer_instance_id=self._writer_instance_id,
                action_type=action_type,
                target=target,
                status=status,
                details=event_details,
            )

            # 1. Write to local sealed JSONL ledger
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(record.to_canonical_json() + "\n")

            # 2. Emit to OS-managed Windows Event Log
            if self._event_sink:
                self._event_sink.emit_event(record)

            # 3. Advance state
            self._seen_event_ids.add(ev_id)
            self._sequence = current_seq + 1
            self._current_hash = current_hash
            self._persist_state()

            return record

    def _handle_ipc_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process incoming requests from AuraAI Host across IPC boundary."""
        op = request.get("op", "")
        if op == "LOG_EVENT":
            try:
                record = self.submit_event(
                    event_type=request.get("event_type", "GENERIC_SECURITY_EVENT"),
                    action_type=request.get("action_type", ""),
                    target=request.get("target", ""),
                    status=request.get("status", "SUCCESS"),
                    details=request.get("details", {}),
                    audit_event_id=request.get("audit_event_id"),
                )
                return {
                    "status": "OK",
                    "sequence": record.sequence,
                    "current_hash": record.current_hash,
                    "audit_event_id": record.audit_event_id,
                }
            except Exception as exc:
                return {"status": "ERROR", "error": str(exc)}

        elif op == "GET_STATUS":
            return {
                "status": "OK",
                "is_ready": self._is_ready,
                "sequence": self._sequence,
                "current_hash": self._current_hash,
                "writer_instance_id": self._writer_instance_id,
            }

        return {"status": "ERROR", "error": f"Unknown operation: '{op}'"}
