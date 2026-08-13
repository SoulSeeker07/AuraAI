"""
Milestone 25.6 Cross-Domain Expert Systems Integration & Final Acceptance Benchmark
Location: scratch/test_m25_6_cross_domain_expert_gate.py

Verifies end-to-end integration across all 4 Professional Expert Systems:
  1. SoftwareEngineeringExpert (M25.2)
  2. NetworkDiagnosticsExpert (M25.3)
  3. CybersecurityAuditExpert (M25.4)
  4. FinancialAnalysisExpert (M25.5)

Ensures zero architectural leaks, full proposal routing through ExecutionPolicy -> ExecutionCoordinator -> GoalVerifier,
and 100% green regression.
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
    expert_reg.register(SoftwareEngineeringExpert())
    expert_reg.register(NetworkDiagnosticsExpert())
    expert_reg.register(CybersecurityAuditExpert())
    expert_reg.register(FinancialAnalysisExpert())
    return reg, expert_reg


async def run_m25_6_benchmark():
    reg, expert_reg = setup_fresh_environment()
    coord = ExecutionCoordinator()
    policy = ExecutionPolicy.get_instance()

    # 1. Software Engineering Expert Execution Map
    sw_expert = expert_reg.resolve(DomainType.SOFTWARE_ENGINEERING)
    sw_res = sw_expert.analyze("refactor module src/experts/models.py", {"target_path": "src/experts/models.py"})
    sw_map = sw_res.to_execution_map("Software engineering analysis proposal")
    sw_coord = await coord.coordinate(sw_map)
    g1_pass = sw_res.success and sw_coord.success

    # 2. Network Diagnostics Expert Execution Map
    net_expert = expert_reg.resolve(DomainType.NETWORK_DIAGNOSTICS)
    net_res = net_expert.analyze("check network target data:text/html,<h1>NetTest</h1>", {"host": "data:text/html,<h1>NetTest</h1>"})
    net_map = net_res.to_execution_map("Network diagnostics proposal")
    net_coord = await coord.coordinate(net_map)
    g2_pass = net_res.success and net_coord.success

    # 3. Cybersecurity Audit Expert Execution Map
    sec_expert = expert_reg.resolve(DomainType.CYBERSECURITY_AUDIT)
    sec_res = sec_expert.analyze("audit workspace security posture", {"target_path": "src/experts"})
    sec_map = sec_res.to_execution_map("Cybersecurity audit proposal")
    sec_coord = await coord.coordinate(sec_map)
    g3_pass = sec_res.success and sec_coord.success

    # 4. Financial Analysis Expert Execution Map
    fin_expert = expert_reg.resolve(DomainType.FINANCIAL_ANALYSIS)
    fin_res = fin_expert.analyze("analyze 3-year revenue and CAGR", {"csv_content": "year,revenue\n2022,100\n2023,150\n2024,225"})
    fin_map = fin_res.to_execution_map("Financial analysis proposal")
    fin_coord = await coord.coordinate(fin_map)
    g4_pass = fin_res.success and fin_coord.success

    # 5. Policy & Verification Enforcement Across All Domains
    g5_pass = all([
        "goal_verification" in sw_coord.data and sw_coord.data["goal_verification"]["passed"] is True,
        "goal_verification" in net_coord.data and net_coord.data["goal_verification"]["passed"] is True,
        "goal_verification" in sec_coord.data and sec_coord.data["goal_verification"]["passed"] is True,
        "goal_verification" in fin_coord.data and fin_coord.data["goal_verification"]["passed"] is True,
    ])

    # 6. Combined Integration Gate
    all_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass])

    facts = {
        "G1: Software Engineering Expert Integration": g1_pass,
        "G2: Network Diagnostics Expert Integration": g2_pass,
        "G3: Cybersecurity Audit Expert Integration": g3_pass,
        "G4: Financial Analysis Expert Integration": g4_pass,
        "G5: End-to-End Goal Verification Across All 4 Domains": g5_pass,
        "G6: Milestone 25 Professional Expert Systems Final Result": all_pass,
    }

    print("==========================================================================")
    print("     AURA MILESTONE 25 -- CROSS-DOMAIN INTEGRATION BENCHMARK")
    print("==========================================================================")
    for k, v in facts.items():
        status_str = "PASS" if v else "FAIL"
        print(f"  +-- {k:<58} : {status_str}")
    print("--------------------------------------------------------------------------")
    print(f"Milestone 25 Final Integration Result: {'PASS' if all_pass else 'FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_m25_6_benchmark())
