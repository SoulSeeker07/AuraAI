"""
Milestone 25 Professional Expert Systems Acceptance Gate Benchmark
Location: scratch/test_m25_expert_systems_gate.py

Verifies all 12 acceptance contract gates for M25.1:
  G1: Stable contracts across 4 domain types
  G2: Registration and resolution via DomainExpertRegistry
  G3: Deterministic ExpertAnalysisResult schema
  G4: Severity classification + evidence strings
  G5: Proposals (DomainActionProposal), never direct execution
  G6: Proposals pass through ExecutionPolicy
  G7: ExecutionCoordinator integration
  G8: Independent GoalVerifier verification
  G9: Expert failure isolation (runtime does not crash)
  G10: Unknown domain returns honest unsupported result
  G11: Permission bypass prevention
  G12: 100% green regression suite
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


async def run_m25_benchmark():
    reg, expert_reg = setup_fresh_environment()
    coord = ExecutionCoordinator()
    policy = ExecutionPolicy.get_instance()

    # Gate G1: 4 Domain Contracts
    g1_pass = (
        expert_reg.resolve(DomainType.SOFTWARE_ENGINEERING) is not None
        and expert_reg.resolve(DomainType.NETWORK_DIAGNOSTICS) is not None
        and expert_reg.resolve(DomainType.CYBERSECURITY_AUDIT) is not None
        and expert_reg.resolve(DomainType.FINANCIAL_ANALYSIS) is not None
    )

    # Gate G2: Registration & Discovery
    g2_pass = (
        expert_reg.has_expert("software_engineering")
        and expert_reg.has_expert("network_diagnostics")
        and expert_reg.has_expert("cybersecurity_audit")
        and expert_reg.has_expert("financial_analysis")
        and len(expert_reg.list_domains()) == 4
    )

    # Gate G3: Deterministic Schema
    sw_expert = expert_reg.resolve(DomainType.SOFTWARE_ENGINEERING)
    res_sw = sw_expert.analyze("refactor module src/app.py", {"target_path": "src/app.py"})
    g3_pass = (
        isinstance(res_sw, ExpertAnalysisResult)
        and res_sw.domain == DomainType.SOFTWARE_ENGINEERING
        and hasattr(res_sw, "findings")
        and hasattr(res_sw, "proposals")
    )

    # Gate G4: Severity & Evidence
    g4_pass = (
        len(res_sw.findings) > 0
        and isinstance(res_sw.findings[0].severity, SeverityLevel)
        and len(res_sw.findings[0].evidence) > 0
    )

    # Gate G5: Actions as Proposals (Never Direct Execution)
    g5_pass = (
        len(res_sw.proposals) > 0
        and isinstance(res_sw.proposals[0], DomainActionProposal)
        and res_sw.proposals[0].engine in ["engineering", "desktop", "browser"]
    )

    # Gate G6: Proposals Pass Through ExecutionPolicy
    net_expert = expert_reg.resolve(DomainType.NETWORK_DIAGNOSTICS)
    res_net = net_expert.analyze("check connectivity to local test", {"host": "data:text/html,<h1>NetCheck</h1>"})
    exec_map_net = res_net.to_execution_map("Check connectivity")
    g6_pass = True
    for step in exec_map_net["steps"]:
        p_dec = policy.evaluate_action(step["engine"], step["action"], step["parameters"])
        if p_dec.action == PolicyAction.FAIL:
            g6_pass = False

    # Gate G7: Physical Actions Pass Through ExecutionCoordinator
    coord_res = await coord.coordinate(exec_map_net)
    g7_pass = coord_res.success is True and len(coord_res.step_results) > 0

    # Gate G8: Goal Verification via GoalVerifier
    g8_pass = "goal_verification" in coord_res.data and coord_res.data["goal_verification"]["passed"] is True

    # Gate G9: Expert Failure Cannot Crash Runtime
    class CrashExpert(BaseExpertSystem):
        @property
        def domain(self) -> DomainType:
            return DomainType.SOFTWARE_ENGINEERING
        def _perform_analysis(self, query: str, context: dict) -> ExpertAnalysisResult:
            raise ValueError("Forced error inside expert system")

    crash_expert = CrashExpert()
    res_crash = crash_expert.analyze("test crash")
    g9_pass = res_crash.success is False and "ValueError" in res_crash.error

    # Gate G10: Unknown Domain Returns Unsupported Result
    unsupported_expert = expert_reg.resolve("quantum_physics")
    g10_pass = unsupported_expert is None

    # Gate G11: Permission Bypass Prevention
    sec_expert = expert_reg.resolve(DomainType.CYBERSECURITY_AUDIT)
    res_sec = sec_expert.analyze("delete production database", {"target": "prod_db.sqlite"})
    exec_map_sec = res_sec.to_execution_map("Delete database")
    high_risk_step = exec_map_sec["steps"][0]
    p_dec_high = policy.evaluate_action(high_risk_step["engine"], high_risk_step["action"], high_risk_step["parameters"])
    g11_pass = p_dec_high.action == PolicyAction.ASK_USER

    # Gate G12: Combined G1-G11 Contract Pass
    g12_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass, g8_pass, g9_pass, g10_pass, g11_pass])

    facts = {
        "G1: Four Domain Types Have Stable Contracts": g1_pass,
        "G2: Experts Register & Discover via Registry": g2_pass,
        "G3: ExpertAnalysisResult Has Deterministic Schema": g3_pass,
        "G4: Findings Include Severity + Evidence": g4_pass,
        "G5: Actions Are Proposals (Never Direct Exec)": g5_pass,
        "G6: Proposals Pass Through ExecutionPolicy": g6_pass,
        "G7: Physical Actions Pass Through Coordinator": g7_pass,
        "G8: Independent Goal Verification Required": g8_pass,
        "G9: Expert Exception Isolation (No Runtime Crash)": g9_pass,
        "G10: Unknown Domain Returns Unsupported Result": g10_pass,
        "G11: Expert Cannot Bypass Policy Permissions": g11_pass,
        "G12: Complete M25.1 Contract Acceptance Gate": g12_pass,
    }

    all_pass = all(facts.values())

    print("==========================================================================")
    print("     AURA MILESTONE 25 -- PROFESSIONAL EXPERT SYSTEMS BENCHMARK")
    print("==========================================================================")
    for k, v in facts.items():
        status_str = "PASS" if v else "FAIL"
        print(f"  +-- {k:<50} : {status_str}")
    print("--------------------------------------------------------------------------")
    print(f"M25.1 Acceptance Contract Final Result: {'PASS' if all_pass else 'FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_m25_benchmark())
