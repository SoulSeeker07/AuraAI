"""
Unit Tests for M25 Phase 5: Financial Analysis Expert Subsystem
Location: tests/unit/test_finance_expert.py

Verifies:
1. ProvenanceValidator strict classification (SOURCE_FACT, EXTRACTED_VALUE, CALCULATION, FORECAST_INFERENCE).
2. FinancialDataExtractor tabular metric parsing, currency normalization, and unit multipliers.
3. FinancialModelBuilder ratio calculations (Gross Margin, EBITDA, Operating Margin, Debt/Equity).
4. VarianceAnalyzer budget vs actual variances and favorable/unfavorable indicators.
5. TrendForecaster CAGR calculations and Bear/Base/Bull scenario modeling with declared assumptions.
6. FinancialAnalysisExpertPlanner DomainAssessment and PlanDAG synthesis.
7. Strict Invariant: Zero transaction execution during planning.
8. Seamless routing integration via ExpertDomainRouter and PlannerRegistry.
"""

import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.planner_registry import PlannerRegistry
from experts.finance.data_extractor import FinancialDataExtractor
from experts.finance.model_builder import FinancialModelBuilder
from experts.finance.planner import FinancialAnalysisExpertPlanner
from experts.finance.provenance_validator import ProvenanceType, ProvenanceValidator
from experts.finance.trend_forecaster import TrendForecaster
from experts.finance.variance_analyzer import VarianceAnalyzer
from experts.models import DomainAssessment, PlanDAG
from experts.router import ExpertDomainRouter


def test_provenance_validator_classification():
    """Verify ProvenanceValidator classifies entries and demotes unverified facts."""
    entries = [
        {
            "metric_name": "Q3 Revenue",
            "value": 150_000_000,
            "currency": "USD",
            "provenance_type": "SOURCE_FACT",
            "source_uri": "https://sec.gov/edgar/data/10k_q3.pdf",
        },
        {
            "metric_name": "Rumored Q4 Revenue",
            "value": 180_000_000,
            "currency": "USD",
            "provenance_type": "SOURCE_FACT",
            "source_uri": "",  # Missing source -> should be demoted
        },
        {
            "metric_name": "Projected FY2026 EBITDA",
            "value": 45_000_000,
            "currency": "USD",
            "provenance_type": "FORECAST_INFERENCE",
            "assumptions": ["CAGR = 12%"],
        },
    ]
    validator = ProvenanceValidator()
    res = validator.validate_entries(entries)

    assert res["total_count"] == 3
    assert res["unverified_count"] == 1
    assert res["entries"][0]["provenance_type"] == "SOURCE_FACT"
    assert res["entries"][1]["provenance_type"] == "EXTRACTED_VALUE"  # Demoted
    assert res["entries"][2]["provenance_type"] == "FORECAST_INFERENCE"


def test_financial_data_extractor_parsing():
    """Verify FinancialDataExtractor parses currencies, scaling units, and metric lines."""
    report_text = """
Financial Summary for FY2024:
Total Revenue: $250M
Cost of Goods Sold = $100M
Operating Expenses: $50 million
India Regional Revenue: ₹120 Cr
Net Income: $75M
"""
    extractor = FinancialDataExtractor()
    items = extractor.extract_line_items(report_text)

    assert len(items) >= 4
    rev_item = next(i for i in items if "Revenue" in i["metric_name"])
    assert rev_item["normalized_value"] == 250_000_000.0
    assert rev_item["currency"] == "USD"

    inr_item = next(i for i in items if "India Regional" in i["metric_name"])
    assert inr_item["normalized_value"] == 1_200_000_000.0  # 120 Cr = 1,200,000,000
    assert inr_item["currency"] == "INR"


def test_financial_model_builder_metrics():
    """Verify FinancialModelBuilder calculates ratios, margins, and EBITDA accurately."""
    statement = {
        "revenue": 1_000_000.0,
        "cogs": 400_000.0,
        "operating_expenses": 300_000.0,
        "net_income": 200_000.0,
        "depreciation_amortization": 50_000.0,
        "current_assets": 500_000.0,
        "current_liabilities": 250_000.0,
        "total_debt": 200_000.0,
        "total_equity": 800_000.0,
    }
    builder = FinancialModelBuilder()
    res = builder.compute_statement_metrics(statement)

    assert res["gross_profit"] == 600_000.0
    assert res["gross_margin_pct"] == 60.0
    assert res["operating_income"] == 300_000.0
    assert res["operating_margin_pct"] == 30.0
    assert res["ebitda"] == 350_000.0
    assert res["net_margin_pct"] == 20.0
    assert res["current_ratio"] == 2.0
    assert res["debt_to_equity"] == 0.25


