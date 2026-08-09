"""
Network Diagnostics Expert System
Location: src/experts/network_expert.py

Provides network reachability analysis, DNS resolution, port diagnostics, and HTTP checks.
Proposes actions to ExecutionCoordinator — NEVER executes directly.
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


class NetworkDiagnosticsExpert(BaseExpertSystem):
    """
    Expert System for Network Diagnostics, Connectivity, and Protocol Auditing.
    """

    @property
    def domain(self) -> DomainType:
        return DomainType.NETWORK_DIAGNOSTICS

    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        query_lower = query.lower()
        findings: list[DomainFinding] = []
        proposals: list[DomainActionProposal] = []

        target_host = context.get("host") or context.get("target_url") or "data:text/html,<h1>NetCheck</h1>"

        if "port" in query_lower or "scan" in query_lower:
            findings.append(
                DomainFinding(
                    category="network_ports",
                    title="Port Diagnostic Proposal",
                    description=f"Diagnostic inspection for open ports on target host '{target_host}'.",
                    severity=SeverityLevel.MEDIUM,
                    evidence=[f"Host: {target_host}", f"Query: {query}"],
                )
            )
            proposals.append(
                DomainActionProposal(
                    engine="desktop",
                    action="network.scan_ports",
                    parameters={"host": target_host, "ports": [80, 443, 8080]},
                    description=f"Scan standard ports on {target_host}",
                    risk_level="low",
                )
            )
        else:
            findings.append(
                DomainFinding(
                    category="connectivity",
                    title="Host Reachability Proposal",
                    description=f"Evaluating ping reachability and ICMP latency to '{target_host}'.",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Host: {target_host}"],
                )
            )
            url = target_host if (target_host.startswith("http") or target_host.startswith("data:")) else f"https://{target_host}"
            proposals.append(
                DomainActionProposal(
                    engine="browser",
                    action="browser.navigate",
                    parameters={"url": url},
                    description=f"Verify HTTP connectivity to {target_host}",
                    risk_level="low",
                )
            )

        return ExpertAnalysisResult(
            domain=self.domain,
            success=True,
            summary=f"Network diagnostics analysis complete for '{query}'",
            findings=findings,
            proposals=proposals,
            data={"target_host": target_host},
        )
