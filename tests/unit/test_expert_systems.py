"""
Unit Tests for M25.1 Professional Expert Systems
Location: tests/unit/test_expert_systems.py

Verifies domain expert system contracts, proposal generation, policy evaluation,
and ExecutionCoordinator integration without violating architecture freeze.
"""

import os
import sys

sys.path.insert(0, os.path.abspath("src"))

import asyncio
import pytest

from brain.aca.engine_interface import EngineRegistry
from brain.execution_coordinator import ExecutionCoordinator
from brain.goal_verifier import GoalVerifier
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction
from experts import (
    BaseExpertSystem,
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
    expert_reg.register(SoftwareEngineeringExpert())
    expert_reg.register(NetworkDiagnosticsExpert())
    expert_reg.register(CybersecurityAuditExpert())
    expert_reg.register(FinancialAnalysisExpert())
    return reg, expert_reg


def test_g1_four_domain_types_stable_contracts():
    setup_fresh_environment()
    expert_reg = DomainExpertRegistry.get_instance()

    domains = [
        DomainType.SOFTWARE_ENGINEERING,
        DomainType.NETWORK_DIAGNOSTICS,
        DomainType.CYBERSECURITY_AUDIT,
        DomainType.FINANCIAL_ANALYSIS,
    ]
    for d in domains:
        expert = expert_reg.resolve(d)
        assert expert is not None
        assert expert.domain == d


def test_g2_expert_registry_registration_discovery():
    setup_fresh_environment()
    expert_reg = DomainExpertRegistry.get_instance()

    assert expert_reg.has_expert("software_engineering")
    assert expert_reg.has_expert("network_diagnostics")
    assert expert_reg.has_expert("cybersecurity_audit")
    assert expert_reg.has_expert("financial_analysis")
    assert len(expert_reg.list_domains()) == 4


def test_g3_g4_g5_analysis_result_findings_proposals_schema():
    setup_fresh_environment()
    sw_expert = SoftwareEngineeringExpert()

    res = sw_expert.analyze("refactor module src/core/nlu/nlu_engine.py", {"target_path": "src/core/nlu/nlu_engine.py"})
    assert res.domain == DomainType.SOFTWARE_ENGINEERING
    assert res.success is True
    assert len(res.findings) > 0
    assert len(res.proposals) > 0

    finding = res.findings[0]
    assert isinstance(finding.severity, SeverityLevel)
    assert len(finding.evidence) > 0

    proposal = res.proposals[0]
    assert isinstance(proposal, DomainActionProposal)
    # G5 Invariant: Proposals are data objects, not active calls
    assert proposal.engine == "engineering"
    assert proposal.action == "code.edit"


def test_g6_g7_g8_proposals_route_through_policy_coordinator_verifier():
    setup_fresh_environment()
    sec_expert = CybersecurityAuditExpert()
    coord = ExecutionCoordinator()
    policy = ExecutionPolicy.get_instance()

    # Normal low-risk proposal
    analysis = sec_expert.analyze("audit permissions in repo", {"target": "src"})
    exec_map = analysis.to_execution_map("Audit repository permissions")

    # Step passes through ExecutionPolicy evaluation
    steps = exec_map["steps"]
    for step in steps:
        p_dec = policy.evaluate_action(step["engine"], step["action"], step["parameters"])
        assert p_dec.action != PolicyAction.FAIL

    # Physical execution routes through ExecutionCoordinator
    res = asyncio.run(coord.coordinate(exec_map))
    assert res.success is True
    assert "goal_verification" in res.data
    assert res.data["goal_verification"]["passed"] is True


def test_g9_expert_exception_isolation():
    setup_fresh_environment()

    class FaultyExpert(BaseExpertSystem):
        @property
        def domain(self) -> DomainType:
            return DomainType.SOFTWARE_ENGINEERING

        def _perform_analysis(self, query: str, context: dict) -> ExpertAnalysisResult:
            raise RuntimeError("Simulated expert crash during AST parse")

    faulty = FaultyExpert()
    # High-level analyze() catches exception safely
    res = faulty.analyze("crash test")
    assert res.success is False
    assert "Simulated expert crash" in res.error
    assert res.domain == DomainType.SOFTWARE_ENGINEERING


def test_g10_unknown_domain_returns_unsupported():
    setup_fresh_environment()
    expert_reg = DomainExpertRegistry.get_instance()

    expert = expert_reg.resolve("quantum_computing_domain")
    assert expert is None


def test_g11_expert_cannot_bypass_permissions():
    setup_fresh_environment()
    sec_expert = CybersecurityAuditExpert()
    policy = ExecutionPolicy.get_instance()

    # Destructive high-risk proposal generated by expert
    analysis = sec_expert.analyze("purge protected system file", {"target": "C:/Windows/System32/config.sys"})
    exec_map = analysis.to_execution_map("Purge protected file")

    steps = exec_map["steps"]
    high_risk_step = steps[0]

    # ExecutionPolicy halts high-risk step under default ASSISTED autonomy
    p_dec = policy.evaluate_action(high_risk_step["engine"], high_risk_step["action"], high_risk_step["parameters"])
    assert p_dec.action == PolicyAction.ASK_USER


def test_m25_2_software_expert_repository_ast_discovery():
    setup_fresh_environment()
    sw_expert = SoftwareEngineeringExpert()

    # Analyze actual AuraAI workspace
    res = sw_expert.analyze("audit workspace AST and git health", {"target_path": "src/experts", "workspace_root": "."})
    assert res.success is True
    assert res.domain == DomainType.SOFTWARE_ENGINEERING

    # Verify Findings Schema & Discovery
    disc_findings = [f for f in res.findings if f.category == "repository_discovery"]
    assert len(disc_findings) > 0
    assert disc_findings[0].location != ""
    assert disc_findings[0].confidence > 0.8

    # Verify Dependency Vulnerability Status (Honest Unknown)
    dep_findings = [f for f in res.findings if f.category == "dependency_audit"]
    assert len(dep_findings) > 0
    assert "UNAVAILABLE (Honest Unknown)" in str(dep_findings[0].evidence)

    # Verify Git Health Finding
    git_findings = [f for f in res.findings if f.category == "git_health"]
    assert len(git_findings) > 0

    # Verify Proposal Generation (Never Direct Execution)
    assert len(res.proposals) > 0
    assert all(isinstance(p, DomainActionProposal) for p in res.proposals)


def test_m25_3_network_expert_dns_tcp_tls_http_diagnostics():
    setup_fresh_environment()
    net_expert = NetworkDiagnosticsExpert()

    # 1. Test local / loopback target diagnostics
    res_local = net_expert.analyze("diagnose 127.0.0.1 connectivity", {"host": "127.0.0.1"})
    assert res_local.success is True
    assert res_local.domain == DomainType.NETWORK_DIAGNOSTICS

    dns_findings = [f for f in res_local.findings if f.category == "dns_resolution"]
    assert len(dns_findings) > 0
    assert dns_findings[0].location == "127.0.0.1:443"
    assert dns_findings[0].confidence > 0.9

    tcp_findings = [f for f in res_local.findings if f.category == "tcp_connectivity"]
    assert len(tcp_findings) > 0
    assert "TCP Status:" in str(tcp_findings[0].evidence)

    # 2. Test fine-grained failure classification on invalid hostname
    res_invalid = net_expert.analyze("diagnose invalid_host_xyz_9999.invalid", {"host": "invalid_host_xyz_9999.invalid"})
    assert res_invalid.success is True
    dns_fail_findings = [f for f in res_invalid.findings if f.category == "dns_resolution"]
    assert len(dns_fail_findings) > 0
    assert "DNS_RESOLUTION_FAILURE" in str(dns_fail_findings[0].evidence)


def test_m25_4_security_expert_permission_secrets_posture():
    setup_fresh_environment()
    sec_expert = CybersecurityAuditExpert()

    # 1. Audit real workspace
    res = sec_expert.analyze("audit workspace security posture", {"target_path": "src/experts"})
    assert res.success is True
    assert res.domain == DomainType.CYBERSECURITY_AUDIT
    assert res.data.get("posture_score", 0.0) > 0.0

    # Verify Findings Categories
    categories = [f.category for f in res.findings]
    assert "filesystem_permissions" in categories
    assert "sensitive_file_detection" in categories
    assert "process_privileges" in categories
    assert "open_port_audit" in categories
    assert "security_posture" in categories

    # 2. Verify Honest Inaccessible Path Handling
    res_inaccessible = sec_expert.analyze("audit non_existent_path_xyz_99", {"target_path": "non_existent_path_xyz_99"})
    assert res_inaccessible.success is True
    inaccess_findings = [f for f in res_inaccessible.findings if f.category == "filesystem_permissions"]
    assert len(inaccess_findings) > 0
    assert "INSPECTION_UNAVAILABLE" in str(inaccess_findings[0].evidence)
    assert inaccess_findings[0].confidence == 0.50


def test_m25_5_financial_expert_metrics_cagr_margins():
    setup_fresh_environment()
    fin_expert = FinancialAnalysisExpert()

    # 1. Analyze valid CSV financial dataset
    csv_data = "year,revenue,cogs,net_income\n2022,100,60,20\n2023,150,80,35\n2024,225,110,60"
    res = fin_expert.analyze("calculate revenue growth and CAGR", {"csv_content": csv_data})
    assert res.success is True
    assert res.domain == DomainType.FINANCIAL_ANALYSIS
    assert res.data.get("periods_count") == 3
    assert res.data.get("cagr") is not None

    categories = [f.category for f in res.findings]
    assert "revenue_growth" in categories
    assert "cagr_analysis" in categories
    assert "margin_analysis" in categories
    assert "trend_detection" in categories

    # 2. Verify Honest Invalid Data Handling
    res_bad = fin_expert.analyze("analyze empty dataset", {"csv_content": "invalid_data_without_revenue_col"})
    assert res_bad.success is True
    bad_findings = [f for f in res_bad.findings if f.category == "schema_validation"]
    assert len(bad_findings) > 0
    assert "INVALID_FINANCIAL_DATA" in str(bad_findings[0].evidence)
    assert bad_findings[0].confidence == 0.50




