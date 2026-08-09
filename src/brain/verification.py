"""
Layer 8: Verification
=====================

Current Aura only checks success. Verification should be much richer.

Example:
    Requested: Open YouTube
    Observed:
        - Chrome launched
        - youtube.com loaded
        - Page title
        - Window focused
        - PASS

If any check fails → Reflection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .execution_coordinator import CoordinationResult

logger = logging.getLogger(__name__)


@dataclass
class VerificationCheck:
    """A single verification check."""

    description: str
    passed: bool
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "passed": self.passed,
            "details": self.details,
        }


@dataclass
class VerificationReport:
    """The result of verifying an execution."""

    passed: bool
    checks: list[VerificationCheck] = field(default_factory=list)
    requested: str = ""
    observed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "requested": self.requested,
            "observed": self.observed,
        }


class VerificationEngine:
    """
    Verifies execution outcomes against the Execution Map's success criteria.

    This is richer than a simple success check — it validates
    each verification criterion from the Execution Map.
    """

    def verify(
        self,
        execution_map: dict[str, Any],
        coordination_result: CoordinationResult,
    ) -> VerificationReport:
        """
        Verify the execution against the map's verification criteria.

        Args:
            execution_map: The validated Execution Map.
            coordination_result: The result from the Execution Coordinator.

        Returns:
            VerificationReport with per-check results.
        """
        checks: list[VerificationCheck] = []
        observed: list[str] = []

        # Collect observations from all steps
        for step_result in coordination_result.step_results:
            observed.extend(step_result.observations)

        # ── 1. All steps succeeded ──────────────────────────────────────────
        all_steps_passed = len(coordination_result.failed_steps) == 0
        checks.append(
            VerificationCheck(
                description="All execution steps succeeded",
                passed=all_steps_passed,
                details=(
                    f"{len(coordination_result.step_results)} steps passed"
                    if all_steps_passed
                    else f"{len(coordination_result.failed_steps)} steps failed"
                ),
            )
        )

        # ── 2. Each verification criterion from the map ─────────────────────
        verification_criteria = execution_map.get("verification", [])
        for criterion in verification_criteria:
            passed = self._check_criterion(criterion, coordination_result, observed)
            checks.append(
                VerificationCheck(
                    description=criterion,
                    passed=passed,
                    details="Observed in execution" if passed else "Not observed",
                )
            )

        # ── 3. Goal achieved ────────────────────────────────────────────────
        goal = execution_map.get("goal", "")
        goal_achieved = all_steps_passed and all(c.passed for c in checks[1:])
        checks.append(
            VerificationCheck(
                description=f"Goal achieved: {goal}",
                passed=goal_achieved,
                details=(
                    "All criteria met" if goal_achieved else "Some criteria not met"
                ),
            )
        )

        passed = all(c.passed for c in checks)

        logger.info(
            f"Verification: {'PASSED' if passed else 'FAILED'} "
            f"({sum(1 for c in checks if c.passed)}/{len(checks)} checks)"
        )

        return VerificationReport(
            passed=passed,
            checks=checks,
            requested=goal,
            observed=observed,
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _check_criterion(
        self,
        criterion: str,
        coordination_result: CoordinationResult,
        observed: list[str],
    ) -> bool:
        """
        Check a single verification criterion.

        Uses keyword matching against observations and step results.
        """
        criterion_lower = criterion.lower()

        # Check observations
        for obs in observed:
            if criterion_lower in obs.lower():
                return True

        # Check step data
        for step_result in coordination_result.step_results:
            data = step_result.data
            if isinstance(data, dict):
                for key, value in data.items():
                    if (
                        criterion_lower in str(key).lower()
                        or criterion_lower in str(value).lower()
                    ):
                        return True

        # Check step descriptions
        for step_result in coordination_result.step_results:
            if criterion_lower in step_result.action.lower():
                return step_result.success

        return False


@dataclass
class GoalVerificationReport:
    """Independent end-to-end goal verification report."""

    goal: str
    passed: bool
    failure_type: str = "none"
    evidence: list[str] = field(default_factory=list)
    observed_state: dict[str, Any] = field(default_factory=dict)
    step_count: int = 0
    verified_steps: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "passed": self.passed,
            "failure_type": self.failure_type,
            "evidence": self.evidence,
            "observed_state": self.observed_state,
            "step_count": self.step_count,
            "verified_steps": self.verified_steps,
        }


__all__ = [
    "VerificationEngine",
    "VerificationReport",
    "VerificationCheck",
    "GoalVerificationReport",
]
