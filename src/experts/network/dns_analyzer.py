"""
DNS Analyzer for Network Engineering Expert (M25 Phase 3)
Location: src/experts/network/dns_analyzer.py

Analyzes DNS resolution latency, records (A, AAAA, CNAME), NXDOMAIN errors, and timeout patterns.
Pure in-memory analysis, zero OS mutation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DNSAnalyzer:
    """
    Evaluates DNS queries and identifies resolution bottlenecks and failures.
    """

    def analyze_dns_result(self, domain: str, dns_data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyzes DNS query telemetry.

        Returns:
            Dictionary containing:
                - domain: str
                - resolved: bool
                - records: list[str]
                - response_time_ms: float
                - is_slow: bool (>150ms)
                - error_category: str | None ('NXDOMAIN', 'TIMEOUT', 'SERVFAIL', None)
                - diagnosis: str
        """
        resolved = dns_data.get("resolved", False)
        records = dns_data.get("records", [])
        response_time = float(dns_data.get("response_time_ms", 0.0))
        raw_error = str(dns_data.get("error", "")).lower()

        error_category = None
        if not resolved:
            if "nxdomain" in raw_error or "name not found" in raw_error:
                error_category = "NXDOMAIN"
            elif "timeout" in raw_error or "timed out" in raw_error:
                error_category = "TIMEOUT"
            elif "servfail" in raw_error:
                error_category = "SERVFAIL"
            else:
                error_category = "RESOLUTION_FAILED"

        is_slow = response_time > 150.0

        if not resolved:
            diagnosis = f"DNS resolution for '{domain}' failed with {error_category}."
        elif is_slow:
            diagnosis = f"DNS resolved '{domain}' to {records} with high latency ({response_time:.1f} ms)."
        else:
            diagnosis = f"DNS healthy: '{domain}' resolved in {response_time:.1f} ms."

        return {
            "domain": domain,
            "resolved": resolved,
            "records": records,
            "response_time_ms": response_time,
            "is_slow": is_slow,
            "error_category": error_category,
            "diagnosis": diagnosis,
        }
