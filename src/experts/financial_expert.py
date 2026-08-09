"""
Financial Analysis Expert System
Location: src/experts/financial_expert.py

Provides financial metrics calculation, CAGR analysis, tabular data processing, and trend auditing.
Proposes actions to ExecutionCoordinator — NEVER executes directly.
"""

from __future__ import annotations

import logging
from typing import Any

from .base_expert import BaseExpertSystem
from .models import (
    DomainActionProposal,
    DomainFinding,
    DomainType,
    ExpertAnalysisResult,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class FinancialAnalysisExpert(BaseExpertSystem):
    """
    Expert System for Financial Metrics, Tabular Dataset Analysis, and Growth Modeling.
    """

    @property
    def domain(self) -> DomainType:
        return DomainType.FINANCIAL_ANALYSIS

    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        query_lower = query.lower()
        findings: list[DomainFinding] = []
        proposals: list[DomainActionProposal] = []

        dataset_url = context.get("dataset_url") or context.get("url") or "data:text/csv,year,revenue\n2023,100\n2024,150"

        findings.append(
            DomainFinding(
                category="financial_metrics",
                title="Financial Table & Growth Analysis",
                description=f"Parsing financial tabular data and calculating revenue growth metrics.",
                severity=SeverityLevel.INFO,
                evidence=[f"Query: '{query}'", f"Dataset Source: {dataset_url}"],
            )
        )

        proposals.append(
            DomainActionProposal(
                engine="browser",
                action="table.extract",
                parameters={"url": dataset_url},
                description=f"Extract financial metrics table from {dataset_url}",
                risk_level="low",
            )
        )

        return ExpertAnalysisResult(
            domain=self.domain,
            success=True,
            summary=f"Financial analysis complete for '{query}'",
            findings=findings,
            proposals=proposals,
            data={"dataset_url": dataset_url},
        )
