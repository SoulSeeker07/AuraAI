"""
Network Engineering Expert Planner (M25 Phase 3)
Location: src/experts/network/planner.py

Specialized domain planner coordinating adapter inspection, routing analysis,
DNS query diagnostics, packet loss detection, and transport socket probing.

Architectural Invariants:
1. Pure Reasoning: Generates DomainAssessment and PlanDAG data structures.
   Zero direct capability execution, zero network adapter mutation during planning.
2. Strict Separation: Read-only diagnostic observation is cleanly separated from
   active remediation (which requires explicit ActionRisk.HIGH confirmation).
3. Causal Continuity: Preserves event_id, correlation_id, and assessment_id.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import PlanValidationResult
from core.orchestration.autonomy_mode import ActionRisk
from ..base_expert import DomainExpertPlanner
from ..models import DomainAssessment, PlanDAG, PlanNode
from .connectivity_diagnostician import ConnectivityDiagnostician
from .dns_analyzer import DNSAnalyzer
from .interface_analyzer import InterfaceAnalyzer
from .routing_analyzer import RoutingAnalyzer

logger = logging.getLogger(__name__)


class NetworkEngineeringExpertPlanner(DomainExpertPlanner):
    """
    Professional domain planner for network engineering, connectivity diagnostics, and topology analysis.
    """

    def __init__(
        self,
        interface_analyzer: InterfaceAnalyzer | None = None,
        dns_analyzer: DNSAnalyzer | None = None,
        routing_analyzer: RoutingAnalyzer | None = None,
        diagnostician: ConnectivityDiagnostician | None = None,
    ) -> None:
        self.interface_analyzer = interface_analyzer or InterfaceAnalyzer()
        self.dns_analyzer = dns_analyzer or DNSAnalyzer()
        self.routing_analyzer = routing_analyzer or RoutingAnalyzer()
        self.diagnostician = diagnostician or ConnectivityDiagnostician()

    @property
    def domain(self) -> str:
        return "network_engineering"

    @property
    def description(self) -> str:
        return "Specialized expert for network adapter telemetry, DNS resolution, routing inspection, packet loss analysis, and socket diagnostics."

    @property
    def supported_intents(self) -> list[str]:
        return [
            "network.diagnose",
            "network.dns_audit",
            "network.latency_trace",
            "network.route_inspect",
            "network.remediate",
        ]

    def can_handle(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, float, str]:
        """
        Evaluates goal text against network engineering semantic patterns.
        """
        g = goal_text.lower().strip()
        ctx = context or {}

        # Check explicit intent
        intent = ctx.get("intent", "")
        if intent in self.supported_intents:
            return True, 0.98, f"Direct match with supported intent '{intent}'."

        # High-confidence indicators
        high_indicators = [
            r"\bping\b", r"\bdns\b", r"\btraceroute\b", r"\bpacket loss\b", r"\blatency\b", r"\bsocket\b",
            r"\brouting table\b", r"\bdefault gateway\b", r"\bethernet\b", r"\bwi-fi\b", r"\bwifi\b",
            r"\badapter\b", r"\bip address\b", r"\bsubnet\b", r"\btcp handshake\b", r"\bport 80\b",
            r"\bport 443\b", r"\bport 8080\b", r"\bnetwork diagnosis\b", r"\brtt\b", r"\bjitter\b"
        ]
        matched_high = [ind for ind in high_indicators if re.search(ind, g)]
        if matched_high:
            clean_names = [ind.replace(r"\b", "") for ind in matched_high]
            confidence = min(0.96, 0.82 + (0.04 * len(matched_high)))
            return True, confidence, f"Matched network engineering signals: {', '.join(clean_names)}."

        # Medium-confidence indicators
        med_indicators = [
            r"\bconnection\b", r"\btimeout\b", r"\boffline\b", r"\bunreachable\b",
            r"\binternet\b", r"\bbandwidth\b"
        ]
        matched_med = [ind for ind in med_indicators if re.search(ind, g)]
        if matched_med:
            clean_names = [ind.replace(r"\b", "") for ind in matched_med]
            return True, 0.70, f"Matched connectivity-related terms: {', '.join(clean_names)}."

        return False, 0.10, "Goal does not require specialized network engineering expertise."

    async def assess(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> DomainAssessment:
        """
        Conducts deep network domain evaluation and synthesizes findings and strategy.
        """
        ctx = context or {}
        causal = ctx.get("causal_context", {})
        strategy_info = self.diagnostician.formulate_diagnostic_strategy(goal_text, context=ctx)

        findings: list[str] = [
            f"Symptom Category: {strategy_info['symptom_category']}",
        ]
        if strategy_info["target_host"]:
            findings.append(f"Target Host: {strategy_info['target_host']}")
        if strategy_info["target_port"]:
            findings.append(f"Target Port: {strategy_info['target_port']}")
        if strategy_info["remediation_candidate"]:
            findings.append(f"Candidate Remediation: {strategy_info['remediation_candidate']}")

        assumptions = [
            "Local OS network stack is active.",
            "ICMP and socket probes are permitted by local security policy.",
            "Diagnostic read observations do not disrupt active traffic.",
        ]

        required_caps = list(strategy_info["required_capabilities"])
        strategy = (
            f"Layered Diagnostic Inspection: "
            f"1. Adapters -> 2. Routing -> 3. DNS ({strategy_info['target_host'] or 'target'}) -> "
            f"4. ICMP/RTT -> 5. Socket Handshake. Zero mutation during diagnosis."
        )

        return DomainAssessment.create(
            domain=self.domain,
            confidence=0.94,
            findings=findings,
            assumptions=assumptions,
            required_capabilities=required_caps,
            recommended_strategy=strategy,
            causal_context=causal,
            metadata={"symptom": strategy_info["symptom_category"], "host": strategy_info["target_host"]},
        )

    async def generate_plan(
        self,
        goal_text: str,
        assessment: DomainAssessment,
        context: dict[str, Any] | None = None,
    ) -> PlanDAG:
        """
        Synthesizes a dependency-ordered PlanDAG for network diagnostics.
        """
        plan = PlanDAG.create(
            domain=self.domain,
            goal=goal_text,
            assessment_id=assessment.assessment_id,
            causal_context=dict(assessment.causal_context),
        )

        # Stage 1: Parallel Layer 1/2 & Layer 3 Baseline
        plan.add_node(
            PlanNode(
                node_id="net_iface_01",
                capability="network.interface_list",
                description="List adapter states, link speeds, IP assignments, and packet error counts.",
                risk_level=ActionRisk.LOW,
            )
        )
        plan.add_node(
            PlanNode(
                node_id="net_route_02",
                capability="network.route_inspect",
                description="Inspect routing table and verify default gateway binding.",
                risk_level=ActionRisk.LOW,
            )
        )

        # Stage 2: DNS Resolution
        plan.add_node(
            PlanNode(
                node_id="net_dns_03",
                capability="network.dns_query",
                dependencies=["net_iface_01", "net_route_02"],
                description="Query DNS resolution records and evaluate lookup latency.",
                risk_level=ActionRisk.LOW,
            )
        )

        # Stage 3: End-to-End ICMP Probing
        plan.add_node(
            PlanNode(
                node_id="net_ping_04",
                capability="network.ping",
                dependencies=["net_dns_03"],
                description="Probe round-trip time (RTT) and packet drop rate to target host/gateway.",
                risk_level=ActionRisk.LOW,
            )
        )

        # Stage 4: Socket Handshake (if port specified or applicable)
        if "port" in goal_text.lower() or "socket" in goal_text.lower():
            plan.add_node(
                PlanNode(
                    node_id="net_socket_05",
                    capability="network.socket_probe",
                    dependencies=["net_ping_04"],
                    description="Perform TCP/UDP socket handshake test to evaluate port accessibility.",
                    risk_level=ActionRisk.LOW,
                )
            )

        plan.compute_execution_stages()
        return plan
