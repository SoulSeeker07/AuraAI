"""
Plan Evaluator
Scores plan execution trajectory quality (0-100) based on duration, retries, recovery steps, and verification pass rate.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class EvaluationResult:
    """
    Quality evaluation breakdown for an execution plan.
    """

    plan_id: str
    overall_score: float  # 0.0 to 100.0
    success_rate: float
    total_duration_ms: float
    retry_penalty: float
    recovery_penalty: float
    verification_passed: bool
    summary: str


class PlanEvaluator:
    """
    Evaluates completed execution plan quality.
    """

    def evaluate(self, plan: Any) -> EvaluationResult:
        """
        Compute quality score (0.0 - 100.0) for a completed plan.

        Args:
            plan: Completed plan object

        Returns:
            EvaluationResult
        """
        steps = getattr(plan, "steps", [])
        if not steps:
            return EvaluationResult(
                plan_id=getattr(plan, "plan_id", "plan_unknown"),
                overall_score=0.0,
                success_rate=0.0,
                total_duration_ms=0.0,
                retry_penalty=0.0,
                recovery_penalty=0.0,
                verification_passed=False,
                summary="Empty plan",
            )

        successful_steps = sum(
            1
            for s in steps
            if getattr(s, "status", None) and s.status.value == "success"
        )
        success_rate = (successful_steps / len(steps)) * 100.0

        total_duration = sum(getattr(s, "actual_time_ms", 0.0) or 0.0 for s in steps)
        total_retries = sum(getattr(s, "retry_count", 0) for s in steps)
        total_recoveries = sum(
            1 for s in steps if getattr(s, "rollback_result", None) is not None
        )

        retry_penalty = min(30.0, total_retries * 10.0)
        recovery_penalty = min(20.0, total_recoveries * 15.0)

        is_successful = getattr(plan, "is_successful", True)
        verification_passed = is_successful and all(
            s.status.value == "success"
            for s in steps
            if hasattr(s, "step_type")
            and getattr(s.step_type, "value", "") == "verification"
        )

        base_score = 100.0 if is_successful else (success_rate * 0.5)
        overall_score = max(0.0, base_score - retry_penalty - recovery_penalty)

        summary = (
            f"Plan {'succeeded' if is_successful else 'failed'} with score {overall_score:.1f}/100 "
            f"({total_retries} retries, {total_recoveries} recoveries)"
        )

        return EvaluationResult(
            plan_id=getattr(plan, "plan_id", "plan_unknown"),
            overall_score=overall_score,
            success_rate=success_rate,
            total_duration_ms=total_duration,
            retry_penalty=retry_penalty,
            recovery_penalty=recovery_penalty,
            verification_passed=verification_passed,
            summary=summary,
        )
