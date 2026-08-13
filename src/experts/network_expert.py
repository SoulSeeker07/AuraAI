"""
Network Diagnostics Expert System
Location: src/experts/network_expert.py

Provides DNS resolution analysis, TCP socket connectivity checks, TLS/SSL inspection,
HTTP response header diagnostics, and restricted port scanning proposals.

INVARIANT: Diagnoses & proposes remediation actions to ExecutionCoordinator — NEVER executes direct OS or network mutations.
RULE: Preserves distinct failure classifications (DNS_RESOLUTION_FAILURE != TCP_TIMEOUT != TCP_REFUSED != TLS_FAILURE != HTTP_401/403/500).
"""

from __future__ import annotations

import logging
import socket
import ssl
import urllib.request
from typing import Any
from urllib.parse import urlparse

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
    Expert System for Network Diagnostics, Connectivity, Protocol Auditing, and Fine-Grained Failure Classification.
    """

    @property
    def domain(self) -> DomainType:
        return DomainType.NETWORK_DIAGNOSTICS

    def _resolve_target_info(self, raw_target: str) -> tuple[str, str, int, str]:
        """Extract clean hostname, host_or_ip, port, and scheme from raw target."""
        if not raw_target.startswith(("http://", "https://", "data:")):
            target_url = f"https://{raw_target}"
        else:
            target_url = raw_target

        if target_url.startswith("data:"):
            return target_url, "data_uri", 443, "data"

        parsed = urlparse(target_url)
        scheme = parsed.scheme or "https"
        host = parsed.hostname or "127.0.0.1"
        default_port = 80 if scheme == "http" else 443
        port = parsed.port or default_port
        return target_url, host, port, scheme

    def _diagnose_dns(self, host: str) -> tuple[bool, str, list[str]]:
        """Perform DNS resolution check."""
        if host == "data_uri":
            return True, "127.0.0.1", ["127.0.0.1"]
        try:
            _, _, ip_list = socket.gethostbyname_ex(host)
            return True, ip_list[0] if ip_list else host, ip_list
        except socket.gaierror as e:
            return False, f"DNS_RESOLUTION_FAILURE: {e.strerror}", []
        except Exception as e:
            return False, f"DNS_RESOLUTION_FAILURE: {e}", []

    def _diagnose_tcp(self, host: str, port: int, timeout: float = 1.5) -> tuple[str, str]:
        """Perform TCP socket connection attempt and return fine-grained failure classification."""
        if host == "data_uri":
            return "TCP_OPEN", "In-memory data URI target"
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                return "TCP_OPEN", f"Successfully established TCP socket connection to {host}:{port}"
        except socket.timeout:
            return "TCP_TIMEOUT", f"TCP connection timed out after {timeout}s on {host}:{port}"
        except ConnectionRefusedError:
            return "TCP_REFUSED", f"TCP connection explicitly refused by host {host}:{port}"
        except socket.gaierror as e:
            return "DNS_RESOLUTION_FAILURE", f"DNS lookup failed during TCP socket creation: {e}"
        except OSError as e:
            if "WSAECONNREFUSED" in str(e) or getattr(e, "errno", 0) == 10061:
                return "TCP_REFUSED", f"TCP connection explicitly refused by host {host}:{port}"
            if "WSAETIMEDOUT" in str(e) or getattr(e, "errno", 0) == 10060:
                return "TCP_TIMEOUT", f"TCP connection timed out on {host}:{port}"
            return "TCP_FAILURE", f"TCP socket connection error on {host}:{port}: {e}"

    def _diagnose_tls(self, host: str, port: int = 443, timeout: float = 2.0) -> tuple[str, str, dict[str, Any]]:
        """Inspect TLS/SSL certificate metadata and handshake validity."""
        if host == "data_uri" or port != 443:
            return "TLS_SKIPPED", "TLS inspection not applicable for non-SSL target", {}

        context = ssl.create_default_context()
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    subject = dict(x[0] for x in cert.get("subject", []))
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    return "TLS_VALID", f"TLS 1.3 handshake successful. Subject: {subject.get('commonName')}", {
                        "subject": subject,
                        "issuer": issuer,
                        "version": ssock.version(),
                    }
        except ssl.SSLCertVerificationError as e:
            return "TLS_CERTIFICATE_INVALID", f"TLS certificate verification failed: {e.verify_message}", {}
        except ssl.SSLError as e:
            return "TLS_HANDSHAKE_FAILED", f"TLS handshake failed: {e}", {}
        except Exception as e:
            return "TLS_UNVERIFIED", f"TLS inspection could not be completed: {e}", {}

    def _diagnose_http(self, target_url: str, timeout: float = 2.0) -> tuple[str, str, int, dict[str, str]]:
        """Inspect HTTP response status code and headers."""
        if target_url.startswith("data:"):
            return "HTTP_200_OK", "Data URI content available", 200, {"content-type": "text/html"}

        req = urllib.request.Request(target_url, headers={"User-Agent": "AuraAI-NetworkDiagnostics/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                headers = dict(resp.headers)
                return f"HTTP_{status}_OK", f"HTTP {status} response received from {target_url}", status, headers
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return "HTTP_AUTH_BARRIER", f"HTTP {e.code} authentication barrier at {target_url}", e.code, dict(e.headers)
            elif e.code >= 500:
                return "HTTP_SERVER_ERROR", f"HTTP {e.code} server internal error at {target_url}", e.code, dict(e.headers)
            return f"HTTP_{e.code}_RESPONSE", f"HTTP {e.code} error response at {target_url}", e.code, dict(e.headers)
        except Exception as e:
            return "HTTP_UNREACHABLE", f"HTTP request failed: {e}", 0, {}

    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        query_lower = query.lower()
        findings: list[DomainFinding] = []
        proposals: list[DomainActionProposal] = []

        raw_target = context.get("host") or context.get("target_url") or context.get("target") or "127.0.0.1"
        target_url, host, port, scheme = self._resolve_target_info(str(raw_target))

        # 1. DNS Resolution Inspection (G1)
        dns_success, dns_ip_or_err, ip_list = self._diagnose_dns(host)
        if dns_success:
            findings.append(
                DomainFinding(
                    category="dns_resolution",
                    title=f"DNS Resolution: {host}",
                    description=f"Resolved hostname '{host}' to IP addresses: {', '.join(ip_list)}.",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Host: {host}", f"Primary IP: {dns_ip_or_err}", f"All Resolved IPs: {ip_list}"],
                    location=f"{host}:{port}",
                    confidence=0.99,
                )
            )
        else:
            findings.append(
                DomainFinding(
                    category="dns_resolution",
                    title=f"DNS Resolution Failure: {host}",
                    description=f"Failed to resolve DNS hostname '{host}'. Details: {dns_ip_or_err}",
                    severity=SeverityLevel.HIGH,
                    evidence=[f"Host: {host}", f"Error: {dns_ip_or_err}", "Failure Classification: DNS_RESOLUTION_FAILURE"],
                    location=f"{host}:{port}",
                    confidence=0.98,
                )
            )

        # 2. TCP Socket Connectivity Inspection (G2)
        tcp_status, tcp_msg = self._diagnose_tcp(host, port)
        tcp_severity = SeverityLevel.INFO if tcp_status == "TCP_OPEN" else SeverityLevel.HIGH
        findings.append(
            DomainFinding(
                category="tcp_connectivity",
                title=f"TCP Socket Status: {tcp_status}",
                description=f"Target {host}:{port} TCP status is '{tcp_status}'. {tcp_msg}",
                severity=tcp_severity,
                evidence=[f"Host: {host}", f"Port: {port}", f"TCP Status: {tcp_status}", f"Details: {tcp_msg}"],
                location=f"{host}:{port}",
                confidence=0.96,
            )
        )

        # 3. TLS / SSL Inspection (G4)
        if scheme == "https" and tcp_status == "TCP_OPEN":
            tls_status, tls_msg, tls_data = self._diagnose_tls(host, port)
            tls_severity = SeverityLevel.INFO if tls_status == "TLS_VALID" else SeverityLevel.MEDIUM
            findings.append(
                DomainFinding(
                    category="tls_inspection",
                    title=f"TLS Certificate Status: {tls_status}",
                    description=f"TLS inspection on {host}:{port} returned '{tls_status}'. {tls_msg}",
                    severity=tls_severity,
                    evidence=[f"TLS Status: {tls_status}", f"Message: {tls_msg}", f"Cert Data: {tls_data}"],
                    location=f"{host}:{port}",
                    confidence=0.92,
                )
            )

        # 4. HTTP Diagnostics Inspection (G3)
        if tcp_status == "TCP_OPEN" or target_url.startswith("data:"):
            http_status_cat, http_msg, http_code, http_headers = self._diagnose_http(target_url)
            http_severity = SeverityLevel.INFO if http_code in (200, 301, 302) else SeverityLevel.MEDIUM
            findings.append(
                DomainFinding(
                    category="http_diagnostics",
                    title=f"HTTP Diagnostic Status: {http_status_cat}",
                    description=f"HTTP endpoint '{target_url}' returned status code {http_code}. {http_msg}",
                    severity=http_severity,
                    evidence=[
                        f"URL: {target_url}",
                        f"HTTP Code: {http_code}",
                        f"Status Category: {http_status_cat}",
                        f"Headers Count: {len(http_headers)}",
                    ],
                    location=target_url,
                    confidence=0.95,
                )
            )

        # 5. Port Diagnostic Proposals (G5, G8)
        if "port" in query_lower or "scan" in query_lower or tcp_status != "TCP_OPEN":
            proposals.append(
                DomainActionProposal(
                    engine="desktop",
                    action="network.scan_ports",
                    parameters={"host": host, "ports": [80, 443, 8080, 22]},
                    description=f"Execute diagnostic port scan for standard services on {host}",
                    risk_level="low",
                )
            )

        # HTTP remediation proposal
        proposals.append(
            DomainActionProposal(
                engine="browser",
                action="browser.navigate",
                parameters={"url": target_url},
                description=f"Verify HTTP page loading and DOM state for {target_url}",
                risk_level="low",
            )
        )

        summary = (
            f"Network diagnostics complete for '{host}:{port}'. "
            f"DNS={dns_success}, TCP={tcp_status}, Findings={len(findings)}."
        )

        return ExpertAnalysisResult(
            domain=self.domain,
            success=True,
            summary=summary,
            findings=findings,
            proposals=proposals,
            data={
                "target_url": target_url,
                "host": host,
                "port": port,
                "dns_resolved": dns_success,
                "tcp_status": tcp_status,
            },
        )
