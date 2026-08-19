"""
Variance Analyzer for Financial Analysis Expert (M25 Phase 5)
Location: src/experts/finance/variance_analyzer.py

Calculates Budget vs Actual variances, period-over-period deltas, and favorable/unfavorable indicators.
Pure in-memory calculations, zero file mutation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VarianceAnalyzer:
    """
    Computes variance breakdowns and flags significant deviations between budget and actual figures.
    """

    def analyze_variance(
        self,
        budget: dict[str, float],
        actual: dict[str, float],
        expense_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Analyzes variance across line items.

        Returns:
            Dictionary containing:
                - line_items: list[dict]
                - total_budget: float
                - total_actual: float
                - overall_variance: float
                - overall_variance_pct: float
        """
        exp_keys = expense_keys or {"cogs", "opex", "cost", "operating_expenses", "marketing", "r&d", "salaries"}
        results: list[dict[str, Any]] = []

        all_metrics = sorted(list(set(budget.keys()) | set(actual.keys())))

        for metric in all_metrics:
            b_val = float(budget.get(metric, 0.0))
            a_val = float(actual.get(metric, 0.0))
            delta = a_val - b_val
            pct = (delta / b_val * 100.0) if b_val != 0 else 0.0

            # Determine favorable vs unfavorable
            is_expense = any(k in metric.lower() for k in exp_keys)
            if is_expense:
                favorable = delta <= 0  # Under budget is favorable for expenses
            else:
                favorable = delta >= 0  # Over budget is favorable for revenue/income

            results.append({
                "metric": metric,
                "budget": b_val,
                "actual": a_val,
                "variance": round(delta, 2),
                "variance_pct": round(pct, 2),
                "favorable": favorable,
                "status": "FAVORABLE" if favorable else "UNFAVORABLE",
            })

        return {
            "item_count": len(results),
            "line_items": results,
        }
