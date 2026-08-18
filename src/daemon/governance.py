"""
Autonomy Governance & Cryptographic Policy Engine
Location: src/daemon/governance.py

Enforces risk boundaries, scoped cryptographic execution tokens, and prohibits dangerous unattended actions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.orchestration.autonomy_mode import ActionRisk
from .models import AutonomyRiskTier, JobDefinition

logger = logging.getLogger(__name__)

# Capabilities strictly prohibited from unattended daemon execution
DEFAULT_PROHIBITED_CAPABILITIES = {
    "system.format_disk",
    "system.wipe",
    "security.disable_firewall",
    "security.disable_audit",
    "security.disable_defender",
    "power.shutdown",
    "power.reboot",
    "terminal.raw_sudo",
    "terminal.dangerous_exec",
}

# High-risk capabilities requiring pre-authorized cryptographic tokens
DEFAULT_HIGH_RISK_CAPABILITIES = {
    "file.delete",
    "file.wipe",
    "terminal.execute",
    "software.uninstall",
    "network.block_ip",
    "settings.modify_registry",
}


@dataclass
class AutonomyPolicy:
    """Configurable security policy for unattended background execution."""

    max_unattended_risk: ActionRisk = ActionRisk.LOW
    allowed_domains: set[str] = field(default_factory=lambda: {"desktop", "coding", "browser", "memory", "research", "multimodal", "daemon", "scheduler"})
    prohibited_capabilities: set[str] = field(default_factory=lambda: set(DEFAULT_PROHIBITED_CAPABILITIES))
    high_risk_capabilities: set[str] = field(default_factory=lambda: set(DEFAULT_HIGH_RISK_CAPABILITIES))
    max_runtime_seconds: float = 600.0
    max_retries: int = 3
    token_secret: str = "aura_daemon_auth_secret_kdf_derived_2026"


class AutonomyGovernanceEngine:
    """Singleton governance engine enforcing authorization bounds on daemon jobs."""

    _instance: AutonomyGovernanceEngine | None = None

    def __init__(self, policy: AutonomyPolicy | None = None) -> None:
        self.policy = policy or AutonomyPolicy()

    @classmethod
    def get_instance(cls) -> AutonomyGovernanceEngine:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def compute_arguments_digest(self, arguments: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 digest of execution arguments."""
        try:
            canonical = json.dumps(arguments, sort_keys=True, default=str)
        except Exception:
            canonical = str(sorted(arguments.items()))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def create_scoped_token(
        self,
        job_id: str,
        capability: str,
        arguments_digest: str,
        validity_seconds: float = 3600.0,
    ) -> str:
        """
        Generate a parameter-bound, time-bound cryptographic HMAC token
        authorizing a high-risk background execution.
        """
        expires_at = int(time.time() + validity_seconds)
        payload = f"{job_id}:{capability}:{arguments_digest}:{expires_at}"
        sig = hmac.new(
            self.policy.token_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}:{sig}"

    def verify_scoped_token(
        self,
        token: str,
        job_id: str,
        capability: str,
        arguments_digest: str,
    ) -> tuple[bool, str]:
        """
        Verify that the token is valid, unexpired, and matches job_id, capability, and arguments.
        """
        if not token or ":" not in token:
            return False, "Malformed or missing authorization token"

        parts = token.split(":")
        if len(parts) != 5:
            return False, "Invalid token structure"

        t_job, t_cap, t_digest, t_exp_str, t_sig = parts
        try:
            expires_at = int(t_exp_str)
        except ValueError:
            return False, "Invalid token expiration timestamp"

        # Check expiration
        if time.time() > expires_at:
            return False, f"Authorization token expired at {expires_at} (current: {int(time.time())})"

        # Check parameter binding
        if t_job != job_id:
            return False, f"Token bound to job '{t_job}', does not match target job '{job_id}'"

        if t_cap != capability:
            return False, f"Token bound to capability '{t_cap}', does not match target '{capability}'"

        if t_digest != arguments_digest and t_digest != "*":
            return False, "Token argument digest mismatch (parameters were altered)"

        # Check cryptographic signature
        expected_payload = f"{t_job}:{t_cap}:{t_digest}:{expires_at}"
        expected_sig = hmac.new(
            self.policy.token_secret.encode("utf-8"),
            expected_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(t_sig, expected_sig):
            return False, "Cryptographic signature validation failed"

        return True, "Token valid and authorized"

    def classify_risk(self, capability: str, arguments: dict[str, Any] | None = None) -> AutonomyRiskTier:
        """Classify the autonomy risk tier of a capability and arguments."""
        cap_clean = capability.lower().strip()

        # 1. Check prohibited capabilities
        if cap_clean in self.policy.prohibited_capabilities:
            return AutonomyRiskTier.PROHIBITED

        # 2. Check high risk capabilities
        if cap_clean in self.policy.high_risk_capabilities:
            return AutonomyRiskTier.HIGH_RISK_GATE

        # 3. Check destructive arguments (e.g. recursive delete or rm -rf)
        args = arguments or {}
        args_str = json.dumps(args, default=str).lower()
        if any(w in args_str for w in ["drop table", "format", "rm -rf", "remove-item -recurse -force"]):
            return AutonomyRiskTier.PROHIBITED

        return AutonomyRiskTier.LOW_IMPACT

    def evaluate_execution(
        self,
        job: JobDefinition,
        capability: str,
        arguments: dict[str, Any],
        token: str | None = None,
    ) -> tuple[bool, str, AutonomyRiskTier]:
        """
        Evaluate whether an unattended background task is authorized to execute.
        """
        risk_tier = self.classify_risk(capability, arguments)

        if risk_tier == AutonomyRiskTier.PROHIBITED:
            msg = f"Capability '{capability}' is PROHIBITED from unattended daemon execution."
            logger.error(f"[AutonomyGovernance] {msg}")
            return False, msg, risk_tier

        if risk_tier == AutonomyRiskTier.HIGH_RISK_GATE:
            tok = token or job.autonomy_token
            if not tok:
                msg = f"Capability '{capability}' is HIGH_RISK and requires a pre-authorized token for unattended run."
                logger.warning(f"[AutonomyGovernance] {msg}")
                return False, msg, risk_tier

            args_digest = self.compute_arguments_digest(arguments)
            valid, reason = self.verify_scoped_token(tok, job.job_id, capability, args_digest)
            if not valid:
                msg = f"Authorization token rejected for '{capability}': {reason}"
                logger.warning(f"[AutonomyGovernance] {msg}")
                return False, msg, risk_tier

        return True, "Authorized for unattended execution", risk_tier
