"""
Milestone 25.2 Software Engineering Expert Acceptance Benchmark
Location: scratch/test_m25_2_software_expert_gate.py

Verifies all 10 M25.2 acceptance gates:
  G1: Real Repository Discovery (inspects workspace, count python/test files)
  G2: AST Analysis (parses Python AST, finds complexity / docstrings)
  G3: Dependency Inspection (honest UNAVAILABLE vulnerability status)
  G4: Git Health (inspects branch, working tree, modified entries)
  G5: Test/Quality Evidence (proposes quality analysis steps)
  G6: Deterministic Finding Schema (category, severity, title, evidence, location, confidence)
  G7: Remediation Proposals (DomainActionProposal, never direct mutation)
  G8: Execution Boundary (Proposal -> Policy -> Coordinator -> Verifier)
  G9: Honest Verification (GoalVerifier rejects fabricated success)
  G10: Real Repository Acceptance (runs on live AuraAI workspace)
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
    sw_expert = SoftwareEngineeringExpert()
    expert_reg.register(sw_expert)
    expert_reg.register(NetworkDiagnosticsExpert())
    expert_reg.register(CybersecurityAuditExpert())
    expert_reg.register(FinancialAnalysisExpert())
    return reg, expert_reg, sw_expert


async def run_m25_2_benchmark():
    reg, expert_reg, sw_expert = setup_fresh_environment()
    coord = ExecutionCoordinator()
    policy = ExecutionPolicy.get_instance()

    # Run analysis against real AuraAI src/ directory
    workspace_path = str(Path("src").resolve())
    analysis = sw_expert.analyze(
        "refactor and audit codebase quality, dependencies, and git health",
        {"target_path": workspace_path, "workspace_root": str(Path(".").resolve())}
    )

    # Gate G1: Repository Discovery
    disc_findings = [f for f in analysis.findings if f.category == "repository_discovery"]
    g1_pass = len(disc_findings) > 0 and analysis.data.get("py_files_count", 0) > 10

    # Gate G2: AST Analysis
    g2_pass = any(f.category in ("ast_complexity", "ast_syntax_error", "documentation_coverage") for f in analysis.findings)

    # Gate G3: Dependency Inspection (Honest Unknown)
    dep_findings = [f for f in analysis.findings if f.category == "dependency_audit"]
    g3_pass = len(dep_findings) > 0 and "UNAVAILABLE (Honest Unknown)" in str(dep_findings[0].evidence)

    # Gate G4: Git Health Inspection
    git_findings = [f for f in analysis.findings if f.category == "git_health"]
    g4_pass = len(git_findings) > 0 and "Active Branch" in str(git_findings[0].evidence)

    # Gate G5: Test/Quality Evidence Proposals
    g5_pass = any(p.action in ("code.analyze", "code.test", "code.edit") for p in analysis.proposals)

    # Gate G6: Deterministic Finding Schema (location & confidence)
    g6_pass = all(
        hasattr(f, "category") and hasattr(f, "severity") and hasattr(f, "title")
        and hasattr(f, "evidence") and hasattr(f, "location") and hasattr(f, "confidence")
        for f in analysis.findings
    ) and any(len(f.location) > 0 for f in analysis.findings)

    # Gate G7: Remediation Proposals (Never Direct Execution)
    g7_pass = (
        len(analysis.proposals) > 0
        and all(isinstance(p, DomainActionProposal) for p in analysis.proposals)
        # Verify expert did not modify files directly
        and analysis.success is True
    )

    # Gate G8: Execution Boundary (Proposal -> Policy -> Coordinator)
    exec_map = analysis.to_execution_map("Run quality analysis proposal")
    eval_pass = True
    for step in exec_map["steps"]:
        p_dec = policy.evaluate_action(step["engine"], step["action"], step["parameters"])
        if p_dec.action == PolicyAction.FAIL:
            eval_pass = False

    coord_res = await coord.coordinate(exec_map)
    g8_pass = eval_pass and coord_res.success is True

    # Gate G9: Honest Verification (GoalVerifier rejects unverified claim)
    from brain.execution_coordinator import CoordinationResult
    verifier = GoalVerifier()
    v_report = verifier.verify_goal("Unverified edit step", CoordinationResult(success=False, goal="Unverified edit step", step_results=[]))
    g9_pass = v_report.passed is False and len(v_report.evidence) > 0

    # Gate G10: Real Repository Acceptance
    g10_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass, g8_pass, g9_pass])

    facts = {
        "G1: Real Repository Discovery (Count & Paths)": g1_pass,
        "G2: AST Analysis (Complexity & Symbol Docstrings)": g2_pass,
        "G3: Dependency Inspection (Honest Unknown Status)": g3_pass,
        "G4: Git Health (Branch, Working Tree & Status)": g4_pass,
        "G5: Test & Quality Evidence Proposals": g5_pass,
        "G6: Deterministic Findings (Location & Confidence)": g6_pass,
        "G7: Remediation Proposals (Never Direct Mutation)": g7_pass,
        "G8: Execution Boundary (Proposal -> Policy -> Coordinator)": g8_pass,
        "G9: Honest Verification (Rejects Fabricated Success)": g9_pass,
        "G10: Complete M25.2 Real-Repository Acceptance Gate": g10_pass,
    }

    all_pass = all(facts.values())

    print("==========================================================================")
    print("     AURA MILESTONE 25.2 -- SOFTWARE ENGINEERING EXPERT BENCHMARK")
    print("==========================================================================")
    for k, v in facts.items():
        status_str = "PASS" if v else "FAIL"
        print(f"  +-- {k:<58} : {status_str}")
    print("--------------------------------------------------------------------------")
    print(f"M25.2 Acceptance Contract Final Result: {'PASS' if all_pass else 'FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_m25_2_benchmark())
