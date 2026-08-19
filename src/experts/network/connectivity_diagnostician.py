"""
Connectivity Diagnostician for Network Engineering Expert (M25 Phase 3)
Location: src/experts/network/connectivity_diagnostician.py

Synthesizes Root Cause Analysis (RCA) and formulates structured diagnostic plans.
Enforces strict separation of read-only diagnostic observation from active remediation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ConnectivityDiagnostician:
    """
    Formulates structured diagnostic observation sequences and isolates candidate network failure layers.
    """

    def formulate_diagnostic_strategy(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Parses network symptoms and maps them to standard OSI diagnostic stages.

        Returns:
            Dictionary containing:
                - target_host: str | None
                - target_port: int | None
                - symptom_category: str ('PACKET_LOSS', 'DNS_FAILURE', 'LATENCY', 'SOCKET_REFUSED', 'GENERAL')
                - diagnostic_stages: list[dict]
                - remediation_candidate: str | None
                - required_capabilities: list[str]
        """
        g = goal_text.lower()
        target_host = None
        target_port = None

        # Extract host
        host_match = re.search(r'(?:host|domain|ip|to|for|at)\s+([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|(?:\d{1,3}\.){3}\d{1,3})', goal_text)
        if host_match:
            target_host = host_match.group(1)

        # Extract port
        port_match = re.search(r'port\s+(\d+)', goal_text, re.IGNORECASE)
        if port_match:
            target_port = int(port_match.group(1))

        if any(w in g for w in ["packet loss", "drop", "ping fail"]):
            symptom = "PACKET_LOSS"
            remediation = "Flush DNS cache, reset adapter link or verify gateway reachability."
        elif any(w in g for w in ["dns", "resolve", "nxdomain", "lookup"]):
            symptom = "DNS_FAILURE"
            remediation = "Clear local DNS resolver cache, configure secondary DNS server (e.g. 1.1.1.1, 8.8.8.8)."
        elif any(w in g for w in ["latency", "slow", "jitter", "lag"]):
            symptom = "LATENCY"
            remediation = "Identify routing hops with elevated RTT and inspect interface MTU."
        elif any(w in g for w in ["socket", "port", "refused", "timeout", "closed"]):
            symptom = "SOCKET_REFUSED"
            remediation = "Check firewall inbound/outbound rules and verify listening service on target port."
        else:
            symptom = "GENERAL"
            remediation = "Perform full stack network diagnosis: interface -> route -> dns -> ping."

        # Structured diagnostic stages (Read-only observation)
        diagnostic_stages = [
            {
                "stage": 1,
                "name": "Layer 1/2 Interface State Inspection",
                "capability": "network.interface_list",
                "description": "Inspect adapter status, IP allocation, link speed, and packet drop counters.",
            },
            {
                "stage": 2,
                "name": "Layer 3 Routing Table & Gateway Inspection",
                "capability": "network.route_inspect",
                "description": "Verify default gateway route binding and metric consistency.",
            },
            {
                "stage": 3,
                "name": "Application/Name Layer DNS Resolution",
                "capability": "network.dns_query",
                "description": f"Query DNS resolution latency and records for target host '{target_host or 'default'}'.",
            },
            {
                "stage": 4,
                "name": "End-to-End ICMP Probing & Route Tracing",
                "capability": "network.ping",
                "description": f"Probe round-trip latency and packet loss to '{target_host or 'gateway'}'.",
            },
        ]

        if target_port:
            diagnostic_stages.append({
                "stage": 5,
                "name": "Transport Layer Socket Probe",
                "capability": "network.socket_probe",
                "description": f"Test TCP/UDP socket handshake on port {target_port}.",
            })

        return {
            "target_host": target_host,
            "target_port": target_port,
            "symptom_category": symptom,
            "diagnostic_stages": diagnostic_stages,
            "remediation_candidate": remediation,
            "required_capabilities": [s["capability"] for s in diagnostic_stages],
        }
