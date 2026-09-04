"""
Unit Tests for M25 Phase 4: Cybersecurity & Audit Expert Subsystem
Location: tests/unit/test_security_expert.py

Verifies:
1. CredentialScanner secret detection, pattern matching, and automated redaction.
2. AttackSurfaceAnalyzer listening port inspection and dangerous service classification.
3. VulnerabilityCorrelator package CVE matching and dangerous code pattern detection.
4. PolicyAuditor host hardening posture, firewall profile, and UAC evaluation.
5. CybersecurityExpertPlanner DomainAssessment and PlanDAG synthesis.
6. Strict Invariant: Zero system security modification during planning.
7. Strict Invariant: Separation of read-only audit observation from active remediation.
8. Seamless routing integration via ExpertDomainRouter and PlannerRegistry.
"""

import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.autonomy_mode import ActionRisk
from core.orchestration.planner_registry import PlannerRegistry
from experts.models import DomainAssessment, PlanDAG
from experts.router import ExpertDomainRouter
from experts.security.attack_surface_analyzer import AttackSurfaceAnalyzer
from experts.security.credential_scanner import CredentialScanner
from experts.security.planner import CybersecurityExpertPlanner
from experts.security.policy_auditor import PolicyAuditor
from experts.security.vulnerability_correlator import VulnerabilityCorrelator


def test_credential_scanner_detection_and_redaction():
    """Verify CredentialScanner identifies secrets and masks values to prevent leakage."""
    sample_text = """
OPENAI_API_KEY="sk-proj-abc1234567890abcdef1234567890"
AWS_KEY=AKIAIOSFODNN7EXAMPLE
GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyzAB
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0...
"""
    scanner = CredentialScanner()
    res = scanner.scan_content(sample_text, source_label=".env")

    assert res["exposed_count"] >= 4
    assert res["max_severity"] in ("HIGH", "CRITICAL")

    # Verify every finding has a masked preview that does NOT expose the full raw secret
    for finding in res["findings"]:
        assert "*" in finding["masked_preview"]
        assert "sk-proj-abc1234567890abcdef1234567890" not in finding["masked_preview"]
        assert "AKIAIOSFODNN7EXAMPLE" not in finding["masked_preview"]


def test_attack_surface_analyzer_dangerous_ports():
    """Verify AttackSurfaceAnalyzer flags unencrypted and public-facing high-risk ports."""
    analyzer = AttackSurfaceAnalyzer()

    open_ports = [
        {"port": 80, "bind_address": "127.0.0.1", "process": "nginx.exe"},
        {"port": 23, "bind_address": "0.0.0.0", "process": "telnetd.exe"},
        {"port": 445, "bind_address": "0.0.0.0", "process": "System"},
        {"port": 3389, "bind_address": "192.168.1.50", "process": "TermService"},
    ]
    res = analyzer.analyze_listening_ports(open_ports)

    assert res["total_listening"] == 4
    assert res["public_facing_count"] >= 2
    assert len(res["dangerous_findings"]) >= 2
    assert any(f["service"] == "Telnet" for f in res["dangerous_findings"])
    assert any(f["service"] == "SMB" for f in res["dangerous_findings"])
    assert res["risk_score"] > 5.0


def test_vulnerability_correlator_cve_and_code_patterns():
    """Verify VulnerabilityCorrelator identifies vulnerable packages and unsafe code constructs."""
    correlator = VulnerabilityCorrelator()

    # 1. Package CVE Matching
    installed = [
        {"name": "urllib3", "version": "1.26.15"},
        {"name": "requests", "version": "2.28.0"},
        {"name": "pytest", "version": "9.1.1"},
    ]
    cve_res = correlator.check_packages(installed)
    assert len(cve_res) >= 2
    assert any(c["cve"] == "CVE-2023-45803" for c in cve_res)
    assert any(c["cve"] == "CVE-2023-32681" for c in cve_res)

    # 2. Code Pattern Scanning
    dangerous_code = """
import pickle
def execute_payload(raw):
    data = pickle.loads(raw)
    eval(data.get('command'))
"""
    code_res = correlator.check_code_patterns(dangerous_code, file_path="handler.py")
    assert len(code_res) >= 2
    assert any(f["pattern"] == "Unsafe Eval" for f in code_res)
    assert any(f["pattern"] == "Unsafe Pickle Deserialization" for f in code_res)


