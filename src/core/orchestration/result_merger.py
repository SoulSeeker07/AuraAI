"""
Result Merger
Combines multi-planner ExecutionResults, traces, artifacts, and observations into a single coherent response.
"""

import uuid
from typing import Any

from ..planning.execution_result import ExecutionResult
from ..planning.execution_trace import ExecutionTrace


class ResultMerger:
    """
    Merges multiple ExecutionResult objects into a single aggregated ExecutionResult.
    """

    def merge(self, results: list[ExecutionResult], goal: str) -> ExecutionResult:
        """
        Merge a list of ExecutionResults into one unified ExecutionResult.

        Args:
            results: List of ExecutionResult objects
            goal: Original user goal

        Returns:
            Merged ExecutionResult
        """
        if not results:
            return ExecutionResult(
                success=False,
                planner="orchestrator",
                goal=goal,
                confidence=0.0,
                observations=["No execution results were produced."],
                warnings=["Empty execution result set"],
            )

        if len(results) == 1:
            return results[0]

        all_success = all(r.success for r in results)
        total_time = sum(r.execution_time_seconds for r in results)
        avg_confidence = sum(r.confidence for r in results) / len(results)

        merged_observations: list[str] = []
        merged_warnings: list[str] = []
        merged_artifacts: list[dict[str, Any]] = []
        merged_memory_updates: dict[str, Any] = {}
        merged_data: dict[str, Any] = {}

        merged_trace = ExecutionTrace(
            trace_id=f"merged_{uuid.uuid4().hex[:8]}",
            agent_subsystem="orchestrator",
            goal=goal,
        )

        for r in results:
            merged_observations.extend(r.observations)
            merged_warnings.extend(r.warnings)
            merged_artifacts.extend(r.artifacts)
            merged_memory_updates.update(r.memory_updates)
            merged_data[r.planner] = r.data

            if r.trace:
                for node in r.trace.nodes:
                    merged_trace.add_node(
                        stage=f"{r.planner}:{node.stage}",
                        message=node.message,
                        duration_ms=node.duration_ms,
                        details=node.details,
                    )

        merged_trace.complete(success=all_success, score=avg_confidence * 100.0)

        return ExecutionResult(
            success=all_success,
            planner="master_orchestrator",
            goal=goal,
            confidence=avg_confidence,
            execution_time_seconds=total_time,
            trace=merged_trace,
            artifacts=merged_artifacts,
            observations=merged_observations,
            warnings=merged_warnings,
            memory_updates=merged_memory_updates,
            data=merged_data,
        )
