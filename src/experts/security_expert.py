"""
Cybersecurity Audit Expert System
Location: src/experts/security_expert.py

Provides local defensive filesystem permission auditing, sensitive artifact scanning,
process privilege inspection, listening port auditing, and security posture scoring.

INVARIANT: Proposes remediation actions to ExecutionCoordinator — NEVER performs arbitrary offensive actions or direct file mutations.
RULE: If inspection is inaccessible, returns honest INSPECTION_UNAVAILABLE status — NEVER fabricates security findings.
"""

from __future__ import annotations

import ctypes
import logging
import os
import socket
import stat
from pathlib import Path
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
    Expert System for Security Posture Evaluation, Permission Auditing, Sensitive File Detection, and Risk Remediation.
    """

    @property
    def domain(self) -> DomainType:
        return DomainType.CYBERSECURITY_AUDIT

    def _is_admin(self) -> bool:
        """Check if current process has Administrative / Root privileges."""
        try:
            if hasattr(ctypes, "windll"):
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            return os.getuid() == 0
        except Exception:
            return False

    def _audit_permissions(self, target_path: Path) -> list[DomainFinding]:
        """Audit file/directory permissions on target path."""
        findings: list[DomainFinding] = []

        if not target_path.exists():
            findings.append(
                DomainFinding(
                    category="filesystem_permissions",
                    title="Path Inaccessible: Permission Audit Skipped",
                    description=f"Target path '{target_path}' does not exist or is inaccessible. Status: INSPECTION_UNAVAILABLE.",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Path: {target_path}", "Status: INSPECTION_UNAVAILABLE"],
                    location=str(target_path),
                    confidence=0.50,
                )
            )
            return findings

        try:
            st = target_path.stat()
            mode = st.st_mode
            readable = os.access(target_path, os.R_OK)
            writable = os.access(target_path, os.W_OK)
            executable = os.access(target_path, os.X_OK)

            is_world_writable = bool(mode & stat.S_IWOTH)

            if is_world_writable:
                findings.append(
                    DomainFinding(
                        category="filesystem_permissions",
                        title="World-Writable Permission Security Vulnerability",
                        description=f"Target '{target_path.name}' is world-writable (mode octal: {oct(mode)}).",
                        severity=SeverityLevel.HIGH,
                        evidence=[f"Path: {target_path}", f"Mode: {oct(mode)}", "World-Writable: True"],
                        location=str(target_path),
                        confidence=0.95,
                    )
                )
            else:
                findings.append(
                    DomainFinding(
                        category="filesystem_permissions",
                        title="Filesystem Permission Baseline Check",
                        description=f"Permissions verified for '{target_path.name}'. Mode: {oct(mode)}, R={readable}, W={writable}, X={executable}.",
                        severity=SeverityLevel.INFO,
                        evidence=[f"Path: {target_path}", f"Mode: {oct(mode)}", f"Readable={readable}, Writable={writable}"],
                        location=str(target_path),
                        confidence=0.98,
                    )
                )

        except PermissionError as p_err:
            findings.append(
                DomainFinding(
                    category="filesystem_permissions",
                    title="Permission Denied During Access Inspection",
                    description=f"Access denied inspecting '{target_path}'. Status: INSPECTION_UNAVAILABLE due to OS permission restriction.",
                    severity=SeverityLevel.MEDIUM,
                    evidence=[f"Path: {target_path}", f"Error: {p_err}", "Status: INSPECTION_UNAVAILABLE"],
                    location=str(target_path),
                    confidence=0.50,
                )
            )
        except Exception as exc:
            findings.append(
                DomainFinding(
                    category="filesystem_permissions",
                    title="Inaccessible Path Inspection Error",
                    description=f"Unable to stat path '{target_path}'. Status: INSPECTION_UNAVAILABLE ({exc}).",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Path: {target_path}", f"Error: {exc}"],
                    location=str(target_path),
                    confidence=0.50,
                )
            )

        return findings

    def _scan_sensitive_files(self, target_path: Path) -> list[DomainFinding]:
        """Scan workspace for potential sensitive files (.env, keys, unencrypted credentials)."""
        findings: list[DomainFinding] = []
        sensitive_patterns = (".env", ".pem", ".key", "id_rsa", "secrets.json", "credentials.xml")

        scan_dir = target_path if target_path.is_dir() else target_path.parent
        scanned_count = 0
        detected_secrets: list[Path] = []

        try:
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", ".venv", "__pycache__", "build", "dist")]
                for f in files:
                    scanned_count += 1
                    fl = f.lower()
                    if any(p in fl for p in sensitive_patterns):
                        fp = Path(root) / f
                        detected_secrets.append(fp)
                        findings.append(
                            DomainFinding(
                                category="sensitive_file_detection",
                                title=f"Sensitive Artifact Detected: {f}",
                                description=f"Potential unencrypted secret or key artifact found at '{fp.name}'.",
                                severity=SeverityLevel.MEDIUM if f.startswith(".env") else SeverityLevel.HIGH,
                                evidence=[f"File Path: {fp}", f"Pattern Matched: {f}"],
                                location=str(fp),
                                confidence=0.92,
                            )
                        )
                if scanned_count > 200:  # Bound scanning scope
                    break

            if not detected_secrets:
                findings.append(
                    DomainFinding(
                        category="sensitive_file_detection",
                        title="Sensitive Artifact Scan Passed",
                        description=f"Scanned {scanned_count} workspace files. No exposed key or secret artifacts detected.",
                        severity=SeverityLevel.INFO,
                        evidence=[f"Scanned Files Count: {scanned_count}"],
                        location=str(scan_dir),
                        confidence=0.95,
                    )
                )

        except Exception as exc:
            findings.append(
                DomainFinding(
                    category="sensitive_file_detection",
                    title="Sensitive File Scan Interrupted",
                    description=f"File scan interrupted: {exc}. Status: INSPECTION_UNAVAILABLE.",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Error: {exc}"],
                    location=str(scan_dir),
                    confidence=0.50,
                )
            )

        return findings

    def _audit_process_privileges(self) -> DomainFinding:
        """Inspect current process privileges and admin rights."""
        is_admin = self._is_admin()
        user_name = os.getlogin() if hasattr(os, "getlogin") else os.environ.get("USERNAME", "unknown")
        severity = SeverityLevel.LOW if is_admin else SeverityLevel.INFO

        return DomainFinding(
            category="process_privileges",
            title="Process Elevation & Privilege Status",
            description=f"Aura runtime running under user '{user_name}'. Elevated Admin Privileges: {is_admin}.",
            severity=severity,
            evidence=[
                f"User Account: {user_name}",
                f"Is Admin / Root: {is_admin}",
                f"PID: {os.getpid()}",
            ],
            location=f"PID:{os.getpid()}",
            confidence=0.99,
        )

    def _audit_open_ports(self) -> list[DomainFinding]:
        """Audit bound local listening sockets for common exposure ports."""
        findings: list[DomainFinding] = []
        standard_ports = [80, 443, 8080, 22, 3389, 135, 445]
        open_ports: list[int] = []

        for port in standard_ports:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.05):
                    open_ports.append(port)
            except Exception:
                pass

        if open_ports:
            findings.append(
                DomainFinding(
                    category="open_port_audit",
                    title="Local Bound Ports Detected",
                    description=f"Active bound listening sockets detected on ports: {open_ports}.",
                    severity=SeverityLevel.LOW if all(p in (80, 443, 8080) for p in open_ports) else SeverityLevel.MEDIUM,
                    evidence=[f"Open Ports List: {open_ports}", "Target Host: 127.0.0.1"],
                    location=f"127.0.0.1:{open_ports}",
                    confidence=0.95,
                )
            )
        else:
            findings.append(
                DomainFinding(
                    category="open_port_audit",
                    title="Standard Listening Ports Closed",
                    description="No unencrypted high-risk listening ports detected on local loopback.",
                    severity=SeverityLevel.INFO,
                    evidence=["Tested Ports: [80, 443, 8080, 22, 3389, 135, 445]", "Status: All Closed"],
                    location="127.0.0.1",
                    confidence=0.95,
                )
            )

        return findings

    def _calculate_posture_score(self, findings: list[DomainFinding]) -> float:
        """Calculate security posture score out of 100.0 based on findings severity."""
        score = 100.0
        weights = {
            SeverityLevel.CRITICAL: 25.0,
            SeverityLevel.HIGH: 15.0,
            SeverityLevel.MEDIUM: 10.0,
            SeverityLevel.LOW: 3.0,
            SeverityLevel.INFO: 0.0,
        }
        for f in findings:
            score -= weights.get(f.severity, 0.0)

        return max(0.0, min(100.0, score))

    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        query_lower = query.lower()
        findings: list[DomainFinding] = []
        proposals: list[DomainActionProposal] = []

        target_str = context.get("target") or context.get("target_path") or context.get("path") or "."
        target_path = Path(target_str).resolve()

        # 1. Real Filesystem Permission Audit (G1)
        findings.extend(self._audit_permissions(target_path))

        # 2. Sensitive File Detection (G2)
        findings.extend(self._scan_sensitive_files(target_path))

        # 3. Process & Privilege Inspection (G3)
        findings.append(self._audit_process_privileges())

        # 4. Listening / Open Port Audit (G4)
        findings.extend(self._audit_open_ports())

        # 5. Security Posture Scoring (G5)
        posture_score = self._calculate_posture_score(findings)
        findings.append(
            DomainFinding(
                category="security_posture",
                title="Overall Defensive Security Posture Score",
                description=f"Calculated defensive posture score: {posture_score:.1f}% based on {len(findings) - 1} audit findings.",
                severity=SeverityLevel.INFO if posture_score >= 80.0 else SeverityLevel.MEDIUM,
                evidence=[f"Posture Score: {posture_score:.1f}%", f"Findings Count: {len(findings) - 1}"],
                location=str(target_path),
                confidence=0.96,
            )
        )

        # 6. Remediation Proposals Only (G8, G9)
        if "delete" in query_lower or "purge" in query_lower or "remove" in query_lower:
            proposals.append(
                DomainActionProposal(
                    engine="desktop",
                    action="file.delete",
                    parameters={
                        "path": str(target_path),
                        "user_authorized": context.get("user_authorized", False),
                    },
                    description=f"Purge target file {target_path.name} (HIGH Risk)",
                    risk_level="high",
                )
            )

        # Always propose baseline report generation
        proposals.append(
            DomainActionProposal(
                engine="engineering",
                action="code.report",
                parameters={"target_path": str(target_path)},
                description=f"Generate security posture report for {target_path.name}",
                risk_level="low",
            )
        )

        summary = (
            f"Cybersecurity audit complete for '{target_path.name}'. "
            f"Posture Score: {posture_score:.1f}%, Findings: {len(findings)}, Proposals: {len(proposals)}."
        )

        return ExpertAnalysisResult(
            domain=self.domain,
            success=True,
            summary=summary,
            findings=findings,
            proposals=proposals,
            data={
                "target_path": str(target_path),
                "posture_score": posture_score,
                "is_admin": self._is_admin(),
                "findings_count": len(findings),
            },
        )
