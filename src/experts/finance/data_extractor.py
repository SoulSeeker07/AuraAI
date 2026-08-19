"""
Financial Data Extractor for Financial Analysis Expert (M25 Phase 5)
Location: src/experts/finance/data_extractor.py

Parses financial statements, CSV/tabular rows, currency tokens, and reporting periods.
Pure in-memory parsing, zero file mutation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {
    "$": "USD",
    "₹": "INR",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}

UNIT_MULTIPLIERS = {
    "k": 1_000.0,
    "thousand": 1_000.0,
    "thousands": 1_000.0,
    "m": 1_000_000.0,
    "million": 1_000_000.0,
    "millions": 1_000_000.0,
    "b": 1_000_000_000.0,
    "billion": 1_000_000_000.0,
    "billions": 1_000_000_000.0,
    "cr": 10_000_000.0,
    "crore": 10_000_000.0,
    "crores": 10_000_000.0,
    "lakh": 100_000.0,
    "lakhs": 100_000.0,
}


class FinancialDataExtractor:
    """
    Extracts normalized financial line items, currencies, and scalar values from text and tables.
    """

    def extract_line_items(self, text: str) -> list[dict[str, Any]]:
        """
        Parses text for financial metric lines (e.g. 'Revenue: $150M', 'Net Income = ₹45 Cr').

        Returns:
            List of extracted financial metric dictionaries.
        """
        items: list[dict[str, Any]] = []
        lines = text.splitlines()

        pattern = re.compile(
            r'([A-Za-z0-9\s&/-]+?)\s*[:=]\s*([$₹€£¥]?)\s*([\d,]+(?:\.\d+)?)\s*(k|thousand|thousands|m|million|millions|b|billion|billions|cr|crore|crores|lakh|lakhs)?',
            re.IGNORECASE,
        )

        for line in lines:
            match = pattern.search(line)
            if match:
                raw_name = match.group(1).strip()
                curr_sym = match.group(2).strip()
                raw_val = match.group(3).replace(",", "").strip()
                raw_unit = (match.group(4) or "").lower().strip()

                try:
                    num_val = float(raw_val)
                    if raw_unit in UNIT_MULTIPLIERS:
                        num_val *= UNIT_MULTIPLIERS[raw_unit]

                    currency = CURRENCY_SYMBOLS.get(curr_sym, "USD")
                    items.append({
                        "metric_name": raw_name,
                        "raw_value": match.group(3),
                        "normalized_value": num_val,
                        "currency": currency,
                        "unit": raw_unit or "base",
                        "raw_text": line.strip(),
                    })
                except ValueError:
                    continue

        return items
