"""
Interface Analyzer for Network Engineering Expert (M25 Phase 3)
Location: src/experts/network/interface_analyzer.py

Analyzes network adapter states, IP assignments, MAC addresses, MTU, and link status.
Pure in-memory analysis, zero OS mutation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InterfaceAnalyzer:
    """
    Evaluates network adapter metadata and identifies interface-level anomalies.
    """

    def analyze_interfaces(self, interfaces: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyzes a list of network interface telemetry dictionaries.

        Returns:
            Dictionary containing:
                - total_interfaces: int
                - active_interfaces: list[str]
                - apipa_interfaces: list[str] (169.254.x.x link-local auto-ip)
                - disconnected_interfaces: list[str]
                - anomalies: list[str]
        """
        active: list[str] = []
        apipa: list[str] = []
        disconnected: list[str] = []
        anomalies: list[str] = []

        for iface in interfaces:
            name = iface.get("name", "Unknown")
            is_up = iface.get("is_up", False) or iface.get("status", "").lower() == "up"
            ip = iface.get("ip_address") or iface.get("ipv4", "")

            if not is_up:
                disconnected.append(name)
            else:
                active.append(name)
                if ip.startswith("169.254."):
                    apipa.append(name)
                    anomalies.append(f"Interface '{name}' has APIPA address ({ip}), indicating DHCP failure.")

            # Packet drops or errors
            rx_errors = iface.get("rx_errors", 0)
            tx_errors = iface.get("tx_errors", 0)
            if rx_errors > 100 or tx_errors > 100:
                anomalies.append(f"Interface '{name}' reports elevated packet errors (RX: {rx_errors}, TX: {tx_errors}).")

        if not active:
            anomalies.append("No active network interfaces detected on the host.")

        return {
            "total_interfaces": len(interfaces),
            "active_interfaces": active,
            "apipa_interfaces": apipa,
            "disconnected_interfaces": disconnected,
            "anomalies": anomalies,
        }
