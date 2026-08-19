"""
Financial Model Builder for Financial Analysis Expert (M25 Phase 5)
Location: src/experts/finance/model_builder.py

Calculates fundamental financial ratios, margins, and profit metrics deterministically.
Pure in-memory calculations, zero file mutation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FinancialModelBuilder:
    """
    Computes standard financial statement formulas and margin metrics.
    """

    def compute_statement_metrics(self, statement: dict[str, float]) -> dict[str, Any]:
        """
        Calculates derived metrics from base financial statement figures.

        Expected keys in statement (case-insensitive):
            - revenue
            - cogs (cost of goods sold)
            - operating_expenses
            - net_income
            - depreciation_amortization (optional)
            - current_assets (optional)
            - current_liabilities (optional)
            - total_debt (optional)
            - total_equity (optional)
        """
        s = {k.lower().strip().replace(" ", "_"): float(v) for k, v in statement.items()}

        revenue = s.get("revenue", 0.0)
        cogs = s.get("cogs", s.get("cost_of_goods_sold", 0.0))
        op_exp = s.get("operating_expenses", s.get("opex", 0.0))
        net_income = s.get("net_income", 0.0)
        da = s.get("depreciation_amortization", s.get("d_and_a", 0.0))

        gross_profit = revenue - cogs
        gross_margin = (gross_profit / revenue) if revenue > 0 else 0.0

        operating_income = gross_profit - op_exp
        operating_margin = (operating_income / revenue) if revenue > 0 else 0.0

        ebitda = operating_income + da
        net_margin = (net_income / revenue) if revenue > 0 else 0.0

        # Balance sheet ratios
        ca = s.get("current_assets", 0.0)
        cl = s.get("current_liabilities", 0.0)
        current_ratio = (ca / cl) if cl > 0 else None

        debt = s.get("total_debt", 0.0)
        equity = s.get("total_equity", 0.0)
        debt_to_equity = (debt / equity) if equity > 0 else None

        return {
            "gross_profit": round(gross_profit, 2),
            "gross_margin_pct": round(gross_margin * 100, 2),
            "operating_income": round(operating_income, 2),
            "operating_margin_pct": round(operating_margin * 100, 2),
            "ebitda": round(ebitda, 2),
            "net_income": round(net_income, 2),
            "net_margin_pct": round(net_margin * 100, 2),
            "current_ratio": round(current_ratio, 2) if current_ratio is not None else None,
            "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else None,
        }
