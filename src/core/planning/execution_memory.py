"""
Execution Memory
Persists successful and failed plan trajectories, environment fingerprints, and quality scores for plan reuse and adaptive learning.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .plan_evaluator import EvaluationResult


@dataclass
class MemoryRecord:
    """
    Memory record for a completed plan trajectory.
    """

    record_id: str
    goal_text: str
    category: str
    quality_score: float
    plan_id: str
    steps_count: int
    is_successful: bool
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    environment: dict[str, Any] = field(default_factory=dict)


class ExecutionMemory:
    """
    Long-term and short-term memory store for execution plans and quality scores.
    """

    def __init__(self, max_records: int = 500):
        self.max_records = max_records
        self._records: dict[str, MemoryRecord] = {}
        self._plans: dict[str, Any] = {}

    def store_plan(
        self,
        plan: Any,
        evaluation: EvaluationResult,
        environment: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """
        Store a completed plan and its evaluation.

        Args:
            plan: Completed plan object
            evaluation: EvaluationResult
            environment: Optional OS/hardware environment metadata

        Returns:
            Created MemoryRecord
        """
        record_id = f"mem_{plan.plan_id}"
        rec = MemoryRecord(
            record_id=record_id,
            goal_text=plan.goal.goal if hasattr(plan, "goal") else str(plan),
            category=plan.goal.category if hasattr(plan, "goal") else "general",
            quality_score=evaluation.overall_score,
            plan_id=plan.plan_id,
            steps_count=len(plan.steps) if hasattr(plan, "steps") else 0,
            is_successful=(
                plan.is_successful if hasattr(plan, "is_successful") else True
            ),
            environment=environment or {},
        )

        if len(self._records) >= self.max_records:
            first_key = next(iter(self._records))
            del self._records[first_key]
            if first_key in self._plans:
                del self._plans[first_key]

        self._records[record_id] = rec
        self._plans[record_id] = plan
        return rec

    def find_best_plan(self, goal_text: str) -> Any | None:
        """Find highest scoring cached plan for identical goal text."""
        clean_goal = goal_text.strip().lower()
        matching = [
            (rec, self._plans[rec.record_id])
            for rec in self._records.values()
            if rec.goal_text.strip().lower() == clean_goal
            and rec.is_successful
            and rec.record_id in self._plans
        ]

        if not matching:
            return None

        matching.sort(key=lambda item: item[0].quality_score, reverse=True)
        return matching[0][1]

    def get_summary_stats(self) -> dict[str, Any]:
        """Get summary statistics of stored execution memory."""
        total = len(self._records)
        successful = sum(1 for r in self._records.values() if r.is_successful)
        avg_score = (
            (sum(r.quality_score for r in self._records.values()) / total)
            if total > 0
            else 0.0
        )

        return {
            "total_plans": total,
            "successful_plans": successful,
            "success_rate": (successful / total * 100.0) if total > 0 else 0.0,
            "average_quality_score": avg_score,
        }
