"""
Attack Surface Analyzer for Cybersecurity Expert (M25 Phase 4)
Location: src/experts/security/attack_surface_analyzer.py

Analyzes open listening network ports, dangerous unencrypted services, and elevated process exposure.
Pure in-memory analysis, zero OS mutation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# High-risk / unencrypted / legacy ports
DANGEROUS_PORTS: dict[int, tuple[str, str]] = {
    21: ("FTP", "Unencrypted plaintext credentials and file transfer."),
    23: ("Telnet", "Unencrypted plaintext remote shell session."),
    69: ("TFTP", "Unauthenticated trivial file transfer."),
    445: ("SMB", "Direct SMB exposure over public interfaces is vulnerable to lateral movement."),
    3389: ("RDP", "Remote Desktop exposed without network level authentication or VPN."),
    5900: ("VNC", "Unencrypted / weakly authenticated remote frame buffer."),
}


class AttackSurfaceAnalyzer:
    """
    Evaluates listening ports and exposed services to identify attack vectors.
    """

    def analyze_listening_ports(self, open_ports: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyzes listening network sockets.

        Returns:
            Dictionary containing:
                - total_listening: int
                - public_facing_count: int
                - dangerous_findings: list[dict]
                - risk_score: float (0.0..10.0)
        """
        dangerous_findings: list[dict[str, Any]] = []
        public_count = 0

        for p in open_ports:
            port_num = int(p.get("port", 0))
            bind_addr = p.get("bind_address", "127.0.0.1")
            is_public = bind_addr in ("0.0.0.0", "::", "")

            if is_public:
                public_count += 1

            if port_num in DANGEROUS_PORTS and is_public:
                svc_name, desc = DANGEROUS_PORTS[port_num]
                dangerous_findings.append({
                    "port": port_num,
                    "service": svc_name,
                    "bind_address": bind_addr,
                    "description": desc,
                    "severity": "HIGH",
                })

        risk_score = min(10.0, (public_count * 0.5) + (len(dangerous_findings) * 2.5))

        return {
            "total_listening": len(open_ports),
            "public_facing_count": public_count,
            "dangerous_findings": dangerous_findings,
            "risk_score": round(risk_score, 1),
        }
