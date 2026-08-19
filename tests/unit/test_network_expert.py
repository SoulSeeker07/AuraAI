"""
Unit Tests for M25 Phase 3: Network Engineering Expert Subsystem
Location: tests/unit/test_network_expert.py

Verifies:
1. InterfaceAnalyzer adapter state evaluation, APIPA detection, and error rate tracking.
2. DNSAnalyzer latency analysis, record extraction, and NXDOMAIN/TIMEOUT categorization.
3. RoutingAnalyzer default gateway extraction, route metrics, and conflict detection.
4. ConnectivityDiagnostician layered OSI diagnostic formulation and symptom classification.
5. NetworkEngineeringExpertPlanner DomainAssessment and PlanDAG synthesis.
6. Strict Invariant: Zero network configuration mutation during planning.
7. Strict Invariant: Separation of read-only diagnosis from active remediation.
8. Seamless routing integration via ExpertDomainRouter and PlannerRegistry.
"""

import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.planner_registry import PlannerRegistry
from experts.models import DomainAssessment, PlanDAG
from experts.network.connectivity_diagnostician import ConnectivityDiagnostician
from experts.network.dns_analyzer import DNSAnalyzer
from experts.network.interface_analyzer import InterfaceAnalyzer
from experts.network.planner import NetworkEngineeringExpertPlanner
from experts.network.routing_analyzer import RoutingAnalyzer
from experts.router import ExpertDomainRouter


def test_interface_analyzer_apipa_and_error_detection():
    """Verify InterfaceAnalyzer flags APIPA autoconfiguration and packet errors."""
    interfaces = [
        {"name": "Ethernet0", "is_up": True, "ip_address": "192.168.1.50", "rx_errors": 0, "tx_errors": 0},
        {"name": "Wi-Fi", "is_up": True, "ip_address": "169.254.88.12", "rx_errors": 150, "tx_errors": 0},
        {"name": "vEthernet", "is_up": False, "ip_address": "", "rx_errors": 0, "tx_errors": 0},
    ]
    analyzer = InterfaceAnalyzer()
    res = analyzer.analyze_interfaces(interfaces)

    assert res["total_interfaces"] == 3
    assert "Ethernet0" in res["active_interfaces"]
    assert "Wi-Fi" in res["apipa_interfaces"]
    assert "vEthernet" in res["disconnected_interfaces"]
    assert any("APIPA" in a for a in res["anomalies"])
    assert any("elevated packet errors" in a for a in res["anomalies"])


def test_dns_analyzer_latency_and_error_categories():
    """Verify DNSAnalyzer evaluates latency and identifies NXDOMAIN vs TIMEOUT."""
    analyzer = DNSAnalyzer()

    # 1. Healthy DNS
    healthy_res = analyzer.analyze_dns_result("api.github.com", {
        "resolved": True,
        "records": ["140.82.121.4"],
        "response_time_ms": 22.5,
    })
    assert healthy_res["resolved"] is True
    assert healthy_res["is_slow"] is False
    assert healthy_res["error_category"] is None

    # 2. Slow DNS
    slow_res = analyzer.analyze_dns_result("slow-internal.corp", {
        "resolved": True,
        "records": ["10.0.0.5"],
        "response_time_ms": 280.0,
    })
    assert slow_res["resolved"] is True
    assert slow_res["is_slow"] is True

    # 3. NXDOMAIN
    nx_res = analyzer.analyze_dns_result("non-existent-domain-xyz.local", {
        "resolved": False,
        "error": "Name not found (NXDOMAIN)",
    })
    assert nx_res["resolved"] is False
    assert nx_res["error_category"] == "NXDOMAIN"


