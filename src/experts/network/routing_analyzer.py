"""
Routing Analyzer for Network Engineering Expert (M25 Phase 3)
Location: src/experts/network/routing_analyzer.py

Analyzes IPv4/IPv6 routing tables, default gateways, subnet masks, and route metrics.
Pure in-memory analysis, zero OS mutation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RoutingAnalyzer:
    """
    Evaluates routing tables, gateway reachability, and metric conflicts.
    """

    def analyze_routing_table(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyzes routing table entries.

        Returns:
            Dictionary containing:
                - default_gateway: str | None
                - default_interface: str | None
                - route_count: int
                - multiple_default_routes: bool
                - anomalies: list[str]
        """
        default_routes: list[dict[str, Any]] = []
        anomalies: list[str] = []

        for r in routes:
            dest = r.get("destination", "")
            mask = r.get("mask", "")
            if dest in ("0.0.0.0", "default", "::/0") or mask in ("0.0.0.0", "0"):
                default_routes.append(r)

        multiple_defaults = len(default_routes) > 1
        if multiple_defaults:
            anomalies.append(f"Multiple default gateways detected ({len(default_routes)}). Potential metric conflict.")
        elif not default_routes:
            anomalies.append("No default gateway configured. Outbound internet routing will fail.")

        default_gw = default_routes[0].get("gateway") if default_routes else None
        default_iface = default_routes[0].get("interface") if default_routes else None

        return {
            "default_gateway": default_gw,
            "default_interface": default_iface,
            "route_count": len(routes),
            "multiple_default_routes": multiple_defaults,
            "anomalies": anomalies,
        }
