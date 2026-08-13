"""
Financial Analysis Expert System
Location: src/experts/financial_expert.py

Provides programmatic financial metrics calculation (YoY Revenue Growth, CAGR, Gross/Net Margins),
schema validation, trend detection, anomaly auditing, and report proposals.

INVARIANT: Analysis is strictly programmatic — metrics are calculated via deterministic arithmetic, NEVER hallucinated.
RULE: Financial experts ONLY generate analytical findings and proposals — NEVER perform autonomous transactions or payments.
RULE: If data is missing or invalid, returns honest INVALID_FINANCIAL_DATA status with confidence=0.50.
"""

from __future__ import annotations

import csv
import io
import logging
import math
from pathlib import Path
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
    Expert System for Deterministic Financial Metrics Calculation, CAGR Modeling, Margin Analysis, and Anomaly Detection.
    """

    @property
    def domain(self) -> DomainType:
        return DomainType.FINANCIAL_ANALYSIS

    def _parse_tabular_data(self, raw_input: str) -> list[dict[str, Any]]:
        """Parse raw CSV text or inline tabular data into list of row dictionaries."""
        if not raw_input or not isinstance(raw_input, str):
            return []

        clean_text = raw_input.strip()
        if clean_text.startswith("data:text/csv,"):
            clean_text = clean_text.replace("data:text/csv,", "").strip()

        # Handle URI decoding of newlines/commas if needed
        clean_text = clean_text.replace("%0A", "\n").replace("%2C", ",")

        try:
            reader = csv.DictReader(io.StringIO(clean_text))
            rows = [dict(row) for row in reader if row]
            return rows
        except Exception:
            return []

    def _validate_schema(self, rows: list[dict[str, Any]]) -> dict[str, str]:
        """Detect column mappings for revenue, cogs, net_income, expenses, and year/period."""
        if not rows:
            return {}

        headers = [k.lower().strip() for k in rows[0].keys() if k]
        mapping: dict[str, str] = {}

        for orig_k in rows[0].keys():
            k = orig_k.lower().strip()
            if k in ("year", "period", "date", "time"):
                mapping["period"] = orig_k
            elif k in ("revenue", "sales", "total_revenue", "turnover"):
                mapping["revenue"] = orig_k
            elif k in ("cogs", "cost_of_goods_sold", "cost_of_sales"):
                mapping["cogs"] = orig_k
            elif k in ("net_income", "profit", "net_profit", "earnings"):
                mapping["net_income"] = orig_k
            elif k in ("expenses", "operating_expenses", "opex"):
                mapping["expenses"] = orig_k

        return mapping

    def _to_float(self, val: Any) -> float | None:
        """Safely convert value to float."""
        if val is None:
            return None
        s = str(val).replace("$", "").replace(",", "").replace("%", "").strip()
        try:
            return float(s)
        except ValueError:
            return None

    def _calculate_cagr(self, start_val: float, end_val: float, periods: int) -> float | None:
        """Calculate Compound Annual Growth Rate (CAGR)."""
        if start_val <= 0 or end_val <= 0 or periods <= 0:
            return None
        try:
            return (end_val / start_val) ** (1.0 / periods) - 1.0
        except Exception:
            return None

    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        query_lower = query.lower()
        findings: list[DomainFinding] = []
        proposals: list[DomainActionProposal] = []

        # 1. Discover and Load Tabular Data (G1)
        raw_csv = (
            context.get("csv_data")
            or context.get("csv_content")
            or context.get("data")
            or context.get("dataset_url")
            or context.get("url")
            or ""
        )

        target_file = context.get("target_file") or context.get("file_path")
        if target_file and Path(target_file).is_file():
            try:
                raw_csv = Path(target_file).read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Failed reading financial target file {target_file}: {e}")

        rows = self._parse_tabular_data(str(raw_csv))

        # 2. Schema Validation & Honest Missing Data Check (G2, G8)
        col_map = self._validate_schema(rows)
        if not rows or "revenue" not in col_map:
            findings.append(
                DomainFinding(
                    category="schema_validation",
                    title="Financial Schema Validation Failed",
                    description="Tabular dataset is missing or does not contain a valid 'revenue' numeric column. Status: INVALID_FINANCIAL_DATA.",
                    severity=SeverityLevel.INFO,
                    evidence=[
                        f"Raw Input Available: {bool(raw_csv)}",
                        f"Rows Parsed: {len(rows)}",
                        f"Detected Column Mapping: {col_map}",
                        "Status: INVALID_FINANCIAL_DATA",
                    ],
                    location=str(target_file or "inline_csv"),
                    confidence=0.50,
                )
            )
            proposals.append(
                DomainActionProposal(
                    engine="browser",
                    action="browser.navigate",
                    parameters={"url": str(raw_csv) if str(raw_csv).startswith("http") else "data:text/html,<table><tr><th>year</th><th>revenue</th></tr><tr><td>2023</td><td>100</td></tr></table>"},
                    description="Navigate to financial metrics table",
                    risk_level="low",
                )
            )
            return ExpertAnalysisResult(
                domain=self.domain,
                success=True,
                summary="Financial analysis complete with schema warning: INVALID_FINANCIAL_DATA.",
                findings=findings,
                proposals=proposals,
                data={"status": "INVALID_FINANCIAL_DATA", "rows_count": len(rows)},
            )

        # 3. Revenue Growth & CAGR Calculation (G3, G4)
        rev_col = col_map["revenue"]
        period_col = col_map.get("period")

        time_series: list[tuple[Any, float]] = []
        for r in rows:
            p_val = r.get(period_col, len(time_series) + 1) if period_col else len(time_series) + 1
            f_rev = self._to_float(r.get(rev_col))
            if f_rev is not None:
                time_series.append((p_val, f_rev))

        growths: list[float] = []
        for i in range(1, len(time_series)):
            prev_rev = time_series[i - 1][1]
            curr_rev = time_series[i][1]
            if prev_rev > 0:
                g_pct = (curr_rev - prev_rev) / prev_rev
                growths.append(g_pct)

        avg_growth = (sum(growths) / len(growths)) if growths else 0.0
        findings.append(
            DomainFinding(
                category="revenue_growth",
                title="Period-over-Period Revenue Growth Analysis",
                description=f"Calculated average Period-over-Period revenue growth of {avg_growth * 100.0:.2f}% across {len(time_series)} periods.",
                severity=SeverityLevel.INFO if avg_growth >= 0 else SeverityLevel.MEDIUM,
                evidence=[
                    f"Periods Count: {len(time_series)}",
                    f"Growth Series (%): {[round(g * 100.0, 2) for g in growths]}",
                    f"Average Growth Rate: {avg_growth * 100.0:.2f}%",
                ],
                location=f"Column:{rev_col}",
                confidence=0.98,
            )
        )

        cagr_val = None
        if len(time_series) >= 2:
            start_rev = time_series[0][1]
            end_rev = time_series[-1][1]
            n_periods = len(time_series) - 1
            cagr_val = self._calculate_cagr(start_rev, end_rev, n_periods)
            if cagr_val is not None:
                findings.append(
                    DomainFinding(
                        category="cagr_analysis",
                        title="Compound Annual Growth Rate (CAGR)",
                        description=f"Calculated CAGR of {cagr_val * 100.0:.2f}% over {n_periods} periods ({time_series[0][0]} -> {time_series[-1][0]}).",
                        severity=SeverityLevel.INFO if cagr_val >= 0 else SeverityLevel.MEDIUM,
                        evidence=[
                            f"Start Revenue ({time_series[0][0]}): ${start_rev:,.2f}",
                            f"End Revenue ({time_series[-1][0]}): ${end_rev:,.2f}",
                            f"Periods Span: {n_periods}",
                            f"CAGR: {cagr_val * 100.0:.2f}%",
                        ],
                        location=f"Series:{time_series[0][0]}-{time_series[-1][0]}",
                        confidence=0.99,
                    )
                )

        # 4. Gross / Net Margin Analysis (G5)
        cogs_col = col_map.get("cogs")
        net_col = col_map.get("net_income")

        margins: list[dict[str, Any]] = []
        for r in rows:
            rev_f = self._to_float(r.get(rev_col))
            if rev_f and rev_f > 0:
                m_info: dict[str, Any] = {"period": r.get(period_col, "N/A")}
                if cogs_col and self._to_float(r.get(cogs_col)) is not None:
                    cogs_f = self._to_float(r.get(cogs_col))
                    m_info["gross_margin"] = (rev_f - cogs_f) / rev_f
                if net_col and self._to_float(r.get(net_col)) is not None:
                    net_f = self._to_float(r.get(net_col))
                    m_info["net_margin"] = net_f / rev_f
                margins.append(m_info)

        if margins:
            findings.append(
                DomainFinding(
                    category="margin_analysis",
                    title="Gross and Net Margin Analysis",
                    description=f"Computed profitability margins across {len(margins)} periods.",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Computed Margins Summary: {margins}"],
                    location=f"Margins:{len(margins)}_rows",
                    confidence=0.96,
                )
            )

        # 5. Trend & Anomaly Detection (G6, G7)
        if len(growths) >= 2:
            is_increasing = all(g > 0 for g in growths)
            is_decreasing = all(g < 0 for g in growths)
            trend_str = "Upward Expansion" if is_increasing else ("Downward Contraction" if is_decreasing else "Volatile")

            findings.append(
                DomainFinding(
                    category="trend_detection",
                    title=f"Financial Trajectory Trend: {trend_str}",
                    description=f"Identified revenue trend trajectory classified as '{trend_str}'.",
                    severity=SeverityLevel.INFO if trend_str == "Upward Expansion" else SeverityLevel.MEDIUM,
                    evidence=[f"Trajectory Classification: {trend_str}", f"Historical Growth Series: {growths}"],
                    location="Series:Growth",
                    confidence=0.94,
                )
            )

        # Anomaly Detection: Spike or drop > 50%
        for i, g in enumerate(growths):
            if abs(g) >= 0.50:
                p_curr = time_series[i + 1][0]
                findings.append(
                    DomainFinding(
                        category="anomaly_detection",
                        title=f"Financial Anomaly Spike/Drop at Period {p_curr}",
                        description=f"Detected high growth anomaly of {g * 100.0:.2f}% at period {p_curr}.",
                        severity=SeverityLevel.MEDIUM if g > 0 else SeverityLevel.HIGH,
                        evidence=[f"Period: {p_curr}", f"Growth Delta: {g * 100.0:.2f}%", f"Anomaly Threshold: +-50.0%"],
                        location=f"Period:{p_curr}",
                        confidence=0.95,
                    )
                )

        # 6. Analysis Proposals Only (G10)
        proposals.append(
            DomainActionProposal(
                engine="engineering",
                action="code.report",
                parameters={"target_path": str(target_file or "financial_dataset.csv")},
                description="Generate financial metrics executive report",
                risk_level="low",
            )
        )
        html_table_uri = "data:text/html,<table><tr><th>year</th><th>revenue</th></tr><tr><td>2023</td><td>100</td></tr><tr><td>2024</td><td>150</td></tr></table>"
        proposals.append(
            DomainActionProposal(
                engine="browser",
                action="browser.navigate",
                parameters={"url": str(raw_csv) if str(raw_csv).startswith("http") else html_table_uri},
                description="Navigate to financial metrics table",
                risk_level="low",
            )
        )

        summary = (
            f"Financial analysis complete. Processed {len(time_series)} periods. "
            f"Avg Growth: {avg_growth * 100.0:.2f}%, CAGR: {f'{cagr_val * 100.0:.2f}%' if cagr_val is not None else 'N/A'}, "
            f"Findings: {len(findings)}, Proposals: {len(proposals)}."
        )

        return ExpertAnalysisResult(
            domain=self.domain,
            success=True,
            summary=summary,
            findings=findings,
            proposals=proposals,
            data={
                "periods_count": len(time_series),
                "avg_growth": avg_growth,
                "cagr": cagr_val,
                "findings_count": len(findings),
            },
        )
