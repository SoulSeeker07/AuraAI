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
