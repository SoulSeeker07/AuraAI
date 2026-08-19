"""
Financial Analysis Expert Planner (M25 Phase 5)
Location: src/experts/finance/planner.py

Specialized domain planner coordinating financial statement modeling, ratio computation,
variance analysis, CAGR forecasting, and provenance-grounded synthesis.

Architectural Invariants:
1. Pure Reasoning: Generates DomainAssessment and PlanDAG data structures.
   Zero direct capability execution, zero financial transaction execution during planning.
2. Provenance Separation: Distinguishes authoritative SOURCE_FACT from CALCULATIONS
   and FORECAST_INFERENCE assumptions.
3. Causal Continuity: Preserves event_id, correlation_id, and assessment_id.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import PlanValidationResult
from core.orchestration.autonomy_mode import ActionRisk
from ..base_expert import DomainExpertPlanner
from ..models import DomainAssessment, PlanDAG, PlanNode
from .data_extractor import FinancialDataExtractor
from .model_builder import FinancialModelBuilder
from .provenance_validator import ProvenanceValidator
from .trend_forecaster import TrendForecaster
from .variance_analyzer import VarianceAnalyzer

logger = logging.getLogger(__name__)


class FinancialAnalysisExpertPlanner(DomainExpertPlanner):
    """
    Professional domain planner for corporate finance, P&L modeling, variance analysis, and forecasting.
    """

    def __init__(
        self,
        data_extractor: FinancialDataExtractor | None = None,
        provenance_validator: ProvenanceValidator | None = None,
        model_builder: FinancialModelBuilder | None = None,
        variance_analyzer: VarianceAnalyzer | None = None,
        trend_forecaster: TrendForecaster | None = None,
    ) -> None:
        self.data_extractor = data_extractor or FinancialDataExtractor()
        self.provenance_validator = provenance_validator or ProvenanceValidator()
        self.model_builder = model_builder or FinancialModelBuilder()
        self.variance_analyzer = variance_analyzer or VarianceAnalyzer()
        self.trend_forecaster = trend_forecaster or TrendForecaster()

    @property
    def domain(self) -> str:
        return "finance"

    @property
    def description(self) -> str:
        return "Specialized expert for financial modeling, P&L analysis, variance decomposition, CAGR trend forecasting, and provenance-grounded reporting."

    @property
    def supported_intents(self) -> list[str]:
        return [
            "finance.model",
            "finance.variance",
            "finance.forecast",
            "finance.valuation",
            "finance.pnl_audit",
        ]

    def can_handle(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, float, str]:
        """
        Evaluates goal text against financial analysis semantic patterns.
        """
        g = goal_text.lower().strip()
        ctx = context or {}

        # Check explicit intent
        intent = ctx.get("intent", "")
        if intent in self.supported_intents:
            return True, 0.98, f"Direct match with supported intent '{intent}'."

        # High-confidence indicators (word-boundary matched)
        high_indicators = [
            r"\bebitda\b", r"\bgross margin\b", r"\bnet income\b", r"\brevenue\b",
            r"\bvariance analysis\b", r"\bbudget vs actual\b", r"\bcagr\b",
            r"\bfinancial model\b", r"\bbalance sheet\b", r"\bcash flow\b",
            r"\bvaluation\b", r"\boperating margin\b", r"\bdebt to equity\b",
            r"\bfinancial forecast\b", r"\byoy growth\b"
        ]
        matched_high = [ind for ind in high_indicators if re.search(ind, g)]
        if matched_high:
            clean_names = [ind.replace(r"\b", "") for ind in matched_high]
            confidence = min(0.96, 0.82 + (0.04 * len(matched_high)))
            return True, confidence, f"Matched financial analysis signals: {', '.join(clean_names)}."

        # Medium-confidence indicators
        med_indicators = [
            r"\bprofit\b", r"\bloss\b", r"\bbudget\b", r"\bexpense\b",
            r"\bforecast\b", r"\bearnings\b", r"\bmargin\b"
        ]
        matched_med = [ind for ind in med_indicators if re.search(ind, g)]
        if matched_med:
            clean_names = [ind.replace(r"\b", "") for ind in matched_med]
            return True, 0.65, f"Matched general financial terms: {', '.join(clean_names)}."

        return False, 0.10, "Goal does not require specialized financial analysis expertise."

    async def assess(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> DomainAssessment:
        """
        Conducts deep financial evaluation and synthesizes findings, assumptions, and strategy.
        """
        ctx = context or {}
        causal = ctx.get("causal_context", {})
        findings: list[str] = []
        assumptions: list[str] = []
        required_caps: list[str] = []

        g = goal_text.lower()

        if any(w in g for w in ["variance", "budget", "actual", "vs"]):
            findings.append("Focus Area: Variance Analysis (Budget vs Actual).")
            required_caps.extend(["finance.extract_tabular", "finance.variance_analysis", "finance.generate_report"])
        elif any(w in g for w in ["forecast", "cagr", "projection", "scenario"]):
            findings.append("Focus Area: Financial Forecasting & Multi-Scenario Projections.")
            required_caps.extend(["finance.extract_tabular", "finance.forecast_model", "finance.generate_report"])
        elif any(w in g for w in ["ratio", "margin", "ebitda", "pnl", "statement"]):
            findings.append("Focus Area: Financial Statement Metrics & Ratio Modeling.")
            required_caps.extend(["finance.extract_tabular", "finance.compute_metrics", "finance.generate_report"])
        else:
            findings.append("Focus Area: Comprehensive Financial Model & Performance Audit.")
            required_caps.extend([
                "finance.extract_tabular",
                "finance.compute_metrics",
                "finance.variance_analysis",
                "finance.forecast_model",
                "finance.generate_report",
            ])

        assumptions.extend([
            "Extracted historical figures retain verified source citations.",
            "Forecasts represent analytical models under declared growth assumptions.",
            "Analysis does NOT constitute automated transaction execution or trading advice.",
        ])

        strategy = (
            "Multi-Tier Financial Modeling: "
            "1. Tabular Extraction -> 2. Metric Computation -> 3. Variance / CAGR Modeling -> "
            "4. Synthesis with Provenance Citations. Zero financial execution."
        )

        return DomainAssessment.create(
            domain=self.domain,
            confidence=0.94,
            findings=findings,
            assumptions=assumptions,
            required_capabilities=list(set(required_caps)),
            recommended_strategy=strategy,
            causal_context=causal,
            metadata={"goal": goal_text},
        )

    async def generate_plan(
        self,
        goal_text: str,
        assessment: DomainAssessment,
        context: dict[str, Any] | None = None,
    ) -> PlanDAG:
        """
        Synthesizes a dependency-ordered PlanDAG for financial modeling and analysis.
        """
        plan = PlanDAG.create(
            domain=self.domain,
            goal=goal_text,
            assessment_id=assessment.assessment_id,
            causal_context=dict(assessment.causal_context),
        )

        # Stage 1: Tabular Data Extraction & Provenance Binding (Read-only)
        plan.add_node(
            PlanNode(
                node_id="fin_extract_01",
                capability="finance.extract_tabular",
                description="Extract structured financial figures, currencies, and line items with source citations.",
                risk_level=ActionRisk.LOW,
            )
        )

        # Stage 2: Deterministic Financial Ratio & Metric Computation (Read-only)
        plan.add_node(
            PlanNode(
                node_id="fin_metrics_02",
                capability="finance.compute_metrics",
                dependencies=["fin_extract_01"],
                description="Compute EBITDA, Gross Margin, Operating Margin, and Debt/Equity metrics.",
                risk_level=ActionRisk.LOW,
            )
        )

        # Stage 3: Parallel Variance Analysis & Trend Scenario Forecasting
        plan.add_node(
            PlanNode(
                node_id="fin_variance_03",
                capability="finance.variance_analysis",
                dependencies=["fin_metrics_02"],
                description="Calculate budget vs actual variances and favorable/unfavorable indicators.",
                risk_level=ActionRisk.LOW,
            )
        )
        plan.add_node(
            PlanNode(
                node_id="fin_forecast_04",
                capability="finance.forecast_model",
                dependencies=["fin_metrics_02"],
                description="Synthesize multi-scenario forecast models (Bear, Base, Bull) with declared CAGR rates.",
                risk_level=ActionRisk.LOW,
            )
        )

        # Stage 4: Provenance-Grounded Report Synthesis
        plan.add_node(
            PlanNode(
                node_id="fin_report_05",
                capability="finance.generate_report",
                dependencies=["fin_variance_03", "fin_forecast_04"],
                description="Synthesize executive financial summary report with explicit provenance citations and formula tables.",
                risk_level=ActionRisk.LOW,
            )
        )

        plan.compute_execution_stages()
        return plan
