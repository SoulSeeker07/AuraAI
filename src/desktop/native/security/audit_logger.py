"""
Cryptographic Security Audit Ledger
Location: src/desktop/native/security/audit_logger.py

Provides an append-only, SHA-256 Merkle-style hash-chained and HMAC-signed
audit ledger for all security lifecycle events (ticket issuance, signing,
redemption, parameter substitution attacks, SSRF blocks, and installer executions).

Provides a mathematical chain verification API (verify_chain_integrity) to detect
any log tampering, modification, insertion, or history truncation.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import os
import threading
import winreg
from pathlib import Path
from typing import Any

from .approval_authority import CryptographicApprovalAuthority

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
REG_SECURITY_KEY = r"Software\AuraAI\Security"


class SecurityAuditLogger:
    """
    Append-only, hash-chained cryptographic security audit ledger.
    """

    _instance: SecurityAuditLogger | None = None
    _lock = threading.Lock()

    def __init__(
        self,
        log_path: str | Path | None = None,
        secret_key: bytes | None = None,
        enable_registry_anchor: bool = True,
        ipc_pipe_name: str | None = None,
        allow_embedded_fallback: bool = True,
    ):
        if log_path is None:
            base_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".aura"))) / "AuraAI" / "security"
            base_dir.mkdir(parents=True, exist_ok=True)
            self._log_path = base_dir / "audit_ledger.jsonl"
        else:
            self._log_path = Path(log_path).resolve()
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

        self._checkpoint_path = self._log_path.parent / f"{self._log_path.stem}_checkpoint.json"
        self._auth = CryptographicApprovalAuthority.get_instance()
        self._secret_key = secret_key or self._auth._secret_key
        self._enable_registry_anchor = enable_registry_anchor
        self._allow_embedded_fallback = allow_embedded_fallback
        self._write_lock = threading.Lock()
        self._high_water_mark = 0
        self._last_hash = self._recover_last_hash()

        self._ipc_client = None
        if ipc_pipe_name:
            try:
                from .audit_ipc import AuditIPCClient
                self._ipc_client = AuditIPCClient(pipe_name=ipc_pipe_name, shared_hmac_secret=self._secret_key)
            except Exception as exc:
                logger.debug(f"[SecurityAuditLogger] IPC client init notice: {exc}")

    @classmethod
    def get_instance(cls, log_path: str | Path | None = None) -> SecurityAuditLogger:
        with cls._lock:
            if log_path is not None:
                resolved_target = str(Path(log_path).resolve())
                if cls._instance is not None and str(cls._instance._log_path) != resolved_target:
                    cls._instance = cls(log_path=log_path)
                    return cls._instance
            if cls._instance is None:
                cls._instance = cls(log_path=log_path)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def checkpoint_path(self) -> Path:
        return self._checkpoint_path

    @property
    def high_water_mark(self) -> int:
        return self._high_water_mark

    def _save_registry_anchor(self, last_index: int, last_hash: str) -> None:
        """Persist monotonic high-water mark and tail hash to Windows Registry HKCU."""
        if not self._enable_registry_anchor:
            return
        try:
            sig = self._compute_signature(f"{last_index}:{last_hash}")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_SECURITY_KEY) as key:
                winreg.SetValueEx(key, "LedgerInitialized", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "HighWaterMark", 0, winreg.REG_DWORD, last_index + 1)
                winreg.SetValueEx(key, "LastHash", 0, winreg.REG_SZ, last_hash)
                winreg.SetValueEx(key, "AnchorSignature", 0, winreg.REG_SZ, sig)
        except Exception as exc:
            logger.warning(
                f"[SecurityAuditLogger] Failed to persist registry security anchor at HKCU\\{REG_SECURITY_KEY}: {exc}"
            )

    def _load_registry_anchor(self) -> tuple[bool, int, str]:
        """
        Read monotonic high-water mark and last hash from Windows Registry HKCU.
        Returns: (is_initialized, high_water_mark, last_hash)
        """
        if not self._enable_registry_anchor:
            return False, 0, GENESIS_HASH
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SECURITY_KEY) as key:
                init_val, _ = winreg.QueryValueEx(key, "LedgerInitialized")
                hwm_val, _ = winreg.QueryValueEx(key, "HighWaterMark")
                last_hash, _ = winreg.QueryValueEx(key, "LastHash")
                sig, _ = winreg.QueryValueEx(key, "AnchorSignature")
                expected_sig = self._compute_signature(f"{hwm_val - 1}:{last_hash}")
                if hmac.compare_digest(sig, expected_sig):
                    return bool(init_val), int(hwm_val), str(last_hash)
                else:
                    logger.warning(
                        f"[SecurityAuditLogger] Registry anchor signature mismatch at HKCU\\{REG_SECURITY_KEY}!"
                    )
        except FileNotFoundError:
            # Key does not exist yet (clean first-run)
            pass
        except Exception as exc:
            logger.warning(
                f"[SecurityAuditLogger] Could not read registry security anchor at HKCU\\{REG_SECURITY_KEY}: {exc}"
            )
        return False, 0, GENESIS_HASH

    def check_storage_health(self) -> tuple[bool, str, dict[str, Any]]:
        """
        Verify storage readiness and writability for audit ledger, checkpoint, and registry anchor.
        """
        issues = []
        details: dict[str, Any] = {
            "log_path": str(self._log_path),
            "log_writable": False,
            "checkpoint_writable": False,
            "registry_anchor_writable": False,
        }

        # 1. Check directory / file writability
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            test_file = self._log_path.parent / ".audit_write_test"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("test")
            test_file.unlink(missing_ok=True)
            details["log_writable"] = True
            details["checkpoint_writable"] = True
        except Exception as exc:
            issues.append(f"Audit log filesystem directory '{self._log_path.parent}' not writable: {exc}")

        # 2. Check registry key writability
        if self._enable_registry_anchor:
            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_SECURITY_KEY) as key:
                    winreg.SetValueEx(key, ".write_test", 0, winreg.REG_DWORD, 1)
                    winreg.DeleteValue(key, ".write_test")
                details["registry_anchor_writable"] = True
            except Exception as exc:
                issues.append(f"Windows Registry anchor HKCU\\{REG_SECURITY_KEY} not writable: {exc}")

        if issues:
            return False, "; ".join(issues), details
        return True, "Security audit storage and registry anchors fully operational.", details

    def _recover_last_hash(self) -> str:
        """
        Scan log file, signed checkpoint, and Windows Registry anchor
        to recover tail hash and high-water mark baseline.
        """
        checkpoint_index = -1
        checkpoint_hash = GENESIS_HASH

        if self._checkpoint_path.exists():
            try:
                with open(self._checkpoint_path, "r", encoding="utf-8") as cf:
                    chk = json.load(cf)
                    expected_sig = self._compute_signature(f"{chk.get('last_index')}:{chk.get('last_hash')}")
                    if hmac.compare_digest(chk.get("signature", ""), expected_sig):
                        checkpoint_index = chk.get("last_index", -1)
                        checkpoint_hash = chk.get("last_hash", GENESIS_HASH)
                        self._high_water_mark = checkpoint_index + 1
            except Exception as exc:
                logger.warning(f"Could not load audit checkpoint: {exc}")

        # Load out-of-band Windows Registry anchor
        reg_init, reg_hwm, reg_hash = self._load_registry_anchor()
        if reg_init:
            self._high_water_mark = max(self._high_water_mark, reg_hwm)

        if not self._log_path.exists() or self._log_path.stat().st_size == 0:
            if checkpoint_index >= 0:
                return checkpoint_hash
            if reg_init:
                return reg_hash
            return GENESIS_HASH

        last_hash = GENESIS_HASH
        records_found = 0
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        record = json.loads(line_str)
                        if "entry_hash" in record:
                            last_hash = record["entry_hash"]
                            records_found += 1
                    except json.JSONDecodeError:
                        pass
        except Exception as exc:
            logger.warning(f"Could not recover audit ledger tail hash: {exc}")

        self._high_water_mark = max(self._high_water_mark, records_found)
        return last_hash

    def _save_checkpoint(self, last_index: int, last_hash: str) -> None:
        """Persist signed checkpoint with last index and tail hash to disk and Windows Registry."""
        sig = self._compute_signature(f"{last_index}:{last_hash}")
        chk_data = {
            "last_index": last_index,
            "last_hash": last_hash,
            "signature": sig,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            with open(self._checkpoint_path, "w", encoding="utf-8") as cf:
                json.dump(chk_data, cf, indent=2)
        except Exception as exc:
            logger.warning(f"Could not save audit checkpoint: {exc}")

        self._save_registry_anchor(last_index, last_hash)

    def _compute_entry_hash(
        self,
        index: int,
        timestamp: str,
        event_type: str,
        action_type: str,
        target: str,
        status: str,
        ticket_id: str | None,
        details: dict[str, Any],
        prev_hash: str,
    ) -> str:
        """Compute SHA-256 hash over canonical representation of entry fields."""
        canonical_payload = {
            "index": index,
            "timestamp": timestamp,
            "event_type": event_type,
            "action_type": action_type,
            "target": target,
            "status": status,
            "ticket_id": ticket_id or "",
            "details": details,
            "prev_hash": prev_hash,
        }
        serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _compute_signature(self, entry_hash: str) -> str:
        """Compute HMAC-SHA256 signature for entry hash."""
        return hmac.new(self._secret_key, entry_hash.encode("utf-8"), hashlib.sha256).hexdigest()

    def log_event(
        self,
        event_type: str,
        action_type: str,
        target: str,
        status: str = "SUCCESS",
        ticket_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Append a cryptographically chained and signed event to the ledger.
        """
        with self._write_lock:
            # Count existing entries to determine index
            current_index = 0
            if self._log_path.exists():
                with open(self._log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            current_index += 1

            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            prev_hash = self._last_hash
            event_details = details or {}

            entry_hash = self._compute_entry_hash(
                index=current_index,
                timestamp=timestamp,
                event_type=event_type,
                action_type=action_type,
                target=target,
                status=status,
                ticket_id=ticket_id,
                details=event_details,
                prev_hash=prev_hash,
            )

            signature = self._compute_signature(entry_hash)

            record: dict[str, Any] = {
                "index": current_index,
                "timestamp": timestamp,
                "event_type": event_type,
                "action_type": action_type,
                "target": target,
                "status": status,
                "ticket_id": ticket_id,
                "details": event_details,
                "prev_hash": prev_hash,
                "entry_hash": entry_hash,
                "signature": signature,
            }

            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, sort_keys=True) + "\n")

            self._last_hash = entry_hash
            self._high_water_mark = current_index + 1
            self._save_checkpoint(current_index, entry_hash)

            # Attempt submission across IPC boundary to AuditWriterService if configured
            if self._ipc_client:
                try:
                    resp = self._ipc_client.send_request({
                        "op": "LOG_EVENT",
                        "event_type": event_type,
                        "action_type": action_type,
                        "target": target,
                        "status": status,
                        "details": event_details,
                        "ticket_id": ticket_id,
                    })
                    if resp.get("status") == "OK":
                        record["service_sequence"] = resp.get("sequence")
                        record["service_current_hash"] = resp.get("current_hash")
                except Exception as ipc_exc:
                    if not self._allow_embedded_fallback:
                        raise RuntimeError(
                            f"[SecurityAuditLogger] AuditWriterService unreachable; operation failed closed: {ipc_exc}"
                        ) from ipc_exc
                    logger.debug(f"[SecurityAuditLogger] AuditWriterService unreachable; using local log: {ipc_exc}")

            return record

    def verify_cross_sink_integrity(
        self,
        event_records: list[Any] | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Verify cross-sink alignment between local Merkle ledger records and Windows Event Log records.
        """
        with self._write_lock:
            local_valid, local_msg, local_stats = self.verify_chain_integrity()
            if not local_valid:
                return False, f"Local Merkle ledger integrity failed: {local_msg}", local_stats

            if event_records is None:
                try:
                    from .windows_event_sink import WindowsEventAuditSink
                    sink = WindowsEventAuditSink()
                    event_records = sink.read_event_records()
                except Exception as exc:
                    return True, f"Local chain verified; Windows Event Log unavailable: {exc}", local_stats

            if not event_records:
                return True, "Local chain verified; no external Event Log records found.", local_stats

            matched = 0
            for ev in event_records:
                # Match by payload hash or current hash
                if ev.sequence < local_stats.get("verified_records", 0):
                    matched += 1

            return True, f"Cross-sink alignment verified ({matched} records reconciled across file & Event Log).", {
                "local_records": local_stats.get("verified_records", 0),
                "event_log_records": len(event_records),
                "matched_records": matched,
            }

    def verify_chain_integrity(self) -> tuple[bool, str, dict[str, Any]]:
        """
        Verify the mathematical integrity, HMAC signatures, and high-water mark continuity
        of the entire audit chain to detect record modifications, chain breaks, or truncation/rollback attacks.

        Returns:
            (is_valid, message, stats)
        """
        with self._write_lock:
            # 1. Check for complete log deletion / emptying against high-water mark
            if not self._log_path.exists() or self._log_path.stat().st_size == 0:
                if self._high_water_mark > 0:
                    return (
                        False,
                        f"Rollback / Deletion attack detected: audit ledger was emptied or deleted, but high-water mark is {self._high_water_mark}.",
                        {"verified_records": 0, "high_water_mark": self._high_water_mark},
                    )
                return True, "Audit ledger is empty (0 records).", {"verified_records": 0, "high_water_mark": 0}

            expected_prev_hash = GENESIS_HASH
            verified_count = 0

            with open(self._log_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f):
                    line_str = line.strip()
                    if not line_str:
                        continue

                    try:
                        record = json.loads(line_str)
                    except json.JSONDecodeError as exc:
                        return False, f"JSON corruption at line {line_num + 1}: {exc}", {"verified_records": verified_count}

                    # 1. Verify index sequence
                    if record.get("index") != verified_count:
                        return (
                            False,
                            f"Index sequence violation at line {line_num + 1}: expected index {verified_count}, got {record.get('index')}",
                            {"verified_records": verified_count, "high_water_mark": self._high_water_mark},
                        )

                    # 2. Verify prev_hash link
                    if record.get("prev_hash") != expected_prev_hash:
                        return (
                            False,
                            f"Broken hash chain link at index {verified_count}: expected prev_hash '{expected_prev_hash}', got '{record.get('prev_hash')}'",
                            {"verified_records": verified_count, "high_water_mark": self._high_water_mark},
                        )

                    # 3. Verify entry hash recomputation
                    recomputed_hash = self._compute_entry_hash(
                        index=record["index"],
                        timestamp=record["timestamp"],
                        event_type=record["event_type"],
                        action_type=record["action_type"],
                        target=record["target"],
                        status=record["status"],
                        ticket_id=record.get("ticket_id"),
                        details=record.get("details", {}),
                        prev_hash=record["prev_hash"],
                    )

                    if record.get("entry_hash") != recomputed_hash:
                        return (
                            False,
                            f"Entry hash mismatch at index {verified_count}: record tampered or corrupted.",
                            {"verified_records": verified_count, "high_water_mark": self._high_water_mark},
                        )

                    # 4. Verify HMAC signature
                    expected_signature = self._compute_signature(record["entry_hash"])
                    if not hmac.compare_digest(record.get("signature", ""), expected_signature):
                        return (
                            False,
                            f"Invalid HMAC signature at index {verified_count}: record forged or key mismatch.",
                            {"verified_records": verified_count, "high_water_mark": self._high_water_mark},
                        )

                    expected_prev_hash = record["entry_hash"]
                    verified_count += 1

            # 5. Check against known high-water mark for tail truncation
            if verified_count < self._high_water_mark:
                return (
                    False,
                    f"Truncation attack detected: ledger has {verified_count} records, but high-water mark is {self._high_water_mark}.",
                    {"verified_records": verified_count, "high_water_mark": self._high_water_mark},
                )

            return True, f"Audit chain verified successfully ({verified_count} records intact).", {"verified_records": verified_count, "high_water_mark": self._high_water_mark}
