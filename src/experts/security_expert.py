"""
Cybersecurity Audit Expert System
Location: src/experts/security_expert.py

Provides file permission auditing, sensitive artifact scanning, and posture evaluation.
Proposes actions to ExecutionCoordinator — NEVER executes directly.
Must strictly enforce permissions and policy governance.
"""

from __future__ import annotations

import logging
from typing import Any

from .base_expert import BaseExpertSystem
from .models import (
    DomainActionProposal,
    DomainFinding,
    DomainType,
    ExpertAnalysisResult,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class CybersecurityAuditExpert(BaseExpertSystem):
    """
    Expert System for Security Posture, Permission Auditing, and Risk Classification.
    """

    @property
    def domain(self) -> DomainType:
        return DomainType.CYBERSECURITY_AUDIT

    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        query_lower = query.lower()
        findings: list[DomainFinding] = []
        proposals: list[DomainActionProposal] = []

        target = context.get("target") or context.get("path") or "."

        if "delete" in query_lower or "remove" in query_lower or "purge" in query_lower:
            findings.append(
                DomainFinding(
                    category="destructive_action_audit",
                    title="High-Risk Action Flagged",
                    description=f"Destructive operation detected in query '{query}'. Requires explicit authorization.",
                    severity=SeverityLevel.HIGH,
                    evidence=[f"Query: '{query}'", f"Target: {target}"],
                )
            )
            proposals.append(
                DomainActionProposal(
                    engine="desktop",
                    action="file.delete",
                    parameters={
                        "path": target,
                        "user_authorized": context.get("user_authorized", False),
                    },
                    description=f"Delete target path {target} (HIGH Risk)",
                    risk_level="high",
                )
            )
        else:
            findings.append(
                DomainFinding(
                    category="security_posture",
                    title="Security Audit Baseline Scan",
                    description=f"Performing security baseline and permission audit on '{target}'.",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Target: {target}"],
                )
            )
            proposals.append(
                DomainActionProposal(
                    engine="engineering",
                    action="code.report",
                    parameters={"target_path": target},
                    description=f"Generate security & dependency posture report for {target}",
                    risk_level="low",
                )
            )

        return ExpertAnalysisResult(
            domain=self.domain,
            success=True,
            summary=f"Cybersecurity audit analysis complete for '{query}'",
            findings=findings,
            proposals=proposals,
            data={"target": target},
        )
