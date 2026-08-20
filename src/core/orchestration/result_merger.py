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
            fail_obs = [
                obs
                for obs in user_facing_sys_obs
                if obs.startswith("❌")
                or "error" in obs.lower()
                or "failed" in obs.lower()
                or "stopped" in obs.lower()
            ]
            if task_obs and fail_obs:
                obs_texts = task_obs + fail_obs
            elif task_obs:
                obs_texts = task_obs
            elif user_facing_sys_obs:
                obs_texts = user_facing_sys_obs
            else:
                obs_texts = ["I was unable to complete that action."]
        else:
            obs_texts = task_obs if task_obs else user_facing_sys_obs
        artifacts_dict = [art.to_dict() for art in session.artifacts]

        # Extract citations and claims from artifacts or observations if present (G3 Invariant)
        extracted_citations: list[dict[str, Any]] = []
        extracted_claims: list[dict[str, Any]] = []
        extracted_topic: str = session.goal
        extracted_summary: str = ""
        extracted_grounding: list[dict[str, Any]] = []
        extracted_transcripts: list[dict[str, Any]] = []
        extracted_captures: list[dict[str, Any]] = []

        for art in session.artifacts:
            art_data = getattr(art, "content", None)
            if isinstance(art_data, dict):
                if art_data.get("citations"):
                    extracted_citations.extend(art_data["citations"])
                if art_data.get("claims"):
                    extracted_claims.extend(art_data["claims"])
                if art_data.get("summary"):
                    extracted_summary = art_data["summary"]
                if art_data.get("topic"):
                    extracted_topic = art_data["topic"]
                if art_data.get("grounding") or getattr(art, "artifact_type", "") == "ui_grounding":
                    extracted_grounding.append(art_data.get("grounding") or art_data)
                if art_data.get("transcript") or getattr(art, "artifact_type", "") == "voice_transcript":
                    extracted_transcripts.append(art_data)
                if art_data.get("capture_id") or getattr(art, "artifact_type", "") in ("vision_capture", "vision_perception"):
                    extracted_captures.append(art_data)

        avg_confidence = (
            sum(obs.confidence for obs in session.observations)
            / len(session.observations)
            if session.observations
            else 1.0
        )

        res_data: dict[str, Any] = {
            "session_id": session.session_id,
            "metrics": session.metrics,
            "budget": session.budget.to_dict(),
            "system_observations": sys_obs,
        }

        if extracted_citations:
            res_data["citations"] = extracted_citations
        if extracted_claims:
            res_data["claims"] = extracted_claims
        if extracted_summary:
            res_data["summary"] = extracted_summary
        if extracted_topic:
            res_data["topic"] = extracted_topic
        if extracted_grounding:
            res_data["grounding"] = extracted_grounding[0] if len(extracted_grounding) == 1 else extracted_grounding
        if extracted_transcripts:
            res_data["transcripts"] = extracted_transcripts
        if extracted_captures:
            res_data["vision_captures"] = extracted_captures

        # Extract daemon and scheduler keys if present in any subtask data
        for art in session.artifacts:
            art_data = getattr(art, "content", None)
            if isinstance(art_data, dict):
                if "job_id" in art_data and "job_id" not in res_data:
                    res_data["job_id"] = art_data["job_id"]
                if "run_id" in art_data and "run_id" not in res_data:
                    res_data["run_id"] = art_data["run_id"]
                if "jobs" in art_data and "jobs" not in res_data:
                    res_data["jobs"] = art_data["jobs"]

        return ExecutionResult(
            success=success,
            planner="cognitive_orchestrator",
            goal=session.goal,
            confidence=avg_confidence,
            trace=session.execution_trace,
            artifacts=artifacts_dict,
            observations=obs_texts,
            data=res_data,
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
        aggregated_citations: list[dict[str, Any]] = []
        aggregated_claims: list[dict[str, Any]] = []

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

            if isinstance(r.data, dict):
                if r.data.get("citations"):
                    aggregated_citations.extend(r.data["citations"])
                if r.data.get("claims"):
                    aggregated_claims.extend(r.data["claims"])

            if r.trace:
                for node in r.trace.nodes:
                    merged_trace.add_node(
                        stage=f"{r.planner}:{node.stage}",
                        message=node.message,
                        duration_ms=node.duration_ms,
                        details=node.details,
                    )

        if aggregated_citations:
            merged_data["citations"] = aggregated_citations
        if aggregated_claims:
            merged_data["claims"] = aggregated_claims

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