def test_policy_auditor_compliance_evaluation():
    """Verify PolicyAuditor audits firewall profiles, Defender state, and UAC elevation."""
    auditor = PolicyAuditor()

    # 1. Hardened posture
    hardened = {
        "defender_realtime_protection": True,
        "firewall_profiles": {"Domain": True, "Private": True, "Public": True},
        "uac_enabled": True,
        "running_as_admin": False,
    }
    res_h = auditor.audit_security_posture(hardened)
    assert res_h["posture_score"] == 100.0
    assert len(res_h["compliance_violations"]) == 0

    # 2. Weak posture
    weak = {
        "defender_realtime_protection": False,
        "firewall_profiles": {"Domain": True, "Private": False, "Public": False},
        "uac_enabled": False,
        "running_as_admin": True,
    }
    res_w = auditor.audit_security_posture(weak)
    assert res_w["posture_score"] < 50.0
    assert len(res_w["compliance_violations"]) >= 4


@pytest.mark.asyncio
async def test_cybersecurity_expert_planner_full_lifecycle():
    """Verify CybersecurityExpertPlanner assesses, plans, and explains without executing."""
    expert = CybersecurityExpertPlanner()
    goal = "Perform vulnerability scan for CVEs and audit exposed credentials in repository"

    can_handle, conf, rationale = expert.can_handle(goal)
    assert can_handle is True
    assert conf >= 0.85

    assessment = await expert.assess(goal, context={"causal_context": {"event_id": "evt_sec_01"}})
    assert isinstance(assessment, DomainAssessment)
    assert assessment.domain == "cybersecurity"
    assert assessment.causal_context["event_id"] == "evt_sec_01"
    assert "security.credential_scan" in assessment.required_capabilities

    plan = await expert.generate_plan(goal, assessment)
    assert isinstance(plan, PlanDAG)
    assert len(plan.nodes) >= 4
    assert len(plan.execution_stages) >= 2

    # Validation against capability registry
    val_res = expert.validate_plan(plan, CapabilityRegistry.get_instance())
    assert val_res.valid is True

    explanation = expert.explain_plan(plan, assessment)
    assert "CYBERSECURITY" in explanation
    assert plan.plan_id in explanation


@pytest.mark.asyncio
async def test_cybersecurity_expert_no_critical_or_remediation_actions():
    """
    Verify CybersecurityExpertPlanner only schedules observational audit capabilities during standard planning.
    
    Observational audit nodes may include ActionRisk.HIGH (e.g. security.credential_scan which inspects
    sensitive private keys/tokens and requires human confirmation under ASSISTED autonomy),
    but must NEVER schedule ActionRisk.CRITICAL operations or mutating 'remediate' capabilities.
    """
    expert = CybersecurityExpertPlanner()
    goal = "Audit attack surface, open ports, and Windows Defender compliance"

    assessment = await expert.assess(goal)
    plan = await expert.generate_plan(goal, assessment)

    # Invariant: Every node must be strictly observational (never CRITICAL, never remediation)
    for nid, node in plan.nodes.items():
        assert node.risk_level in (ActionRisk.LOW, ActionRisk.HIGH), f"Node {nid} has unexpected risk {node.risk_level}"
        assert node.risk_level != ActionRisk.CRITICAL, f"Node {nid} cannot be CRITICAL in audit plan"
        assert "remediate" not in node.capability, f"Node {nid} cannot be a remediation action in audit plan"


@pytest.mark.asyncio
async def test_router_integration_with_cybersecurity_expert():
    """Verify ExpertDomainRouter automatically discovers and routes security tasks to CybersecurityExpertPlanner."""
    ExpertDomainRouter.reset_instance()
    router = ExpertDomainRouter.get_instance()

    goal = "Audit CVE vulnerabilities in dependencies and check for leaked API keys"
    expert, assessment, rationale = await router.route(goal)

    assert expert is not None
    assert expert.domain == "cybersecurity"
    assert assessment is not None
    assert assessment.domain == "cybersecurity"
    assert assessment.confidence >= 0.85
    assert "cybersecurity" in rationale.lower()
