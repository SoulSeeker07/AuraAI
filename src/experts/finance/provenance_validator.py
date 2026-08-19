"""
Provenance Validator for Financial Analysis Expert (M25 Phase 5)
Location: src/experts/finance/provenance_validator.py

Enforces strict provenance classification:
1. SOURCE_FACT: Directly cited raw figure from authoritative source document.
2. EXTRACTED_VALUE: Normalized numeric token with currency/period metadata.
3. VALIDATED_VALUE: Cross-reconciled figure verified against multiple sources.
4. CALCULATION: Deterministic formula result (e.g. Gross Margin, EBITDA).
5. FORECAST_INFERENCE: Extrapolated projection with declared modeling assumptions.
"""

from __future__ import annotations

from enum import Enum
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProvenanceType(str, Enum):
    SOURCE_FACT = "SOURCE_FACT"
    EXTRACTED_VALUE = "EXTRACTED_VALUE"
    VALIDATED_VALUE = "VALIDATED_VALUE"
    CALCULATION = "CALCULATION"
    FORECAST_INFERENCE = "FORECAST_INFERENCE"


class ProvenanceValidator:
    """
    Validates and tags financial figures with provenance metadata to prevent hallucination.
    """

    def validate_entries(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Validates a collection of financial entries and ensures each has a verified provenance type.

        Returns:
            Dictionary containing:
                - verified_count: int
                - unverified_count: int
                - entries: list[dict]
                - provenance_breakdown: dict[str, int]
        """
        breakdown: dict[str, int] = {pt.value: 0 for pt in ProvenanceType}
        validated_list: list[dict[str, Any]] = []
        unverified = 0

        for entry in entries:
            raw_pt = entry.get("provenance_type", ProvenanceType.SOURCE_FACT.value)
            try:
                pt = ProvenanceType(raw_pt)
            except ValueError:
                pt = ProvenanceType.EXTRACTED_VALUE

            source = entry.get("source_uri") or entry.get("citation", "unspecified")
            has_source = source != "unspecified" and bool(source)

            if not has_source and pt in (ProvenanceType.SOURCE_FACT, ProvenanceType.VALIDATED_VALUE):
                unverified += 1
                pt = ProvenanceType.EXTRACTED_VALUE  # Demote unverified facts

            breakdown[pt.value] += 1
            validated_list.append({
                "metric_name": entry.get("metric_name", "unnamed_metric"),
                "value": entry.get("value"),
                "currency": entry.get("currency", "USD"),
                "period": entry.get("period", "FY"),
                "provenance_type": pt.value,
                "source_uri": source,
                "assumptions": entry.get("assumptions", []),
            })

        return {
            "total_count": len(entries),
            "unverified_count": unverified,
            "provenance_breakdown": breakdown,
            "entries": validated_list,
        }
