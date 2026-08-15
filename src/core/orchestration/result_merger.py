"""
Result Merger
Location: src/core/orchestration/result_merger.py

Combines observations, artifacts, execution traces, and subsystem results
into a unified ExecutionResult and updates the AgentSession.
"""

import uuid
from typing import Any

from ..planning.execution_result import ExecutionResult
from ..planning.execution_trace import ExecutionTrace
from .agent_session import AgentSession


class ResultMerger:
    """
    Merges multi-subsystem execution outcomes into a unified ExecutionResult.
    """

    def merge_session(
        self, session: AgentSession, success: bool = True
    ) -> ExecutionResult:
        """
        Synthesize an ExecutionResult directly from an AgentSession.

        Args:
            session: AgentSession process object
            success: Overall execution success flag

        Returns:
            Unified ExecutionResult
        """
        task_obs = [
            obs.content
            for obs in session.observations
            if obs.content and obs.obs_type != "system"
        ]
        sys_obs = [
            obs.content
            for obs in session.observations
            if obs.content and obs.obs_type == "system"
        ]
        user_facing_sys_obs = []
        for obs in session.observations:
            if obs.obs_type == "system" and obs.content:
                # Filter out raw internal orchestration state prefixes from user-facing text
                if any(
                    obs.content.startswith(p)
                    for p in (
                        "Pre-execution Decision:",
                        "Session started",
                        "DecisionEngine evaluated",
                    )
                ):
                    continue
                # Translate capability errors into clean user-friendly phrasing
                if "no backend available for capability" in obs.content.lower():
                    user_facing_sys_obs.append("I don't know how to perform that specific desktop action yet.")
                else:
                    user_facing_sys_obs.append(obs.content)

        if not success:
            obs_texts = task_obs if task_obs else (user_facing_sys_obs if user_facing_sys_obs else ["I was unable to complete that action."])
        else:
            obs_texts = task_obs if task_obs else user_facing_sys_obs
        artifacts_dict = [art.to_dict() for art in session.artifacts]

        avg_confidence = (
            sum(obs.confidence for obs in session.observations)
            / len(session.observations)
            if session.observations
            else 1.0
        )

        return ExecutionResult(
            success=success,
            planner="cognitive_orchestrator",
            goal=session.goal,
            confidence=avg_confidence,
            trace=session.execution_trace,
            artifacts=artifacts_dict,
            observations=obs_texts,
            data={
                "session_id": session.session_id,
                "metrics": session.metrics,
                "budget": session.budget.to_dict(),
                "system_observations": sys_obs,
            },
        )

    def merge(self, results: list[ExecutionResult], goal: str) -> ExecutionResult:
        """
        Merge a list of ExecutionResults into one unified ExecutionResult.
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
