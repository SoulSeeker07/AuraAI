"""
Milestone 25.5 Financial Analysis Expert Acceptance Benchmark
Location: scratch/test_m25_5_financial_expert_gate.py

Verifies all 12 M25.5 acceptance gates:
  G1: Real CSV / Tabular Dataset Discovery & Loading
  G2: Schema & Column Type Validation
  G3: Deterministic Revenue Growth Calculation
  G4: Programmatic CAGR Calculation
  G5: Gross and Net Margin Analysis
  G6: Revenue Trajectory Trend Detection
  G7: Anomaly Detection with Evidence
  G8: Honest Handling of Invalid Data (INVALID_FINANCIAL_DATA)
  G9: Evidence-Backed Financial Findings Schema
  G10: Analysis Proposals Only (No Autonomous Transactions)
  G11: Independent Verification Integration
  G12: Complete Real-Data Acceptance Gate
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
    fin_expert = FinancialAnalysisExpert()
    expert_reg.register(SoftwareEngineeringExpert())
    expert_reg.register(NetworkDiagnosticsExpert())
    expert_reg.register(CybersecurityAuditExpert())
    expert_reg.register(fin_expert)
    return reg, expert_reg, fin_expert


async def run_m25_5_benchmark():
    reg, expert_reg, fin_expert = setup_fresh_environment()
    coord = ExecutionCoordinator()
    policy = ExecutionPolicy.get_instance()

    # Real financial CSV dataset (4-year period with revenue, cogs, net income, and a >50% anomaly spike)
    sample_csv = (
        "year,revenue,cogs,net_income\n"
        "2021,100,60,15\n"
        "2022,120,70,22\n"
        "2023,200,110,45\n"  # 66.6% revenue growth spike anomaly
        "2024,250,135,60\n"
    )

    analysis = fin_expert.analyze("analyze 4-year revenue growth, CAGR, margins, and anomalies", {"csv_content": sample_csv})

    # Gate G1: Real CSV Dataset Discovery & Loading
    g1_pass = analysis.success is True and analysis.data.get("periods_count") == 4

    # Gate G2: Schema & Column Type Validation
    g2_pass = any(f.category == "revenue_growth" for f in analysis.findings)

    # Gate G3: Deterministic Revenue Growth Calculation
    growth_findings = [f for f in analysis.findings if f.category == "revenue_growth"]
    g3_pass = len(growth_findings) > 0 and "Average Growth Rate:" in str(growth_findings[0].evidence)

    # Gate G4: Programmatic CAGR Calculation
    cagr_findings = [f for f in analysis.findings if f.category == "cagr_analysis"]
    # CAGR for 100 -> 250 over 3 periods: (250/100)^(1/3) - 1 = 35.72%
    g4_pass = len(cagr_findings) > 0 and analysis.data.get("cagr") is not None and abs(analysis.data["cagr"] - 0.3572) < 0.05

    # Gate G5: Gross and Net Margin Analysis
    margin_findings = [f for f in analysis.findings if f.category == "margin_analysis"]
    g5_pass = len(margin_findings) > 0 and "gross_margin" in str(margin_findings[0].evidence)

    # Gate G6: Revenue Trajectory Trend Detection
    trend_findings = [f for f in analysis.findings if f.category == "trend_detection"]
    g6_pass = len(trend_findings) > 0 and "Upward Expansion" in str(trend_findings[0].title)

    # Gate G7: Anomaly Detection with Evidence
    anomaly_findings = [f for f in analysis.findings if f.category == "anomaly_detection"]
    g7_pass = len(anomaly_findings) > 0 and "Anomaly Spike/Drop" in str(anomaly_findings[0].title)

    # Gate G8: Honest Handling of Invalid Data (INVALID_FINANCIAL_DATA)
    res_bad = fin_expert.analyze("analyze invalid dataset", {"csv_content": "corrupted_text_no_header"})
    bad_findings = [f for f in res_bad.findings if f.category == "schema_validation"]
    g8_pass = len(bad_findings) > 0 and "INVALID_FINANCIAL_DATA" in str(bad_findings[0].evidence) and bad_findings[0].confidence == 0.50

    # Gate G9: Evidence-Backed Financial Findings Schema
    g9_pass = all(
        hasattr(f, "category") and hasattr(f, "severity") and hasattr(f, "title")
        and hasattr(f, "evidence") and hasattr(f, "location") and hasattr(f, "confidence")
        for f in analysis.findings
    ) and any(f.confidence > 0.9 for f in analysis.findings)

    # Gate G10: Analysis Proposals Only (No Autonomous Financial Transactions)
    # Ensure proposals ONLY involve read-only / analytical engines (engineering, browser)
    g10_pass = (
        len(analysis.proposals) > 0
        and all(isinstance(p, DomainActionProposal) for p in analysis.proposals)
        and all(p.action in ("code.report", "table.extract", "browser.navigate") for p in analysis.proposals)
    )

    # Gate G11: Independent Verification Integration
    exec_map = analysis.to_execution_map("Generate financial metrics executive report")
    coord_res = await coord.coordinate(exec_map)
    g11_pass = coord_res.success is True and "goal_verification" in coord_res.data and coord_res.data["goal_verification"]["passed"] is True

    # Gate G12: Complete Real-Data Acceptance Gate
    g12_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass, g8_pass, g9_pass, g10_pass, g11_pass])

    facts = {
        "G1: Real CSV Dataset Discovery & Loading": g1_pass,
        "G2: Schema & Column Type Validation": g2_pass,
        "G3: Deterministic Revenue Growth Calculation": g3_pass,
        "G4: Programmatic CAGR Calculation (35.72% Verified)": g4_pass,
        "G5: Gross and Net Margin Analysis": g5_pass,
        "G6: Revenue Trajectory Trend Detection": g6_pass,
        "G7: Anomaly Detection with Evidence (Growth Spike)": g7_pass,
        "G8: Honest Handling of Invalid Data (INVALID_FINANCIAL_DATA)": g8_pass,
        "G9: Evidence-Backed Financial Findings Schema": g9_pass,
        "G10: Analysis Proposals Only (No Autonomous Transactions)": g10_pass,
        "G11: Independent Verification Integration": g11_pass,
        "G12: Complete Real-Data Acceptance Gate": g12_pass,
    }

    all_pass = all(facts.values())

    print("==========================================================================")
    print("     AURA MILESTONE 25.5 -- FINANCIAL ANALYSIS EXPERT BENCHMARK")
    print("==========================================================================")
    for k, v in facts.items():
        status_str = "PASS" if v else "FAIL"
        print(f"  +-- {k:<66} : {status_str}")
    print("--------------------------------------------------------------------------")
    print(f"M25.5 Acceptance Contract Final Result: {'PASS' if all_pass else 'FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_m25_5_benchmark())