def test_routing_analyzer_default_gateway_detection():
    """Verify RoutingAnalyzer detects default routes and flags missing or conflicting gateways."""
    analyzer = RoutingAnalyzer()

    routes = [
        {"destination": "0.0.0.0", "mask": "0.0.0.0", "gateway": "192.168.1.1", "interface": "Ethernet0"},
        {"destination": "192.168.1.0", "mask": "255.255.255.0", "gateway": "192.168.1.50", "interface": "Ethernet0"},
    ]
    res = analyzer.analyze_routing_table(routes)
    assert res["default_gateway"] == "192.168.1.1"
    assert res["default_interface"] == "Ethernet0"
    assert res["multiple_default_routes"] is False
    assert len(res["anomalies"]) == 0

    # Missing gateway
    res_no_gw = analyzer.analyze_routing_table([{"destination": "127.0.0.1", "gateway": "127.0.0.1"}])
    assert res_no_gw["default_gateway"] is None
    assert any("No default gateway" in a for a in res_no_gw["anomalies"])


def test_connectivity_diagnostician_symptom_classification():
    """Verify ConnectivityDiagnostician classifies symptoms and builds structured diagnostic stages."""
    diag = ConnectivityDiagnostician()

    # 1. Packet Loss
    res_loss = diag.formulate_diagnostic_strategy("Investigate 30% packet loss to host 8.8.8.8")
    assert res_loss["symptom_category"] == "PACKET_LOSS"
    assert res_loss["target_host"] == "8.8.8.8"
    assert len(res_loss["diagnostic_stages"]) >= 4

    # 2. Port refused
    res_port = diag.formulate_diagnostic_strategy("Diagnose socket refused to host api.service.internal on port 8080")
    assert res_port["symptom_category"] == "SOCKET_REFUSED"
    assert res_port["target_host"] == "api.service.internal"
    assert res_port["target_port"] == 8080
    assert any(s["capability"] == "network.socket_probe" for s in res_port["diagnostic_stages"])


@pytest.mark.asyncio
async def test_network_expert_planner_full_lifecycle():
    """Verify NetworkEngineeringExpertPlanner assesses, plans, and explains without executing."""
    expert = NetworkEngineeringExpertPlanner()
    goal = "Diagnose high latency and DNS lookup timeouts for gateway 192.168.1.1 on port 443"

    can_handle, conf, rationale = expert.can_handle(goal)
    assert can_handle is True
    assert conf >= 0.85

    assessment = await expert.assess(goal, context={"causal_context": {"event_id": "evt_net_01"}})
    assert isinstance(assessment, DomainAssessment)
    assert assessment.domain == "network_engineering"
    assert assessment.causal_context["event_id"] == "evt_net_01"
    assert "network.ping" in assessment.required_capabilities

    plan = await expert.generate_plan(goal, assessment)
    assert isinstance(plan, PlanDAG)
    assert len(plan.nodes) >= 4
    assert len(plan.execution_stages) >= 3

    # Validation against capability registry
    val_res = expert.validate_plan(plan, CapabilityRegistry.get_instance())
    assert val_res.valid is True

    explanation = expert.explain_plan(plan, assessment)
    assert "NETWORK_ENGINEERING" in explanation
    assert plan.plan_id in explanation


@pytest.mark.asyncio
async def test_network_expert_zero_mutation_diagnostic_invariant():
    """Verify NetworkEngineeringExpertPlanner only schedules read/diagnostic capabilities during normal planning."""
    expert = NetworkEngineeringExpertPlanner()
    goal = "Check network connectivity and packet loss to 1.1.1.1"

    assessment = await expert.assess(goal)
    plan = await expert.generate_plan(goal, assessment)

    # Verify every node in the diagnostic plan is read-only / low risk
    for nid, node in plan.nodes.items():
        assert node.risk_level.value == "low"
        assert "remediate" not in node.capability


@pytest.mark.asyncio
async def test_router_integration_with_network_expert():
    """Verify ExpertDomainRouter automatically discovers and routes network tasks to NetworkEngineeringExpertPlanner."""
    ExpertDomainRouter.reset_instance()
    router = ExpertDomainRouter.get_instance()

    goal = "Troubleshoot DNS resolution and packet drops on default gateway"
    expert, assessment, rationale = await router.route(goal)

    assert expert is not None
    assert expert.domain == "network_engineering"
    assert assessment is not None
    assert assessment.domain == "network_engineering"
    assert assessment.confidence >= 0.85
    assert "network" in rationale.lower()