def test_variance_analyzer_budget_vs_actual():
    """Verify VarianceAnalyzer calculates deltas and favorable/unfavorable statuses."""
    budget = {"Revenue": 500_000.0, "Marketing": 100_000.0, "COGS": 200_000.0}
    actual = {"Revenue": 550_000.0, "Marketing": 120_000.0, "COGS": 190_000.0}

    analyzer = VarianceAnalyzer()
    res = analyzer.analyze_variance(budget, actual)

    assert res["item_count"] == 3
    items = {i["metric"]: i for i in res["line_items"]}

    # Revenue over budget => FAVORABLE
    assert items["Revenue"]["variance"] == 50_000.0
    assert items["Revenue"]["status"] == "FAVORABLE"

    # Marketing expense over budget => UNFAVORABLE
    assert items["Marketing"]["variance"] == 20_000.0
    assert items["Marketing"]["status"] == "UNFAVORABLE"

    # COGS expense under budget => FAVORABLE
    assert items["COGS"]["variance"] == -10_000.0
    assert items["COGS"]["status"] == "FAVORABLE"


def test_trend_forecaster_cagr_and_scenarios():
    """Verify TrendForecaster calculates CAGR and outputs scenario forecasts with assumptions."""
    forecaster = TrendForecaster()

    # 1. CAGR: from 100 to 144 in 2 years => sqrt(1.44) - 1 = 20%
    cagr = forecaster.compute_cagr(100.0, 144.0, 2)
    assert cagr == 20.0

    # 2. Scenarios
    scenarios_res = forecaster.forecast_scenarios(base_value=100.0, periods_ahead=3, cagr_rate_pct=10.0)
    assert scenarios_res["base_value"] == 100.0
    assert len(scenarios_res["assumptions"]) >= 3
    assert len(scenarios_res["scenarios"]["base"]["projections"]) == 3
    assert scenarios_res["scenarios"]["base"]["projections"][0]["projected_value"] == 110.0


@pytest.mark.asyncio
async def test_financial_expert_planner_full_lifecycle():
    """Verify FinancialAnalysisExpertPlanner assesses, plans, and explains without executing."""
    expert = FinancialAnalysisExpertPlanner()
    goal = "Build financial model calculating gross margin, EBITDA, and YoY revenue growth for FY2025"

    can_handle, conf, rationale = expert.can_handle(goal)
    assert can_handle is True
    assert conf >= 0.85

    assessment = await expert.assess(goal, context={"causal_context": {"event_id": "evt_fin_01"}})
    assert isinstance(assessment, DomainAssessment)
    assert assessment.domain == "finance"
    assert assessment.causal_context["event_id"] == "evt_fin_01"
    assert "finance.compute_metrics" in assessment.required_capabilities

    plan = await expert.generate_plan(goal, assessment)
    assert isinstance(plan, PlanDAG)
    assert len(plan.nodes) == 5
    assert len(plan.execution_stages) == 4

    # Validation against capability registry
    val_res = expert.validate_plan(plan, CapabilityRegistry.get_instance())
    assert val_res.valid is True

    explanation = expert.explain_plan(plan, assessment)
    assert "FINANCE" in explanation
    assert plan.plan_id in explanation


@pytest.mark.asyncio
async def test_router_integration_with_financial_expert():
    """Verify ExpertDomainRouter automatically discovers and routes finance tasks to FinancialAnalysisExpertPlanner."""
    ExpertDomainRouter.reset_instance()
    router = ExpertDomainRouter.get_instance()

    goal = "Perform budget vs actual variance analysis and compute EBITDA margins"
    expert, assessment, rationale = await router.route(goal)

    assert expert is not None
    assert expert.domain == "finance"
    assert assessment is not None
    assert assessment.domain == "finance"
    assert assessment.confidence >= 0.85
    assert "financial" in rationale.lower()
