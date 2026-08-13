"""
Milestone 25.4 Cybersecurity Audit Expert Acceptance Benchmark
Location: scratch/test_m25_4_security_expert_gate.py

Verifies all 12 M25.4 acceptance gates:
  G1: Real Filesystem Permission Audit (os.access / stat mode)
  G2: Sensitive-File Detection (.env, keys, unencrypted secret artifacts)
  G3: Process / Privilege Inspection (Admin privileges & PID)
  G4: Listening / Open-Port Audit (Local bound sockets)
  G5: Security Posture Scoring (Calculated score out of 100.0%)
  G6: Evidence-backed Findings Schema
  G7: Severity + Confidence + Location Schema
  G8: Remediation Proposals Only (DomainActionProposal, never direct mutation)
  G9: High-Risk Actions Blocked by Policy (file.delete -> ASK_USER)
  G10: Coordinator + Independent Verification Integration
  G11: Honest Handling of Inaccessible Data (INSPECTION_UNAVAILABLE)
  G12: Complete Real-Machine Acceptance Gate
"""

import asyncio
import os
import sys
from pathlib import Path

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
    sec_expert = CybersecurityAuditExpert()
    expert_reg.register(SoftwareEngineeringExpert())
    expert_reg.register(NetworkDiagnosticsExpert())
    expert_reg.register(sec_expert)
    expert_reg.register(FinancialAnalysisExpert())
    return reg, expert_reg, sec_expert


async def run_m25_4_benchmark():
    reg, expert_reg, sec_expert = setup_fresh_environment()
    coord = ExecutionCoordinator()
    policy = ExecutionPolicy.get_instance()

    workspace_path = str(Path("src/experts").resolve())
    analysis = sec_expert.analyze("audit filesystem permissions, secrets, and security posture", {"target_path": workspace_path})

    # Gate G1: Real Filesystem Permission Audit
    perm_findings = [f for f in analysis.findings if f.category == "filesystem_permissions"]
    g1_pass = len(perm_findings) > 0 and "Mode:" in str(perm_findings[0].evidence)

    # Gate G2: Sensitive-File Detection
    sec_findings = [f for f in analysis.findings if f.category == "sensitive_file_detection"]
    g2_pass = len(sec_findings) > 0

    # Gate G3: Process / Privilege Inspection
    priv_findings = [f for f in analysis.findings if f.category == "process_privileges"]
    g3_pass = len(priv_findings) > 0 and "Is Admin" in str(priv_findings[0].evidence)

    # Gate G4: Listening / Open-Port Audit
    port_findings = [f for f in analysis.findings if f.category == "open_port_audit"]
    g4_pass = len(port_findings) > 0

    # Gate G5: Security Posture Scoring
    posture_findings = [f for f in analysis.findings if f.category == "security_posture"]
    g5_pass = len(posture_findings) > 0 and analysis.data.get("posture_score", -1.0) >= 0.0

    # Gate G6: Evidence-backed Findings Schema
    g6_pass = all(len(f.evidence) > 0 for f in analysis.findings)

    # Gate G7: Severity + Confidence + Location
    g7_pass = all(
        isinstance(f.severity, SeverityLevel)
        and f.confidence > 0.4
        and len(f.location) > 0
        for f in analysis.findings
    )

    # Gate G8: Remediation Proposals Only (Never Direct Execution)
    g8_pass = len(analysis.proposals) > 0 and all(isinstance(p, DomainActionProposal) for p in analysis.proposals)

    # Gate G9: High-Risk Actions Blocked by Policy
    analysis_high = sec_expert.analyze("purge protected file", {"target_path": workspace_path, "target": "protected.key"})
    high_proposal = [p for p in analysis_high.proposals if p.risk_level == "high"][0]
    p_dec = policy.evaluate_action(high_proposal.engine, high_proposal.action, high_proposal.parameters)
    g9_pass = p_dec.action == PolicyAction.ASK_USER

    # Gate G10: Coordinator + Independent Verification Integration
    exec_map = analysis.to_execution_map("Generate security posture report")
    coord_res = await coord.coordinate(exec_map)
    g10_pass = coord_res.success is True and "goal_verification" in coord_res.data and coord_res.data["goal_verification"]["passed"] is True

    # Gate G11: Honest Handling of Inaccessible Data (INSPECTION_UNAVAILABLE)
    res_inaccess = sec_expert.analyze("audit non_existent_folder_12345", {"target_path": "non_existent_folder_12345"})
    inaccess_finding = [f for f in res_inaccess.findings if f.category == "filesystem_permissions"][0]
    g11_pass = "INSPECTION_UNAVAILABLE" in str(inaccess_finding.evidence) and inaccess_finding.confidence == 0.50

    # Gate G12: Complete Real-Machine Acceptance Gate
    g12_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass, g8_pass, g9_pass, g10_pass, g11_pass])

    facts = {
        "G1: Real Filesystem Permission Audit (os.access / stat mode)": g1_pass,
        "G2: Sensitive-File Detection (.env, keys, unencrypted secrets)": g2_pass,
        "G3: Process / Privilege Inspection (Admin privileges & PID)": g3_pass,
        "G4: Listening / Open-Port Audit (Local bound sockets)": g4_pass,
        "G5: Security Posture Scoring (Calculated score out of 100.0%)": g5_pass,
        "G6: Evidence-Backed Findings Schema": g6_pass,
        "G7: Severity + Confidence + Location Schema": g7_pass,
        "G8: Remediation Proposals Only (DomainActionProposal)": g8_pass,
        "G9: High-Risk Actions Blocked by Policy (ASK_USER)": g9_pass,
        "G10: Coordinator + Independent Verification Integration": g10_pass,
        "G11: Honest Handling of Inaccessible Data (INSPECTION_UNAVAILABLE)": g11_pass,
        "G12: Complete Real-Machine Acceptance Gate": g12_pass,
    }

    all_pass = all(facts.values())

    print("==========================================================================")
    print("     AURA MILESTONE 25.4 -- CYBERSECURITY AUDIT EXPERT BENCHMARK")
    print("==========================================================================")
    for k, v in facts.items():
        status_str = "PASS" if v else "FAIL"
        print(f"  +-- {k:<68} : {status_str}")
    print("--------------------------------------------------------------------------")
    print(f"M25.4 Acceptance Contract Final Result: {'PASS' if all_pass else 'FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_m25_4_benchmark())
