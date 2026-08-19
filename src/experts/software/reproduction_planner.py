"""
Automated Reproduction Planner for Software Engineering Expert (M25 Phase 2)
Location: src/experts/software/reproduction_planner.py

Formulates automated reproduction strategies for bugs, traceback errors, and test regressions.
Pure in-memory planning, zero file mutation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ReproductionPlanner:
    """
    Synthesizes automated reproduction test plans from error messages, tracebacks, or issue descriptions.
    """

    def plan_reproduction(
        self,
        error_text: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Parses error signals and returns a structured reproduction strategy.

        Returns:
            Dictionary containing:
                - target_file: str | None
                - error_type: str
                - failed_symbol: str | None
                - reproduction_strategy: str
                - test_command: str
                - verification_criteria: str
        """
        target_file = None
        failed_symbol = None
        error_type = "GenericError"

        # Regex heuristics for file extraction from tracebacks
        file_match = re.search(r'File "([^"]+)", line (\d+)(?:, in (\w+))?', error_text)
        if file_match:
            target_file = file_match.group(1)
            failed_symbol = file_match.group(3)

        # Pytest failure patterns
        pytest_match = re.search(r'FAILED ([^:]+)::(\w+)', error_text)
        if pytest_match:
            target_file = pytest_match.group(1)
            failed_symbol = pytest_match.group(2)

        # Exception type extraction
        err_match = re.search(r'([A-Za-z0-9_]+Error|Exception):', error_text)
        if err_match:
            error_type = err_match.group(1)

        # Test command formulation
        if target_file and target_file.endswith(".py"):
            test_cmd = f"pytest {target_file}"
            if failed_symbol:
                test_cmd += f" -k {failed_symbol}"
        else:
            test_cmd = "pytest tests/ -q"

        return {
            "target_file": target_file,
            "error_type": error_type,
            "failed_symbol": failed_symbol,
            "reproduction_strategy": (
                f"1. Isolate failing condition ({error_type} in {target_file or 'target module'}). "
                f"2. Formulate minimal regression test. "
                f"3. Verify failure reproducibility before editing code. "
                f"4. Apply minimal patch and re-run suite."
            ),
            "test_command": test_cmd,
            "verification_criteria": f"Test suite passes with exit code 0 and zero {error_type} occurrences.",
        }
