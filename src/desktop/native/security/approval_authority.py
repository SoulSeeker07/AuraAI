"""
Cryptographic Approval Authority — Shared Human-in-the-Loop Authorization Service
Location: src/desktop/native/security/approval_authority.py

Provides HMAC-SHA256 cryptographic ticket generation, human signing, and verification
to prevent LLM self-authorization, parameter tampering, and replay attacks across
all native desktop managers (Terminal, Software, Settings, Security, File).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ApprovalTicket:
    """Represents a pending or authorized human-in-the-loop approval ticket."""

    ticket_id: str
    action_type: str
    target: str
    action_hash: str
    created_at: float
    expires_at: float
    is_redeemed: bool = False
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def parameters(self) -> dict[str, Any]:
        """Convenience alias for metadata dictionary holding parameters."""
        return self.metadata

    @property
    def command_hash(self) -> str:
        """Backward compatibility alias for TerminalManager tickets."""
        return self.action_hash


class CryptographicApprovalAuthority:
    """
    Unified Process-Wide Cryptographic Approval Authority.

    Manages HMAC-SHA256 cryptographic ticket generation, human signing,
    and single-use verification across all native desktop managers.
    """

    _instance: Optional["CryptographicApprovalAuthority"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, use_dpapi_kdf: bool = True) -> None:
        if use_dpapi_kdf:
            try:
                from .dpapi_key_manager import DPAPIKeyManager
                self._key_manager = DPAPIKeyManager()
                self._secret_key, self._key_meta = self._key_manager.derive_purpose_key(
                    purpose="action_approval_signing", version=1
                )
            except Exception as exc:
                logger.debug(f"[CryptographicApprovalAuthority] DPAPI KDF fallback to ephemeral token: {exc}")
                self._secret_key = secrets.token_bytes(32)
                self._key_meta = None
        else:
            self._secret_key = secrets.token_bytes(32)
            self._key_meta = None
        self._tickets: dict[str, ApprovalTicket] = {}
        self._ticket_lock: threading.Lock = threading.Lock()
        self._load_persisted_tickets()

    def _get_storage_path(self) -> Path:
        p = Path(__file__).resolve().parents[4] / "storage" / "approval_tickets.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _persist_tickets(self) -> None:
        try:
            sp = self._get_storage_path()
            data = {}
            for tid, t in self._tickets.items():
                data[tid] = {
                    "ticket_id": t.ticket_id,
                    "action_type": t.action_type,
                    "target": t.target,
                    "action_hash": t.action_hash,
                    "created_at": t.created_at,
                    "expires_at": t.expires_at,
                    "is_redeemed": t.is_redeemed,
                    "description": t.description,
                    "metadata": t.metadata,
                }
            sp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Failed to persist tickets: {e}")

    def _load_persisted_tickets(self) -> None:
        try:
            sp = self._get_storage_path()
            if not sp.exists():
                return
            data = json.loads(sp.read_text(encoding="utf-8"))
            now = time.time()
            for tid, td in data.items():
                if tid not in self._tickets and td.get("expires_at", 0) > now:
                    self._tickets[tid] = ApprovalTicket(
                        ticket_id=td["ticket_id"],
                        action_type=td["action_type"],
                        target=td["target"],
                        action_hash=td["action_hash"],
                        created_at=td["created_at"],
                        expires_at=td["expires_at"],
                        is_redeemed=td.get("is_redeemed", False),
                        description=td.get("description", ""),
                        metadata=td.get("metadata", {}),
                    )
        except Exception as e:
            logger.debug(f"Failed to load persisted tickets: {e}")

    @classmethod
    def get_instance(cls) -> "CryptographicApprovalAuthority":
        """Get or create the singleton instance of CryptographicApprovalAuthority."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for isolated unit testing)."""
        with cls._lock:
            cls._instance = None

    def compute_action_hash(
        self,
        action_type: str,
        target: str,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        """
        Compute deterministic SHA-256 hash for a structured action payload.
        Canonicalizes parameters by sorting keys and filtering out approval ticket metadata.
        """
        params_str = ""
        if parameters:
            filtered_params = {
                k: v
                for k, v in parameters.items()
                if k not in {"approval_ticket_id", "approval_signature", "user_authorized"}
            }
            try:
                params_str = json.dumps(filtered_params, sort_keys=True, default=str)
            except Exception:
                params_str = str(sorted(filtered_params.items()))

        payload = f"{action_type.lower().strip()}:{target.strip()}:{params_str}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def compute_command_hash(self, command: str, cwd: str) -> str:
        """
        Compute command hash matching TerminalManager format: '{cwd}:{command}'.
        """
        payload = f"{cwd.lower().strip()}:{command.strip()}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def create_ticket(
        self,
        action_type: str,
        target: str,
        parameters: dict[str, Any] | None = None,
        ttl_seconds: float = 300.0,
        description: str = "",
    ) -> str:
        """
        Create an un-signed ticket for human approval for any manager action.
        Returns public ticket_id.
        """
        ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
        action_hash = self.compute_action_hash(action_type, target, parameters)
        now = time.time()

        ticket = ApprovalTicket(
            ticket_id=ticket_id,
            action_type=action_type,
            target=target,
            action_hash=action_hash,
            created_at=now,
            expires_at=now + ttl_seconds,
            is_redeemed=False,
            description=description or f"{action_type}: {target}",
            metadata=parameters or {},
        )

        with self._ticket_lock:
            self._tickets[ticket_id] = ticket
            self._persist_tickets()

        try:
            from .audit_logger import SecurityAuditLogger
            SecurityAuditLogger.get_instance().log_event(
                event_type="TICKET_ISSUED",
                action_type=action_type,
                target=target,
                ticket_id=ticket_id,
                status="PENDING",
                details=parameters or {},
            )
        except Exception as audit_err:
            logger.warning(f"Audit log failed on ticket creation: {audit_err}")

        logger.info(
            f"Issued approval ticket {ticket_id} for action '{action_type}' on '{target}' (TTL: {ttl_seconds}s)"
        )
        return ticket_id

    def create_command_ticket(
        self, command: str, cwd: str, ttl_seconds: float = 300.0
    ) -> str:
        """
        Create an un-signed ticket specifically for shell command execution.
        Returns public ticket_id.
        """
        ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
        cmd_hash = self.compute_command_hash(command, cwd)
        now = time.time()

        ticket = ApprovalTicket(
            ticket_id=ticket_id,
            action_type="command",
            target=command,
            action_hash=cmd_hash,
            created_at=now,
            expires_at=now + ttl_seconds,
            is_redeemed=False,
            description=f"Terminal command: {command} in {cwd}",
            metadata={"command": command, "cwd": cwd},
        )

        with self._ticket_lock:
            self._tickets[ticket_id] = ticket
            self._persist_tickets()

        try:
            from .audit_logger import SecurityAuditLogger
            SecurityAuditLogger.get_instance().log_event(
                event_type="TICKET_ISSUED",
                action_type="command",
                target=command,
                ticket_id=ticket_id,
                status="PENDING",
                details={"cwd": cwd},
            )
        except Exception as audit_err:
            logger.warning(f"Audit log failed on command ticket creation: {audit_err}")

        logger.info(f"Issued command approval ticket {ticket_id} for '{command}' in '{cwd}'")
        return ticket_id

    def generate_human_signature(self, ticket_id: str) -> str | None:
        """
        Signs the ticket using the process HMAC secret. Emits TICKET_SIGNED.

        This is the single signing chokepoint for the human approval channel (UI / CLI),
        but it is NOT a trust boundary: the secret is one process-wide value on a
        singleton, so any in-process caller can mint a valid signature. What it stops is
        LLM self-authorization — a model cannot emit a signature as text, it must route
        through this auditable call. It does not prove a human was present.
        See docs/adr/0007-hmac-approval-trust-boundary.md before relying on it as one.
        """
        with self._ticket_lock:
            self._load_persisted_tickets()
            ticket = self._tickets.get(ticket_id)
            if not ticket or ticket.is_redeemed or time.time() > ticket.expires_at:
                return None

            msg = f"{ticket.ticket_id}:{ticket.action_hash}".encode("utf-8")
            sig = hmac.new(self._secret_key, msg, hashlib.sha256).hexdigest()

            try:
                from .audit_logger import SecurityAuditLogger
                SecurityAuditLogger.get_instance().log_event(
                    event_type="TICKET_SIGNED",
                    action_type=ticket.action_type,
                    target=ticket.target,
                    ticket_id=ticket_id,
                    status="SIGNED",
                    details={"action_hash": ticket.action_hash},
                )
            except Exception as audit_err:
                logger.warning(f"Audit log failed on ticket signing: {audit_err}")

            return sig

    generate_ticket = create_ticket
    sign_ticket = generate_human_signature

    def verify_and_redeem(
        self,
        ticket_id: str,
        signature: str,
        action_type: str,
        target: str,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """
        Verify human signature with constant-time comparison and mark ticket as redeemed.
        """
        with self._ticket_lock:
            self._load_persisted_tickets()
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                self._log_audit_failure("TICKET_NOT_FOUND", action_type, target, ticket_id, "Invalid or unknown approval ticket.")
                return False, "Invalid or unknown approval ticket."

            if ticket.is_redeemed:
                self._log_audit_failure("TICKET_ALREADY_REDEEMED", action_type, target, ticket_id, "Approval ticket has already been redeemed.")
                return False, "Approval ticket has already been redeemed."

            if time.time() > ticket.expires_at:
                self._log_audit_failure("TICKET_EXPIRED", action_type, target, ticket_id, "Approval ticket has expired.")
                return False, "Approval ticket has expired."

            expected_hash = self.compute_action_hash(action_type, target, parameters)
            cmd_hash = self.compute_command_hash(action_type, target)
            if ticket.action_hash != expected_hash and ticket.action_hash != cmd_hash:
                self._log_audit_failure(
                    "SUBSTITUTION_ATTACK_BLOCKED",
                    action_type,
                    target,
                    ticket_id,
                    "Action payload or command does not match approval ticket.",
                    {"expected_hash": expected_hash, "ticket_hash": ticket.action_hash},
                )
                return False, "Action payload or command does not match approval ticket."

            expected_msg = f"{ticket.ticket_id}:{ticket.action_hash}".encode("utf-8")
            expected_sig = hmac.new(self._secret_key, expected_msg, hashlib.sha256).hexdigest()

            if not hmac.compare_digest(expected_sig, signature):
                self._log_audit_failure("SIGNATURE_FORGERY_BLOCKED", action_type, target, ticket_id, "Cryptographic signature verification failed.")
                return False, "Cryptographic signature verification failed (forged or invalid token)."

            # Redeem ticket (single-use enforcement)
            ticket.is_redeemed = True
            self._persist_tickets()
            try:
                from .audit_logger import SecurityAuditLogger
                SecurityAuditLogger.get_instance().log_event(
                    event_type="TICKET_REDEEMED",
                    action_type=action_type,
                    target=target,
                    ticket_id=ticket_id,
                    status="REDEEMED",
                    details=parameters or {},
                )
            except Exception as audit_err:
                logger.warning(f"Audit log failed on ticket redemption: {audit_err}")

            logger.info(f"Redeemed approval ticket {ticket_id} for action '{action_type}'")
            return True, "Ticket verified and redeemed successfully."

    def verify_and_redeem_command(
        self, ticket_id: str, signature: str, command: str, cwd: str
    ) -> tuple[bool, str]:
        """
        Verify human signature for terminal command execution and mark ticket as redeemed.
        """
        with self._ticket_lock:
            self._load_persisted_tickets()
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                self._log_audit_failure("TICKET_NOT_FOUND", "command", command, ticket_id, "Invalid or unknown approval ticket.")
                return False, "Invalid or unknown approval ticket."

            if ticket.is_redeemed:
                self._log_audit_failure("TICKET_ALREADY_REDEEMED", "command", command, ticket_id, "Approval ticket has already been redeemed.")
                return False, "Approval ticket has already been redeemed."

            if time.time() > ticket.expires_at:
                self._log_audit_failure("TICKET_EXPIRED", "command", command, ticket_id, "Approval ticket has expired.")
                return False, "Approval ticket has expired."

            expected_hash = self.compute_command_hash(command, cwd)
            if ticket.action_hash != expected_hash:
                self._log_audit_failure(
                    "SUBSTITUTION_ATTACK_BLOCKED",
                    "command",
                    command,
                    ticket_id,
                    "Command or working directory does not match approval ticket.",
                    {"expected_hash": expected_hash, "ticket_hash": ticket.action_hash, "cwd": cwd},
                )
                return False, "Command or working directory does not match approval ticket."

            expected_msg = f"{ticket.ticket_id}:{ticket.action_hash}".encode("utf-8")
            expected_sig = hmac.new(self._secret_key, expected_msg, hashlib.sha256).hexdigest()

            if not hmac.compare_digest(expected_sig, signature):
                self._log_audit_failure("SIGNATURE_FORGERY_BLOCKED", "command", command, ticket_id, "Cryptographic signature verification failed.")
                return False, "Cryptographic signature verification failed (forged or invalid token)."

            # Redeem ticket (single-use enforcement)
            ticket.is_redeemed = True
            try:
                from .audit_logger import SecurityAuditLogger
                SecurityAuditLogger.get_instance().log_event(
                    event_type="TICKET_REDEEMED",
                    action_type="command",
                    target=command,
                    ticket_id=ticket_id,
                    status="REDEEMED",
                    details={"cwd": cwd},
                )
            except Exception as audit_err:
                logger.warning(f"Audit log failed on command ticket redemption: {audit_err}")

            logger.info(f"Redeemed command approval ticket {ticket_id} for '{command}'")
            return True, "Ticket verified and redeemed successfully."

    def _log_audit_failure(
        self,
        event_type: str,
        action_type: str,
        target: str,
        ticket_id: str | None,
        reason: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        try:
            from .audit_logger import SecurityAuditLogger
            details = {"reason": reason}
            if extra:
                details.update(extra)
            SecurityAuditLogger.get_instance().log_event(
                event_type=event_type,
                action_type=action_type,
                target=target,
                ticket_id=ticket_id,
                status="DENIED",
                details=details,
            )
        except Exception as audit_err:
            logger.warning(f"Audit log failure record error: {audit_err}")

    def get_ticket(self, ticket_id: str) -> ApprovalTicket | None:
        """Lookup ticket by ID."""
        with self._ticket_lock:
            self._load_persisted_tickets()
            return self._tickets.get(ticket_id)

    def get_pending_tickets(self) -> list[ApprovalTicket]:
        """Return list of unredeemed, unexpired tickets awaiting approval."""
        with self._ticket_lock:
            self._load_persisted_tickets()
            now = time.time()
            return [
                t for t in self._tickets.values()
                if not t.is_redeemed and t.expires_at > now
            ]

    def revoke_ticket(self, ticket_id: str) -> bool:
        """Revoke a ticket manually."""
        with self._ticket_lock:
            self._load_persisted_tickets()
            ticket = self._tickets.get(ticket_id)
            if ticket and not ticket.is_redeemed:
                ticket.is_redeemed = True
                self._persist_tickets()
                return True
            return False

    def sign_persisted_task(
        self,
        task_id: str,
        capability: str,
        parameters: dict[str, Any] | None = None,
        workspace_root: str | None = None,
    ) -> str:
        """
        Cryptographically bind and sign a persisted task definition with its capability name,
        canonical parameters, and target workspace root to prevent stored parameter tampering.
        """
        params_str = json.dumps(parameters or {}, sort_keys=True, default=str)
        ws_str = str(workspace_root or "").strip()
        payload = f"task:{task_id.strip()}:{capability.lower().strip()}:{ws_str}:{params_str}".encode("utf-8")
        return hmac.new(self._secret_key, payload, hashlib.sha256).hexdigest()

    def verify_persisted_task(
        self,
        task_id: str,
        capability: str,
        parameters: dict[str, Any] | None,
        signature: str,
        workspace_root: str | None = None,
    ) -> tuple[bool, str]:
        """
        Verify the cryptographic signature of a persisted task definition.
        Detects any tampering of task_id, capability, workspace_root, or parameters.
        """
        if not signature:
            return False, "Missing cryptographic signature for persisted task."
        expected_sig = self.sign_persisted_task(
            task_id=task_id,
            capability=capability,
            parameters=parameters,
            workspace_root=workspace_root,
        )
        if not hmac.compare_digest(expected_sig, signature):
            return False, "Cryptographic signature mismatch: task definition or parameters have been tampered with."
        return True, "Persisted task verified successfully."

    def sign_trigger(
        self,
        trigger_id: str,
        action_goal: str,
        execution_map: dict[str, Any],
        allowed_capabilities: list[str] | None = None,
    ) -> str:
        """
        Cryptographically sign an autonomous or recurring trigger definition with its allowed capability whitelist.
        """
        exec_str = json.dumps(execution_map or {}, sort_keys=True, default=str)
        caps_str = json.dumps(sorted(allowed_capabilities or []), default=str)
        payload = f"trigger:{trigger_id.strip()}:{action_goal.strip()}:{caps_str}:{exec_str}".encode("utf-8")
        return hmac.new(self._secret_key, payload, hashlib.sha256).hexdigest()

    def verify_trigger_signature(
        self,
        trigger_id: str,
        action_goal: str,
        execution_map: dict[str, Any],
        signature: str,
        allowed_capabilities: list[str] | None = None,
    ) -> tuple[bool, str]:
        """
        Verify that an autonomous or recurring trigger definition has not been tampered with.
        """
        if not signature:
            return False, "Missing trigger authorization signature."
        expected_sig = self.sign_trigger(
            trigger_id=trigger_id,
            action_goal=action_goal,
            execution_map=execution_map,
            allowed_capabilities=allowed_capabilities,
        )
        if not hmac.compare_digest(expected_sig, signature):
            return False, "Trigger definition, allowed capabilities, or execution map tampered with (signature mismatch)."
        return True, "Trigger signature verified successfully."
