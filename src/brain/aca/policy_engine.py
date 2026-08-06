"""
Policy Engine — Governance Layer
================================

Safety is too narrow inside the DMM. Aura needs a separate governance layer.

    DecisionContext
        ↓
    Policy Engine
        ↓
    Approved?
        ↓
    Planner

Covers: Security, Permissions, User policies, Admin mode, Plugin permissions, Corporate rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..schemas.decision_context import DecisionContext

logger = logging.getLogger(__name__)


@dataclass
class PolicyDecision:
    """The result of policy evaluation."""

    approved: bool
    policy: str = ""
    reason: str = ""
    risk_level: str = "low"
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "policy": self.policy,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
        }


class PolicyEngine:
    """
    Evaluates whether a DecisionContext is approved for execution.

    This keeps governance independent of reasoning.
    """

    def __init__(self, policies: list[dict[str, Any]] | None = None):
        self.policies = policies or []

    def evaluate(self, decision_context: DecisionContext) -> PolicyDecision:
        """
        Evaluate a DecisionContext against all policies.

        Args:
            decision_context: The fused decision context.

        Returns:
            PolicyDecision with approval status.
        """
        # ── 1. Safety check ─────────────────────────────────────────────────
        if not decision_context.safety.safe:
            return PolicyDecision(
                approved=False,
                policy="safety",
                reason=f"Safety assessment failed: {decision_context.safety.reasons}",
                risk_level=decision_context.safety.risk_level,
            )

        # ── 2. Confidence check ─────────────────────────────────────────────
        if decision_context.confidence.overall < 0.5:
            return PolicyDecision(
                approved=False,
                policy="confidence",
                reason=f"Confidence too low: {decision_context.confidence.overall:.2f}",
                risk_level="medium",
            )

        # ── 3. Custom policies ──────────────────────────────────────────────
        for policy in self.policies:
            policy_name = policy.get("name", "custom")
            condition = policy.get("condition", "")
            action = policy.get("action", "deny")

            if condition and condition in decision_context.raw_input.lower():
                if action == "deny":
                    return PolicyDecision(
                        approved=False,
                        policy=policy_name,
                        reason=policy.get("reason", f"Blocked by policy: {policy_name}"),
                        risk_level=policy.get("risk_level", "high"),
                    )
                elif action == "confirm":
                    return PolicyDecision(
                        approved=True,
                        policy=policy_name,
                        reason=f"Requires confirmation: {policy_name}",
                        risk_level=policy.get("risk_level", "medium"),
                        requires_confirmation=True,
                    )

        # ── 4. High-risk operations ─────────────────────────────────────────
        high_risk_actions = ["delete", "format", "shutdown", "taskkill", "rm -rf"]
        for action in high_risk_actions:
            if action in decision_context.raw_input.lower():
                return PolicyDecision(
                    approved=True,
                    policy="high_risk",
                    reason=f"High-risk operation detected: {action}",
                    risk_level="high",
                    requires_confirmation=True,
                )

        # ── 5. Approved ─────────────────────────────────────────────────────
        return PolicyDecision(
            approved=True,
            policy="default",
            reason="All policies passed",
            risk_level="low",
        )

    def add_policy(self, policy: dict[str, Any]) -> None:
        """Add a custom policy."""
        self.policies.append(policy)


__all__ = ["PolicyEngine", "PolicyDecision"]