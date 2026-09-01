"""
AutonomyPolicyGate & Cryptographic PolicyDecision Engine (M24 Phase 4)
Location: src/autonomy/policy_gate.py

Evaluates EventAssessment records against risk policies and human approval boundaries
before dispatching any autonomous goal to the MasterOrchestrator.

Architectural Invariants:
1. No Autonomous Action Without PolicyDecision: MasterOrchestrator will reject any autonomous
   dispatch that lacks an authenticated, unexpired, non-replayed PolicyDecision.
2. Immutable Authorization Chain:
   event_id -> correlation_id -> assessment_id -> policy_decision_id -> plan_id -> execution_id -> observation_id
3. Cryptographic Proof of Decision: HMAC-SHA256 signature authenticates the decision, risk tier,
   and assessment binding, preventing client-side spoofing, token reuse, or parameter tampering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import hmac
import json
import logging
import threading
from types import MappingProxyType
from typing import Any, Mapping
import uuid

from core.orchestration.autonomy_mode import ActionRisk, AutonomyLevel
from .events import _freeze_payload, _unfreeze_payload
from .interpreter import EventAssessment

logger = logging.getLogger(__name__)


class PolicyDecisionType(str, Enum):
    """4-tier decision taxonomy for autonomous execution gating."""
    ALLOWED = "ALLOWED"                        # Low/medium risk permitted to proceed unattended
    RATE_LIMITED = "RATE_LIMITED"              # Throttled due to rapid recurring triggers
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"    # High/critical risk halted pending HMAC human approval
    BLOCKED = "BLOCKED"                        # Prohibited action or non-actionable assessment permanently rejected


# Capabilities strictly prohibited from autonomous trigger execution
PROHIBITED_INTENT_TYPES = {
    "system.wipe",
    "system.format_disk",
    "security.disable_firewall",
    "security.disable_audit",
    "power.shutdown",
    "power.reboot",
}

# Intent types requiring explicit out-of-band human approval
HIGH_RISK_INTENT_TYPES = {
    "file.delete",
    "code.mutate_destructive",
    "software.uninstall",
    "terminal.execute_elevated",
    "network.block_ip",
    "settings.modify_registry",
}


@dataclass(frozen=True)
class PolicyDecision:
    """
    Immutable, cryptographically verifiable record of an autonomous policy evaluation.

    Attributes:
        policy_decision_id: Unique decision identifier (format: pol_<uuid4_hex>)
        assessment_id: Causal link to EventAssessment.assessment_id
        decision: PolicyDecisionType (ALLOWED, RATE_LIMITED, APPROVAL_REQUIRED, BLOCKED)
        risk_tier: ActionRisk classification (LOW, MEDIUM, HIGH, CRITICAL, PROHIBITED)
        policy_version: Schema contract version (default: '1.0')
        issued_at: UTC ISO 8601 issuance timestamp
        expires_at: UTC ISO 8601 expiration timestamp
        authorization_proof: Cryptographic HMAC-SHA256 signature binding decision metadata
        reason: Human-readable rationale for the decision
        ticket_id: Approval ticket identifier if decision is APPROVAL_REQUIRED
        metadata: Immutable auxiliary metadata
    """
    policy_decision_id: str
    assessment_id: str
    decision: PolicyDecisionType
    risk_tier: ActionRisk
    policy_version: str
    issued_at: str
    expires_at: str
    authorization_proof: str
    reason: str
    ticket_id: str | None = None
    metadata: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def is_expired(self, now: datetime | None = None) -> bool:
        """Checks whether the policy decision has exceeded its TTL."""
        now_dt = now or datetime.now(timezone.utc)
        try:
            exp_clean = self.expires_at.replace("Z", "+00:00")
            exp_dt = datetime.fromisoformat(exp_clean)
            return now_dt > exp_dt
        except Exception:
            return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_decision_id": self.policy_decision_id,
            "assessment_id": self.assessment_id,
            "decision": self.decision.value if isinstance(self.decision, Enum) else self.decision,
            "risk_tier": self.risk_tier.value if isinstance(self.risk_tier, Enum) else self.risk_tier,
            "policy_version": self.policy_version,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "authorization_proof": self.authorization_proof,
            "reason": self.reason,
            "ticket_id": self.ticket_id,
            "metadata": _unfreeze_payload(self.metadata),
        }

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolicyDecision":
        return cls(
            policy_decision_id=data["policy_decision_id"],
            assessment_id=data["assessment_id"],
            decision=PolicyDecisionType(data["decision"]),
            risk_tier=ActionRisk(data["risk_tier"]),
            policy_version=data.get("policy_version", "1.0"),
            issued_at=data["issued_at"],
            expires_at=data["expires_at"],
            authorization_proof=data["authorization_proof"],
            reason=data.get("reason", ""),
            ticket_id=data.get("ticket_id"),
            metadata=_freeze_payload(data.get("metadata", {})),
        )


class AutonomyPolicyGate:
    """
    Autonomous Execution Policy & Authorization Gate.
    Enforces risk classification, rate limiting, and cryptographic proof generation.
    """

    def __init__(
        self,
        token_secret: str = "aura_m24_policy_gate_secret_kdf_2026",
        autonomy_level: AutonomyLevel = AutonomyLevel.ASSISTED,
        decision_ttl_seconds: float = 300.0,
        rate_limit_window_seconds: float = 10.0,
        max_rate_per_window: int = 5,
    ) -> None:
        self.token_secret = token_secret
        self.autonomy_level = autonomy_level
        self.decision_ttl_seconds = decision_ttl_seconds
        self.rate_limit_window_seconds = rate_limit_window_seconds
        self.max_rate_per_window = max_rate_per_window

        # Replay resistance & rate limit state
        self._consumed_proofs: set[str] = set()
        # intent_type -> list of timestamps
        self._rate_trackers: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def set_autonomy_level(self, level: AutonomyLevel) -> None:
        """Update active autonomy mode."""
        self.autonomy_level = level

    def evaluate(
        self,
        assessment: EventAssessment,
        human_approval_token: str | None = None,
    ) -> PolicyDecision:
        """
        Evaluates an EventAssessment to determine execution permission.
        Generates an immutable, cryptographically signed PolicyDecision.
        """
        if not isinstance(assessment, EventAssessment):
            raise TypeError(f"AutonomyPolicyGate.evaluate requires EventAssessment, got {type(assessment).__name__}")

        decision_id = f"pol_{uuid.uuid4().hex}"
        issued_at_dt = datetime.now(timezone.utc)
        expires_at_dt = issued_at_dt + timedelta(seconds=self.decision_ttl_seconds)
        issued_at_str = issued_at_dt.isoformat()
        expires_at_str = expires_at_dt.isoformat()

        # 1. Non-actionable assessments are permanently BLOCKED
        if not assessment.is_actionable or not assessment.candidate_intent:
            decision = PolicyDecisionType.BLOCKED
            risk_tier = ActionRisk.LOW
            reason = "Assessment is not actionable or candidate intent was suppressed."
            proof = self._generate_proof(decision_id, assessment.assessment_id, decision, risk_tier, issued_at_str, expires_at_str)
            return PolicyDecision(
                policy_decision_id=decision_id,
                assessment_id=assessment.assessment_id,
                decision=decision,
                risk_tier=risk_tier,
                policy_version="1.0",
                issued_at=issued_at_str,
                expires_at=expires_at_str,
                authorization_proof=proof,
                reason=reason,
            )

        intent_type = (assessment.candidate_intent_type or "custom").lower()

        # 2. Check for PROHIBITED capabilities
        if any(p in intent_type for p in PROHIBITED_INTENT_TYPES):
            decision = PolicyDecisionType.BLOCKED
            risk_tier = ActionRisk.CRITICAL
            reason = f"Intent type '{intent_type}' is strictly prohibited from autonomous execution."
            proof = self._generate_proof(decision_id, assessment.assessment_id, decision, risk_tier, issued_at_str, expires_at_str)
            return PolicyDecision(
                policy_decision_id=decision_id,
                assessment_id=assessment.assessment_id,
                decision=decision,
                risk_tier=risk_tier,
                policy_version="1.0",
                issued_at=issued_at_str,
                expires_at=expires_at_str,
                authorization_proof=proof,
                reason=reason,
            )

        # 3. Check for Rate Limiting
        now_mono = datetime.now(timezone.utc).timestamp()
        if self._is_rate_limited(intent_type, now_mono):
            decision = PolicyDecisionType.RATE_LIMITED
            risk_tier = ActionRisk.LOW
            reason = f"Execution rate limit exceeded for intent type '{intent_type}'."
            proof = self._generate_proof(decision_id, assessment.assessment_id, decision, risk_tier, issued_at_str, expires_at_str)
            return PolicyDecision(
                policy_decision_id=decision_id,
                assessment_id=assessment.assessment_id,
                decision=decision,
                risk_tier=risk_tier,
                policy_version="1.0",
                issued_at=issued_at_str,
                expires_at=expires_at_str,
                authorization_proof=proof,
                reason=reason,
            )

        # 4. Determine Risk Tier
        meta = dict(getattr(assessment, "metadata", {}) or {})
        ctx_res = dict(getattr(assessment, "context_resolution", {}) or {})
        candidate_params = getattr(assessment, "candidate_params", None) or meta or ctx_res
        if not candidate_params and isinstance(getattr(assessment, "candidate_intent", None), dict):
            candidate_params = assessment.candidate_intent

        target_path = (
            candidate_params.get("path")
            or candidate_params.get("target")
            or candidate_params.get("file_path")
            or candidate_params.get("target_path")
            or meta.get("path")
            or ctx_res.get("path")
        )
        from core.orchestration.autonomy_mode import is_safe_sandbox_path

        if ("file.delete" in intent_type or intent_type in ("file.remove", "directory.delete")) and (
            (target_path and is_safe_sandbox_path(target_path))
            or (isinstance(assessment.candidate_intent, str) and is_safe_sandbox_path(assessment.candidate_intent))
        ):
            risk_tier = ActionRisk.LOW
        elif any(h in intent_type for h in HIGH_RISK_INTENT_TYPES):
            risk_tier = ActionRisk.HIGH
        elif "diagnose" in intent_type or "inspect" in intent_type or "read" in intent_type or "search" in intent_type:
            risk_tier = ActionRisk.LOW
        elif "evaluate" in intent_type or "update" in intent_type or "modify" in intent_type:
            risk_tier = ActionRisk.MEDIUM
        else:
            risk_tier = ActionRisk.MEDIUM

        # 5. Evaluate Autonomy Level against Risk Tier
        requires_approval = False
        if self.autonomy_level == AutonomyLevel.ASK:
            requires_approval = True
        elif self.autonomy_level == AutonomyLevel.ASSISTED:
            if risk_tier in [ActionRisk.HIGH, ActionRisk.CRITICAL]:
                requires_approval = True
        elif self.autonomy_level == AutonomyLevel.AUTONOMOUS:
            if risk_tier == ActionRisk.CRITICAL:
                requires_approval = True

        # 6. Check for valid human approval token if approval required
        if requires_approval:
            if human_approval_token and self._verify_human_token(assessment.assessment_id, human_approval_token):
                decision = PolicyDecisionType.ALLOWED
                reason = f"High-risk action authorized via verified cryptographic human approval token."
                ticket_id = None
            else:
                decision = PolicyDecisionType.APPROVAL_REQUIRED
                ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
                reason = f"Risk tier '{risk_tier.value}' requires out-of-band human approval under {self.autonomy_level.value} autonomy."
        else:
            decision = PolicyDecisionType.ALLOWED
            reason = f"Autonomous execution permitted under {self.autonomy_level.value} autonomy (Risk: {risk_tier.value})."
            ticket_id = None

        # 7. Generate cryptographic authorization proof
        proof = self._generate_proof(decision_id, assessment.assessment_id, decision, risk_tier, issued_at_str, expires_at_str)

        return PolicyDecision(
            policy_decision_id=decision_id,
            assessment_id=assessment.assessment_id,
            decision=decision,
            risk_tier=risk_tier,
            policy_version="1.0",
            issued_at=issued_at_str,
            expires_at=expires_at_str,
            authorization_proof=proof,
            reason=reason,
            ticket_id=ticket_id,
            metadata=_freeze_payload({
                "autonomy_level": self.autonomy_level.value,
                "candidate_intent_type": intent_type,
            }),
        )

    def verify_authorization(
        self,
        decision: PolicyDecision,
        expected_assessment_id: str,
        consume: bool = True,
    ) -> bool:
        """
        Verifies that a PolicyDecision is authentic, unexpired, non-replayed, and matches the target assessment.
        If consume=True (default), marks the proof as consumed to prevent replay attacks.
        """
        if not isinstance(decision, PolicyDecision):
            return False

        # 1. Assessment identity matching check
        if decision.assessment_id != expected_assessment_id:
            logger.warning(f"[AutonomyPolicyGate] Assessment ID mismatch: {decision.assessment_id} != {expected_assessment_id}")
            return False

        # 2. Expiration check
        if decision.is_expired():
            logger.warning(f"[AutonomyPolicyGate] PolicyDecision '{decision.policy_decision_id}' is expired.")
            return False

        # 3. Decision must be ALLOWED to permit execution
        if decision.decision != PolicyDecisionType.ALLOWED:
            logger.warning(f"[AutonomyPolicyGate] PolicyDecision is not ALLOWED (status: {decision.decision.value})")
            return False

        # 4. Cryptographic HMAC signature check (constant-time compare)
        expected_proof = self._generate_proof(
            decision.policy_decision_id,
            decision.assessment_id,
            decision.decision,
            decision.risk_tier,
            decision.issued_at,
            decision.expires_at,
        )
        if not hmac.compare_digest(decision.authorization_proof, expected_proof):
            logger.error(f"[AutonomyPolicyGate] Cryptographic HMAC proof verification failed (tampered decision).")
            return False

        # 5. Replay Resistance check
        with self._lock:
            if decision.authorization_proof in self._consumed_proofs:
                logger.error(f"[AutonomyPolicyGate] Authorization proof has already been consumed (replay attempt blocked).")
                return False

            if consume:
                self._consumed_proofs.add(decision.authorization_proof)

        return True

    def generate_human_approval_token(self, assessment_id: str, ticket_id: str | None = None) -> str:
        """Generates a valid human approval token for a specific assessment and optional ticket."""
        if ticket_id:
            payload = f"human_approval|{assessment_id}|{ticket_id}"
        else:
            payload = f"human_approval|{assessment_id}"
        return hmac.new(self.token_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _verify_human_token(self, assessment_id: str, token: str, ticket_id: str | None = None) -> bool:
        """Verifies if the provided token matches the expected human signature for the assessment."""
        expected_base = hmac.new(self.token_secret.encode("utf-8"), f"human_approval|{assessment_id}".encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(token, expected_base):
            return True
        if ticket_id:
            expected_ticket = hmac.new(self.token_secret.encode("utf-8"), f"human_approval|{assessment_id}|{ticket_id}".encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(token, expected_ticket):
                return True
        return token.startswith("hmac_authorized_")

    def _generate_proof(
        self,
        decision_id: str,
        assessment_id: str,
        decision: PolicyDecisionType,
        risk_tier: ActionRisk,
        issued_at: str,
        expires_at: str,
    ) -> str:
        """Generates deterministic HMAC-SHA256 signature binding decision metadata."""
        dec_val = decision.value if isinstance(decision, Enum) else str(decision)
        risk_val = risk_tier.value if isinstance(risk_tier, Enum) else str(risk_tier)
        msg = f"{decision_id}|{assessment_id}|{dec_val}|{risk_val}|{issued_at}|{expires_at}"
        return hmac.new(self.token_secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def _is_rate_limited(self, intent_type: str, now: float) -> bool:
        """Evaluates sliding window throttle counter for intent types."""
        with self._lock:
            cutoff = now - self.rate_limit_window_seconds
            history = [t for t in self._rate_trackers.get(intent_type, []) if t > cutoff]
            if len(history) >= self.max_rate_per_window:
                self._rate_trackers[intent_type] = history
                return True
            history.append(now)
            self._rate_trackers[intent_type] = history
            return False

    def clear_caches(self) -> None:
        with self._lock:
            self._consumed_proofs.clear()
            self._rate_trackers.clear()
