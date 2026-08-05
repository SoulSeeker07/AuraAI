"""
Master Orchestrator — Cognitive Orchestration Layer
Location: src/core/orchestration/master_orchestrator.py

Main entry point for Aura AI Cognitive Orchestration.
Operates natively on AgentSession processes across the 7-stage cognitive pipeline:
1. Memory Recall (Context pre-fetch)
2. Executive Decision & Reasoning (DecisionEngine)
3. Task Graph Decomposition (TaskDecomposer)
4. Supervisor Delegation (SupervisorAgent -> PlannerRegistry)
5. Backend Selection & Parallel Execution (BackendRegistry)
6. Result Fusion & Observation Merging (ResultMerger)
7. Unified Memory Write (Persist outcomes)
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from ..backends.backend_registry import BackendRegistry
from ..planning.execution_result import ExecutionResult
from ..system.prompt_builder import PromptBuilder
from .agent_session import AgentSession, ExecutionBudget
from .artifact import Artifact
from .decision_engine import DecisionEngine
from .observation import Observation
from .planner_registry import PlannerRegistry
from .result_merger import ResultMerger
from .supervisor_agent import SupervisorAgent
from .task_decomposer import SubTask, TaskDecomposer

logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """
    Master Orchestrator for the Cognitive Orchestration Layer.
    """

    _instance: Any = None

    def __init__(
        self,
        planner_registry: PlannerRegistry | None = None,
        backend_registry: BackendRegistry | None = None,
        task_decomposer: TaskDecomposer | None = None,
        decision_engine: DecisionEngine | None = None,
        supervisor_agent: SupervisorAgent | None = None,
        result_merger: ResultMerger | None = None,
    ):
        self.planner_registry = planner_registry or PlannerRegistry.get_instance()
        self.backend_registry = backend_registry or BackendRegistry.get_instance()
        self.decomposer = task_decomposer or TaskDecomposer()
        self.decision_engine = decision_engine or DecisionEngine()
        self.supervisor = supervisor_agent or SupervisorAgent(self.planner_registry)
        self.result_merger = result_merger or ResultMerger()
        self._last_result: Any = None

        # Milestone 17.0: Build the identity layer at startup.
        # The PromptBuilder reads knowledge/ YAMLs + live registries and assembles
        # Aura's full self-knowledge context. Built once, cached for the session.
        try:
            self._prompt_builder: PromptBuilder = PromptBuilder.get_instance()
            self._identity_context: str = self._prompt_builder.build_system_prompt(
                include_examples=False  # keep shared_context lean; examples in separate key
            )
            logger.info(
                f"MasterOrchestrator: identity context loaded "
                f"({len(self._identity_context)} chars)."
            )
        except Exception as exc:
            logger.warning(f"MasterOrchestrator: PromptBuilder unavailable: {exc}")
            self._prompt_builder = None  # type: ignore[assignment]
            self._identity_context = "(identity layer unavailable)"

        logger.info("MasterOrchestrator initialized (Cognitive Orchestration Layer v17.0)")

    @classmethod
    def get_instance(cls) -> "MasterOrchestrator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def process_request(
        self,
        goal_text: str,
        preferred_planner: str | None = None,
        parameters: dict[str, Any] | None = None,
        budget: ExecutionBudget | None = None,
    ) -> ExecutionResult:
        """Synchronous entry point for processing a request."""
        return asyncio.run(
            self.process_request_async(goal_text, preferred_planner, parameters, budget)
        )

    async def process_request_async(
        self,
        goal_text: str,
        preferred_planner: str | None = None,
        parameters: dict[str, Any] | None = None,
        budget: ExecutionBudget | None = None,
    ) -> ExecutionResult:
        """
        Execute full 7-stage cognitive orchestration pipeline using AgentSession.
        """
        start_t = datetime.now().timestamp()
        session = AgentSession(goal=goal_text, budget=budget or ExecutionBudget())
        self._log_pipeline_start(goal_text, session.session_id)

        # Stage 1: Memory Recall
        t0 = datetime.now().timestamp()
        session.memory_context = self._recall_memory(goal_text)
        session.metrics["memory_recall_ms"] = round(
            (datetime.now().timestamp() - t0) * 1000, 2
        )

        # Stage 1.5: Conversational Reference Resolution ("Minimize it" -> "Minimize Notepad")
        try:
            from .reference_resolver import ReferenceResolver
            resolved_goal, ref_meta = ReferenceResolver.resolve_references(goal_text)
            if ref_meta.get("resolved"):
                logger.info(f"MasterOrchestrator resolved goal '{goal_text}' -> '{resolved_goal}'")
                goal_text = resolved_goal
                session.goal = resolved_goal
                session.metrics["reference_resolved"] = ref_meta
        except Exception as exc:
            logger.debug(f"Reference resolution skipped: {exc}")

        # Stage 2: Decision Engine (Reasoning, Risk, Budget, Policy)
        t1 = datetime.now().timestamp()
        decision = self.decision_engine.evaluate(
            goal=goal_text,
            budget=session.budget,
            memory_context=session.memory_context,
        )
        session.metrics["decision_engine_ms"] = round(
            (datetime.now().timestamp() - t1) * 1000, 2
        )

        session.decision_trace = getattr(decision, "trace", None)
        session.add_observation(
            Observation(
                obs_type="system",
                source="DecisionEngine",
                confidence=1.0,
                content=f"Pre-execution Decision: {decision.decision_summary}",
            )
        )

        try:
            from .world_timeline import WorldTimeline
            WorldTimeline.get_instance().record_event(
                event_type="session_start",
                description=f"Session started for goal: '{goal_text}'",
                session_id=session.session_id,
            )
        except Exception as exc:
            logger.debug(f"Timeline logging skipped: {exc}")

        # Stage 2.5: Desktop World State Snapshot & WorldDiff
        try:
            from .world_snapshot import WorldSnapshotProvider
            from .ownership_tracker import ResourceOwnershipTracker

            world_snap, world_diff = WorldSnapshotProvider().snapshot_with_diff()
            shared_world_state = world_snap.to_context_dict()
            setattr(decision, "world_state", shared_world_state)
            setattr(decision, "world_diff", world_diff.to_dict())
        except Exception as exc:
            logger.debug(f"World state snapshot skipped: {exc}")
            shared_world_state = {"running_processes": [], "is_live": False}
            world_diff = None

        if decision.should_refuse:
            session.add_observation(
                Observation(
                    obs_type="system",
                    source="DecisionEngine",
                    confidence=0.0,
                    content=f"Request Refusal: {decision.refusal_reason}",
                )
            )
            return self.result_merger.merge_session(session, success=False)

        # Stage 3: Task Graph Decomposition
        t2 = datetime.now().timestamp()
        task_graph = self.decomposer.decompose(goal_text, decision=decision)
        session.metrics["decomposition_ms"] = round(
            (datetime.now().timestamp() - t2) * 1000, 2
        )

        completed_ids: set[str] = set()
        shared_context: dict[str, Any] = {
            "session": session,
            "decision": decision,
            "previous_results": {},
            "world_state": getattr(decision, "world_state", {}),
            "world_diff": getattr(decision, "world_diff", {}),
            "aura_identity": self._identity_context,
            "capability_catalog": self.backend_registry.list_all_backends(),
            "planner_catalog": self.planner_registry.list_planners(),
            "resource_ownership": [r.to_dict() for r in ResourceOwnershipTracker.get_instance().get_aura_resources()],
        }

        # Stage 4 & 5: Supervisor Delegation, Backend Routing & Parallel Execution
        t3 = datetime.now().timestamp()
        for level_index, task_level in enumerate(task_graph.execution_order):
            logger.info(
                f"Session [{session.session_id}] Level {level_index + 1}/{len(task_graph.execution_order)}: {task_level}"
            )

            coroutines = [
                self._execute_level_task(
                    t_id, task_graph.subtasks[t_id], decision, shared_context
                )
                for t_id in task_level
            ]

            level_results = await asyncio.gather(*coroutines, return_exceptions=True)

            for t_id, res in zip(task_level, level_results):
                subtask = task_graph.subtasks[t_id]
                if isinstance(res, Exception):
                    logger.error(
                        f"[MasterOrchestrator] Stage 5 subtask '{t_id}' ({subtask.title}) FAILED\n"
                        f"  Capability : {subtask.capability}\n"
                        f"  Goal       : {subtask.description}\n"
                        f"  Exception  : {type(res).__name__}: {res}",
                        exc_info=res,
                    )
                    subtask.status = "failed"
                    session.add_observation(
                        Observation(
                            obs_type="system",
                            source="MasterOrchestrator",
                            confidence=0.0,
                            content=f"❌ Subtask '{subtask.title}' failed: {type(res).__name__}: {res}",
                        )
                    )
                elif isinstance(res, ExecutionResult):
                    subtask.status = "completed" if res.success else "failed"
                    subtask.result = res
                    completed_ids.add(t_id)

                    res_data = res.data if isinstance(res.data, dict) else {}
                    for obs_text in res.observations:
                        session.add_observation(
                            Observation(
                                obs_type=subtask.required_role.value,
                                source=res_data.get("backend", getattr(res, "planner", "desktop")),
                                confidence=res.confidence,
                                content=obs_text,
                            )
                        )

                    for art_data in (res.artifacts or []):
                        if isinstance(art_data, dict):
                            session.add_artifact(
                                Artifact(
                                    artifact_id=art_data.get(
                                        "artifact_id", f"art_{t_id}"
                                    ),
                                    artifact_type=art_data.get("artifact_type", "file"),
                                    location=art_data.get("location", str(art_data)),
                                    mime_type=art_data.get("mime_type", "text/plain"),
                                    creator=res_data.get("backend", res.planner),
                                )
                            )

                    shared_context["previous_results"][t_id] = res

        session.metrics["execution_ms"] = round(
            (datetime.now().timestamp() - t3) * 1000, 2
        )

        # Stage 6: Result Fusion
        t4 = datetime.now().timestamp()
        elapsed_dur = datetime.now().timestamp() - start_t
        session.metrics["total_execution_time_seconds"] = elapsed_dur
        session.metrics["total_request_ms"] = round(elapsed_dur * 1000, 2)
        session.metrics["subtasks_completed"] = len(completed_ids)
        session.metrics["subtasks_total"] = len(task_graph.subtasks)

        overall_success = len(completed_ids) == len(task_graph.subtasks)
        final_result = self.result_merger.merge_session(
            session, success=overall_success
        )
        session.metrics["result_merger_ms"] = round(
            (datetime.now().timestamp() - t4) * 1000, 2
        )
        final_result.data["metrics"] = session.metrics
        final_result.data["decision"] = {
            "intent_type": decision.intent_type.value,
            "can_answer_from_memory": decision.can_answer_from_memory,
            "can_answer_from_system": decision.can_answer_from_system,
            "needs_planner": decision.needs_planner,
            "preferred_planner": decision.preferred_planner,
            "needs_backend": decision.needs_backend,
            "should_search_first": decision.should_search_first,
            "should_refuse": decision.should_refuse,
        }
        final_result.data["subtasks_completed"] = session.metrics.get(
            "subtasks_completed", 0
        )
        final_result.data["subtasks_total"] = session.metrics.get("subtasks_total", 0)

        # Stage 7: Memory Write
        self._write_memory(session, final_result)
        self._last_result = final_result

        return final_result

    async def _execute_level_task(
        self,
        task_id: str,
        subtask: SubTask,
        decision: Any,
        context: dict[str, Any],
    ) -> ExecutionResult:
        subtask.status = "running"
        role_key, planner, plan_payload = self.supervisor.delegate_subtask(
            subtask, decision, context
        )

        backend = self.backend_registry.select_best_backend(subtask.capability)
        if not backend:
            return ExecutionResult(
                success=False,
                planner=role_key,
                goal=subtask.description,
                confidence=0.0,
                observations=[
                    f"No backend available for capability '{subtask.capability}'"
                ],
            )

        logger.info(f"Subtask [{task_id}] executing via backend '{backend.name}'")
        await asyncio.sleep(0.02)
        exec_res = backend.execute(
            capability=subtask.capability,
            goal=subtask.description,
            arguments=subtask.parameters,
        )
        return exec_res

    def _recall_memory(self, goal: str) -> dict[str, Any]:
        """Stage 1: Pre-fetch memory context from persistent store."""
        logger.info(f"Stage 1 Memory Recall for goal: '{goal[:30]}...'")
        try:
            from Memory import Memory as AuraMemory
            mem = AuraMemory()
            facts = mem.search(goal)
            all_facts = mem.facts()
            context_str = mem.build_context(user_input=goal)
            return {
                "recalled_facts": [f.value for f in facts],
                "all_facts": [{"category": f.category, "key": f.key, "value": f.value} for f in all_facts],
                "context_string": context_str,
                "session_id": "current_session",
            }
        except Exception as exc:
            logger.warning(f"Memory recall failed, falling back to empty context: {exc}")
            return {"recalled_facts": [], "session_id": "current_session"}

    def _write_memory(self, session: AgentSession, result: ExecutionResult) -> None:
        """Stage 7: Persist outcomes to unified memory."""
        logger.info(
            f"Stage 7 Memory Write for Session [{session.session_id}] (Success={result.success})"
        )
        try:
            from Memory import Memory as AuraMemory
            mem = AuraMemory()
            obs_summary = "; ".join(result.observations[:3]) if result.observations else "No observations"
            mem.remember_exchange(
                query=session.goal,
                answer=f"Result success={result.success}. {obs_summary}",
                topic=result.planner or "orchestrator",
            )
        except Exception as exc:
            logger.warning(f"Memory write failed: {exc}")

    def _log_pipeline_start(self, goal: str, session_id: str) -> None:
        """Emit one structured log block per pipeline request to logs/app.log."""
        focused_window = "unknown"
        proc_count = 0
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                focused_window = win32gui.GetWindowText(hwnd) or "unknown"
        except Exception:
            pass
        try:
            import psutil
            proc_count = len(list(psutil.process_iter()))
        except Exception:
            pass

        divider = "═" * 52
        logger.info(
            f"\n{divider}\n"
            f" AURA PIPELINE — \"{goal}\"\n"
            f" Session : {session_id}\n"
            f"──────────────────────────────────────────────────────\n"
            f" World Snapshot\n"
            f"   Focused window : {focused_window}\n"
            f"   Running procs  : {proc_count}\n"
            f"{divider}"
        )
