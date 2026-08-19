"""
Policy & Compliance Auditor for Cybersecurity Expert (M25 Phase 4)
Location: src/experts/security/policy_auditor.py

Audits Windows Firewall profiles, Windows Defender status, UAC elevation rules,
and Least Privilege compliance without modifying OS settings.
Pure in-memory analysis, zero OS mutation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PolicyAuditor:
    """
    Audits host security controls and compliance configurations.
    """

    def audit_security_posture(self, posture_data: dict[str, Any]) -> dict[str, Any]:
        """
        Audits system security configuration against baseline hardening standards.

        Returns:
            Dictionary containing:
                - defender_active: bool
                - firewall_profiles_active: list[str]
                - uac_enabled: bool
                - compliance_violations: list[str]
                - posture_score: float (0.0..100.0)
        """
        violations: list[str] = []
        score = 100.0

        defender_active = posture_data.get("defender_realtime_protection", True)
        if not defender_active:
            violations.append("Windows Defender Real-time Protection is DISABLED.")
            score -= 30.0

        firewall = posture_data.get("firewall_profiles", {})
        active_profiles = [p for p, enabled in firewall.items() if enabled]
        for p in ["Domain", "Private", "Public"]:
            if not firewall.get(p, True):
                violations.append(f"Windows Firewall profile '{p}' is DISABLED.")
                score -= 15.0

        uac_enabled = posture_data.get("uac_enabled", True)
        if not uac_enabled:
            violations.append("User Account Control (UAC) elevation prompting is DISABLED.")
            score -= 20.0

        is_admin = posture_data.get("running_as_admin", False)
        if is_admin:
            violations.append("Current process is running with Administrator privileges (Violates Least Privilege).")
            score -= 10.0

        return {
            "defender_active": defender_active,
            "firewall_profiles_active": active_profiles,
            "uac_enabled": uac_enabled,
            "running_as_admin": is_admin,
            "compliance_violations": violations,
            "posture_score": max(0.0, score),
        }
