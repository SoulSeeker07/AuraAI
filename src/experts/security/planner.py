"""
Cybersecurity & Audit Expert Planner (M25 Phase 4)
Location: src/experts/security/planner.py

Specialized domain planner coordinating credential exposure scanning, attack surface auditing,
vulnerability/CVE correlation, and host compliance assessment.

Architectural Invariants:
1. Pure Reasoning: Generates DomainAssessment and PlanDAG data structures.
   Zero direct capability execution, zero system security modification during planning.
2. Strict Separation: Read-only diagnostic observation (Credential Scan, Port Audit, CVE Correlation)
   is strictly separated from active remediation (which requires explicit ActionRisk.HIGH confirmation).
3. Causal Continuity: Preserves event_id, correlation_id, and assessment_id.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import PlanValidationResult
from core.orchestration.autonomy_mode import ActionRisk
from ..base_expert import DomainExpertPlanner
from ..models import DomainAssessment, PlanDAG, PlanNode
from .attack_surface_analyzer import AttackSurfaceAnalyzer
from .credential_scanner import CredentialScanner
from .policy_auditor import PolicyAuditor
from .vulnerability_correlator import VulnerabilityCorrelator

logger = logging.getLogger(__name__)


class CybersecurityExpertPlanner(DomainExpertPlanner):
    """
    Professional domain planner for cybersecurity auditing, vulnerability management, and secret detection.
    """

    def __init__(
        self,
        credential_scanner: CredentialScanner | None = None,
        attack_surface_analyzer: AttackSurfaceAnalyzer | None = None,
        vulnerability_correlator: VulnerabilityCorrelator | None = None,
        policy_auditor: PolicyAuditor | None = None,
    ) -> None:
        self.credential_scanner = credential_scanner or CredentialScanner()
        self.attack_surface_analyzer = attack_surface_analyzer or AttackSurfaceAnalyzer()
        self.vulnerability_correlator = vulnerability_correlator or VulnerabilityCorrelator()
        self.policy_auditor = policy_auditor or PolicyAuditor()

    @property
    def domain(self) -> str:
        return "cybersecurity"

    @property
    def description(self) -> str:
        return "Specialized expert for credential exposure scanning, attack surface analysis, CVE correlation, and security compliance auditing."

    @property
    def supported_intents(self) -> list[str]:
        return [
            "security.audit",
            "security.credential_scan",
            "security.cve_check",
            "security.firewall_audit",
            "security.attack_surface",
            "security.remediate",
        ]

    def can_handle(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, float, str]:
        """
        Evaluates goal text against cybersecurity semantic patterns.
        """
        g = goal_text.lower().strip()
        ctx = context or {}

        # Check explicit intent
        intent = ctx.get("intent", "")
        if intent in self.supported_intents:
            return True, 0.98, f"Direct match with supported intent '{intent}'."

        # High-confidence indicators
        high_indicators = [
            r"\bcves?\b", r"\bvulnerabilit(?:y|ies)\b", r"\bcredentials?\b", r"\bleaked\b",
            r"\bsecrets?\b", r"\bapi keys?\b", r"\bfirewall\b",
            r"\battack surface\b", r"\blistening ports?\b", r"\bopen ports?\b", r"\bsecurity audit\b",
            r"\bleast privilege\b", r"\bwindows defender\b", r"\buac\b", r"\btokens?\b",
            r"\binsecure dependenc(?:y|ies)\b", r"\bpenetration test(?:ing)?\b", r"\bhardening\b"
        ]
        matched_high = [ind for ind in high_indicators if re.search(ind, g)]
        if matched_high:
            clean_names = [ind.replace(r"\b", "").replace("?", "") for ind in matched_high]
            confidence = min(0.96, 0.82 + (0.04 * len(matched_high)))
            return True, confidence, f"Matched cybersecurity signals: {', '.join(clean_names)}."

        # Medium-confidence indicators (word-boundary matches)
        med_indicators = [
            r"\bsecurity\b", r"\bauthentication\b", r"\bauthorization\b",
            r"\bpermission\b", r"\bcompliance\b", r"\bunsafe\b", r"\brisk\b"
        ]
        matched_med = [ind for ind in med_indicators if re.search(ind, g)]
        if matched_med:
            clean_names = [ind.replace(r"\b", "") for ind in matched_med]
            return True, 0.65, f"Matched general security terms: {', '.join(clean_names)}."

        return False, 0.10, "Goal does not require specialized cybersecurity expertise."

    async def assess(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> DomainAssessment:
        """
        Conducts deep cybersecurity evaluation and synthesizes findings and strategy.
        """
        ctx = context or {}
        causal = ctx.get("causal_context", {})
        findings: list[str] = []
        assumptions: list[str] = []
        required_caps: list[str] = []

        g = goal_text.lower()

        if any(w in g for w in ["credential", "secret", "api key", "token", "leak"]):
            findings.append("Focus Area: Credential & Secret Exposure Audit.")
            required_caps.extend(["security.credential_scan", "workspace.walk"])
        elif any(w in g for w in ["port", "attack surface", "listening", "service"]):
            findings.append("Focus Area: Host Attack Surface & Exposed Services Audit.")
            required_caps.extend(["security.attack_surface_audit", "network.interface_list"])
        elif any(w in g for w in ["cve", "vulnerability", "dependency", "package"]):
            findings.append("Focus Area: Dependency & CVE Vulnerability Correlation.")
            required_caps.extend(["security.cve_check", "code.analyze"])
        elif any(w in g for w in ["firewall", "defender", "uac", "policy", "compliance"]):
            findings.append("Focus Area: Host Hardening & Policy Compliance.")
            required_caps.extend(["security.firewall_audit", "security.attack_surface_audit"])
        else:
            findings.append("Focus Area: Comprehensive Security Posture Audit.")
            required_caps.extend([
                "security.credential_scan",
                "security.attack_surface_audit",
                "security.cve_check",
                "security.firewall_audit",
            ])

        assumptions.extend([
            "Security assessment is strictly observational and non-destructive.",
            "Secrets discovered during audit must be masked to prevent exposure in logs.",
            "Active remediation requires separate human authorization.",
        ])

        strategy = (
            "Multi-Pillar Security Audit: "
            "1. Secrets & Credentials -> 2. Attack Surface (Ports/Services) -> "
            "3. CVE Correlation -> 4. Policy/Compliance (Firewall & Defender). Zero autonomous remediation."
        )

        return DomainAssessment.create(
            domain=self.domain,
            confidence=0.95,
            findings=findings,
            assumptions=assumptions,
            required_capabilities=list(set(required_caps)),
            recommended_strategy=strategy,
            causal_context=causal,
            metadata={"goal": goal_text},
        )

    async def generate_plan(
        self,
        goal_text: str,
        assessment: DomainAssessment,
        context: dict[str, Any] | None = None,
    ) -> PlanDAG:
        """
        Synthesizes a dependency-ordered PlanDAG for security audits.
        """
        plan = PlanDAG.create(
            domain=self.domain,
            goal=goal_text,
            assessment_id=assessment.assessment_id,
            causal_context=dict(assessment.causal_context),
        )

        # Stage 1: Parallel Secrets & Attack Surface Discovery (Read-only)
        plan.add_node(
            PlanNode(
                node_id="sec_cred_scan_01",
                capability="security.credential_scan",
                description="Scan workspace files and configuration files for exposed secrets and tokens.",
                risk_level=ActionRisk.LOW,
            )
        )
        plan.add_node(
            PlanNode(
                node_id="sec_surface_audit_02",
                capability="security.attack_surface_audit",
                description="Audit open listening ports, exposed services, and bound network interfaces.",
                risk_level=ActionRisk.LOW,
            )
        )

        # Stage 2: Parallel CVE & Policy Compliance Verification (Read-only)
        plan.add_node(
            PlanNode(
                node_id="sec_cve_check_03",
                capability="security.cve_check",
                dependencies=["sec_cred_scan_01"],
                description="Correlate installed packages and software against known CVE database.",
                risk_level=ActionRisk.LOW,
            )
        )
        plan.add_node(
            PlanNode(
                node_id="sec_firewall_audit_04",
                capability="security.firewall_audit",
                dependencies=["sec_surface_audit_02"],
                description="Audit Windows Firewall profiles, rule consistency, and Windows Defender protection status.",
                risk_level=ActionRisk.LOW,
            )
        )

        plan.compute_execution_stages()
        return plan
