"""
Credential Scanner for Cybersecurity Expert (M25 Phase 4)
Location: src/experts/security/credential_scanner.py

Scans source code, configurations, and text for exposed secrets and high-entropy credentials.
Masks secret values in output findings to prevent leakage.
Pure in-memory analysis, zero file mutation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Known credential regex signatures
SECRET_SIGNATURES: list[tuple[str, str, str]] = [
    ("Private Key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "HIGH"),
    ("AWS Access Key", r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}", "CRITICAL"),
    ("GitHub Token", r"gh[pousr]_[A-Za-z0-9_]{36,255}", "CRITICAL"),
    ("OpenAI / AI Key", r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", "HIGH"),
    ("Groq Key", r"gsk_[A-Za-z0-9_-]{20,}", "HIGH"),
    ("JWT Bearer Token", r"eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*", "MEDIUM"),
    ("Generic Password/Secret", r"(?:password|secret|passwd|api_key|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]", "HIGH"),
]


class CredentialScanner:
    """
    Scans content for exposed secrets with automated redaction and risk scoring.
    """

    def scan_content(self, text: str, source_label: str = "") -> dict[str, Any]:
        """
        Scans text content for exposed credentials and secrets.

        Returns:
            Dictionary containing:
                - exposed_count: int
                - findings: list[dict] (each containing type, masked_preview, severity, line)
                - max_severity: str ('NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
        """
        findings: list[dict[str, Any]] = []
        lines = text.splitlines()

        for line_no, line in enumerate(lines, 1):
            for secret_type, pattern, severity in SECRET_SIGNATURES:
                for match in re.finditer(pattern, line, re.IGNORECASE):
                    matched_val = match.group(0)
                    # Mask secret for audit output
                    if len(matched_val) > 8:
                        masked = matched_val[:4] + "*" * (len(matched_val) - 8) + matched_val[-4:]
                    else:
                        masked = "****"

                    findings.append({
                        "secret_type": secret_type,
                        "severity": severity,
                        "source": source_label,
                        "line": line_no,
                        "masked_preview": masked,
                    })

        severity_ranks = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        max_sev = "NONE"
        for f in findings:
            if severity_ranks.get(f["severity"], 0) > severity_ranks.get(max_sev, 0):
                max_sev = f["severity"]

        return {
            "exposed_count": len(findings),
            "findings": findings,
            "max_severity": max_sev,
        }
