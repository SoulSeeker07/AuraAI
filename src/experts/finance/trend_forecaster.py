"""
Trend Forecaster for Financial Analysis Expert (M25 Phase 5)
Location: src/experts/finance/trend_forecaster.py

Computes Compound Annual Growth Rates (CAGR) and scenario projections (Bear, Base, Bull)
with explicitly declared modeling assumptions.
Pure in-memory calculations, zero file mutation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TrendForecaster:
    """
    Synthesizes financial forecasts, CAGR metrics, and multi-scenario projection tables.
    """

    def compute_cagr(self, initial_value: float, final_value: float, periods: int) -> float:
        """
        Computes Compound Annual Growth Rate (CAGR) as a percentage.
        """
        if initial_value <= 0 or final_value <= 0 or periods <= 0:
            return 0.0
        cagr = (final_value / initial_value) ** (1.0 / periods) - 1.0
        return round(cagr * 100.0, 2)

    def forecast_scenarios(
        self,
        base_value: float,
        periods_ahead: int = 3,
        cagr_rate_pct: float = 10.0,
    ) -> dict[str, Any]:
        """
        Projects multi-scenario financial forecasts:
        - Bear Case: CAGR - 5.0%
        - Base Case: CAGR
        - Bull Case: CAGR + 5.0%

        Returns:
            Dictionary containing scenario projection series and explicit assumptions.
        """
        scenarios = {
            "bear": {"growth_pct": max(0.0, cagr_rate_pct - 5.0), "projections": []},
            "base": {"growth_pct": cagr_rate_pct, "projections": []},
            "bull": {"growth_pct": cagr_rate_pct + 5.0, "projections": []},
        }

        for sc_name, sc_data in scenarios.items():
            rate = sc_data["growth_pct"] / 100.0
            val = base_value
            for t in range(1, periods_ahead + 1):
                val *= (1.0 + rate)
                sc_data["projections"].append({"period_offset": t, "projected_value": round(val, 2)})

        return {
            "base_value": base_value,
            "periods_ahead": periods_ahead,
            "assumptions": [
                f"Base Case assumes constant annual growth of {cagr_rate_pct:.1f}%.",
                f"Bear Case assumes down-cycle growth of {scenarios['bear']['growth_pct']:.1f}%.",
                f"Bull Case assumes expansion growth of {scenarios['bull']['growth_pct']:.1f}%.",
                "Assumes macroeconomic inflation and tax rates remain constant.",
            ],
            "scenarios": scenarios,
        }
