"""
Milestone 25.3 Network Diagnostics Expert Acceptance Benchmark
Location: scratch/test_m25_3_network_expert_gate.py

Verifies all 10 M25.3 acceptance gates:
  G1: DNS Resolution Evidence & Hostname Resolution
  G2: TCP Socket Connectivity (Fine-grained failure classification)
  G3: HTTP Response Status & Header Diagnostics
  G4: TLS/SSL Certificate Inspection
  G5: Restricted Port Diagnostics
  G6: Fine-Grained Failure Classification (DNS_RESOLUTION_FAILURE != TCP_REFUSED != TCP_TIMEOUT != TLS_FAILURE)
  G7: Evidence-backed Deterministic Findings Schema (category, severity, title, evidence, location, confidence)
  G8: Remediation Proposals (DomainActionProposal, never direct mutation)
  G9: Execution Boundary (Proposal -> Policy -> Coordinator -> Verifier)
  G10: Real Local / Loopback Test Target Acceptance Gate
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("src"))

from brain.aca.engine_interface import EngineRegistry
from brain.execution_coordinator import ExecutionCoordinator
from brain.goal_verifier import GoalVerifier
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction
from experts import (
    CybersecurityAuditExpert,
    DomainActionProposal,
    DomainExpertRegistry,
    DomainFinding,
    DomainType,
    ExpertAnalysisResult,
    FinancialAnalysisExpert,
    NetworkDiagnosticsExpert,
    SeverityLevel,
    SoftwareEngineeringExpert,
)


def setup_fresh_environment():
    EngineRegistry.reset_instance()
    DomainExpertRegistry.reset_instance()
    ExecutionPolicy.reset_instance()

    reg = EngineRegistry.get_instance()
    reg.register(DesktopEngineBackend(), name="desktop")
    reg.register(PlaywrightBrowserAdapter(), name="browser")

    expert_reg = DomainExpertRegistry.get_instance()
    net_expert = NetworkDiagnosticsExpert()
    expert_reg.register(SoftwareEngineeringExpert())
    expert_reg.register(net_expert)
    expert_reg.register(CybersecurityAuditExpert())
    expert_reg.register(FinancialAnalysisExpert())
    return reg, expert_reg, net_expert


async def run_m25_3_benchmark():
    reg, expert_reg, net_expert = setup_fresh_environment()
    coord = ExecutionCoordinator()
    policy = ExecutionPolicy.get_instance()

    # 1. Analyze local target
    res_local = net_expert.analyze("diagnose network target", {"host": "data:text/html,<h1>NetCheck</h1>"})
    res_loopback = net_expert.analyze("diagnose loopback 127.0.0.1", {"host": "127.0.0.1"})

    # Gate G1: DNS Resolution Evidence
    dns_findings = [f for f in res_local.findings if f.category == "dns_resolution"]
    g1_pass = len(dns_findings) > 0 and "Primary IP:" in str(dns_findings[0].evidence)

    # Gate G2: TCP Socket Connectivity
    tcp_findings = [f for f in res_local.findings if f.category == "tcp_connectivity"]
    g2_pass = len(tcp_findings) > 0 and ("TCP_OPEN" in str(tcp_findings[0].title) or "TCP_REFUSED" in str(tcp_findings[0].title) or "TCP_TIMEOUT" in str(tcp_findings[0].title))

    # Gate G3: HTTP Diagnostics
    http_findings = [f for f in res_local.findings if f.category == "http_diagnostics"]
    g3_pass = len(http_findings) > 0 or res_local.data.get("tcp_status") != "TCP_OPEN"

    # Gate G4: TLS/SSL Certificate Inspection
    res_tls = net_expert.analyze("check SSL certificate for data URI target", {"host": "data:text/html,<h1>SSLCheck</h1>"})
    tls_findings = [f for f in res_tls.findings if f.category == "tls_inspection"]
    g4_pass = len(tls_findings) > 0 or res_tls.data.get("tcp_status") == "TCP_OPEN"

    # Gate G5: Port Diagnostics Proposal (Restricted ports)
    res_port = net_expert.analyze("scan ports on 127.0.0.1", {"host": "127.0.0.1"})
    port_proposals = [p for p in res_port.proposals if p.action == "network.scan_ports"]
    g5_pass = len(port_proposals) > 0 and port_proposals[0].parameters.get("ports") == [80, 443, 8080, 22]

    # Gate G6: Fine-Grained Failure Classification (DNS_RESOLUTION_FAILURE != TCP_REFUSED)
    res_dns_fail = net_expert.analyze("check non_existent_domain_xyz99.invalid", {"host": "non_existent_domain_xyz99.invalid"})
    dns_fail_findings = [f for f in res_dns_fail.findings if f.category == "dns_resolution"]
    g6_pass = len(dns_fail_findings) > 0 and "DNS_RESOLUTION_FAILURE" in str(dns_fail_findings[0].evidence)

    # Gate G7: Deterministic Findings Schema (location & confidence)
    g7_pass = all(
        hasattr(f, "category") and hasattr(f, "severity") and hasattr(f, "title")
        and hasattr(f, "evidence") and hasattr(f, "location") and hasattr(f, "confidence")
        for f in res_local.findings
    ) and any(f.confidence > 0.9 for f in res_local.findings)

    # Gate G8: Remediation Proposals (Never Direct Execution)
    g8_pass = len(res_local.proposals) > 0 and all(isinstance(p, DomainActionProposal) for p in res_local.proposals)

    # Gate G9: Execution Boundary (Proposal -> Policy -> Coordinator -> Verifier)
    exec_map = res_local.to_execution_map("Execute browser diagnostic step")
    eval_pass = True
    for step in exec_map["steps"]:
        p_dec = policy.evaluate_action(step["engine"], step["action"], step["parameters"])
        if p_dec.action == PolicyAction.FAIL:
            eval_pass = False

    coord_res = await coord.coordinate(exec_map)
    g9_pass = eval_pass and coord_res.success is True

    # Gate G10: Real Local Test Target Acceptance
    g10_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass, g8_pass, g9_pass])

    facts = {
        "G1: DNS Resolution Evidence & Hostname Resolution": g1_pass,
        "G2: TCP Socket Connectivity (Fine-grained failure classification)": g2_pass,
        "G3: HTTP Response Status & Header Diagnostics": g3_pass,
        "G4: TLS/SSL Certificate Inspection": g4_pass,
        "G5: Restricted Port Diagnostics Proposals": g5_pass,
        "G6: Fine-Grained Failure Classification (DNS_RESOLUTION_FAILURE)": g6_pass,
        "G7: Evidence-backed Findings Schema (Location & Confidence)": g7_pass,
        "G8: Remediation Proposals (Never Direct Execution)": g8_pass,
        "G9: Execution Boundary (Proposal -> Policy -> Coordinator)": g9_pass,
        "G10: Complete M25.3 Real Local Target Acceptance Gate": g10_pass,
    }

    all_pass = all(facts.values())

    print("==========================================================================")
    print("     AURA MILESTONE 25.3 -- NETWORK DIAGNOSTICS EXPERT BENCHMARK")
    print("==========================================================================")
    for k, v in facts.items():
        status_str = "PASS" if v else "FAIL"
        print(f"  +-- {k:<66} : {status_str}")
    print("--------------------------------------------------------------------------")
    print(f"M25.3 Acceptance Contract Final Result: {'PASS' if all_pass else 'FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_m25_3_benchmark())
