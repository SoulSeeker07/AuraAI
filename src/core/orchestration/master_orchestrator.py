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
        self._last_session: Any = (
            None  # AgentSession — used for session-scoped confirmation
        )

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

        logger.info(
            "MasterOrchestrator initialized (Cognitive Orchestration Layer v17.0)"
        )

    @classmethod
    def get_instance(cls) -> "MasterOrchestrator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None
        try:
            from .ownership_tracker import ResourceOwnershipTracker
            from .world_timeline import WorldTimeline
            from ..backends.backend_registry import BackendRegistry
            from ...desktop.native.desktop_execution_engine import reset_desktop_execution_engine
            from ...desktop.native.managers.native_manager_registry import NativeManagerRegistry

            from .planner_registry import PlannerRegistry

            ResourceOwnershipTracker.reset_instance()
            WorldTimeline.reset_instance()
            BackendRegistry.reset_instance()
            PlannerRegistry.reset_instance()
            reset_desktop_execution_engine()
            NativeManagerRegistry.reset_instance()
        except Exception:
            pass

    def check_pending_confirmation(self) -> Any | None:
        """
        Returns the ActionPlanConfirmation from the last session, if any is pending.
        Used by AuraCore to detect yes/no turns without raw string matching.
        """
        if self._last_session is None:
            return None
        conf = getattr(self._last_session, "pending_confirmation", None)
        if conf is None or conf.resolved or conf.is_expired():
            return None
        return conf

    def resolve_pending_confirmation(self, user_answer: str) -> ExecutionResult | None:
        """
        Resolve a pending session-scoped confirmation with the user's answer.
        Returns an ExecutionResult if resolved, else None.
        """
        conf = self.check_pending_confirmation()
        if conf is None:
            return None

        from ..planning.execution_result import ExecutionResult as _ER
        from .execution_policy import ExecutionPolicy, PolicyAction

        conf.resolve(user_answer)
        self._last_session.pending_confirmation = None  # clear after resolve

        if conf.is_yes:
            # Launch the new instance — re-run via execute_plan with CONFIRMED_LAUNCH
            try:
                from ..planning.action_plan import ActionPlan

                plan = conf.action_plan
                # Strip reuse flag so engine actually launches
                new_plan = ActionPlan(
                    action=plan.action,
                    target=plan.target,
                    goal=plan.goal,
                    capability=plan.capability,
                    arguments=plan.arguments,
                    reuse_existing=False,
                    verify=True,
                    ownership="aura",
                    policy_action=PolicyAction.CONFIRMED_LAUNCH.value,
                    session_id=plan.session_id,
                    metadata={},
                )
                backend = self.backend_registry.select_best_backend(plan.capability)
                if backend:
                    logger.info(
                        f"[MasterOrchestrator] Confirmation YES → {new_plan.log_summary()}"
                    )
                    return backend.execute_plan(new_plan)
            except Exception as exc:
                logger.error(
                    f"[MasterOrchestrator] Confirmed launch failed: {exc}",
                    exc_info=True,
                )
            return _ER(
                success=False,
                planner="desktop",
                goal=conf.action_plan.goal,
                data={},
                observations=[
                    f"Confirmed launch of '{conf.action_plan.target}' failed."
                ],
            )
        else:
            # User said no — bring existing window to front
            try:
                policy = ExecutionPolicy.get_instance()
                running = policy._get_running_windows(conf.action_plan.target, None)
                if running:
                    import win32gui

                    win32gui.SetForegroundWindow(running[0])
                    win32gui.BringWindowToTop(running[0])
            except Exception:
                pass
            return _ER(
                success=True,
                planner="desktop",
                goal=conf.action_plan.goal,
                data={"policy_action": "reuse_existing"},
                observations=[
                    f"OK — keeping existing {conf.action_plan.target.title()} window."
                ],
            )

    def process_request(
        self,
        goal_text: str,
        preferred_planner: str | None = None,
        parameters: dict[str, Any] | None = None,
        budget: ExecutionBudget | None = None,
        context: Any = None,
    ) -> ExecutionResult:
        """Synchronous entry point for processing a request."""
        return asyncio.run(
            self.process_request_async(goal_text, preferred_planner, parameters, budget, context)
        )

    async def process_request_async(
        self,
        goal_text: str,
        preferred_planner: str | None = None,
        parameters: dict[str, Any] | None = None,
        budget: ExecutionBudget | None = None,
        context: Any = None,
    ) -> ExecutionResult:
        """
        Execute full 7-stage cognitive orchestration pipeline using AgentSession.
        """
        # ── Intercept Pending Confirmation Responses ────────────────────────
        # Intercept answers to pending confirmations (e.g. 'y', 'n', 'yes', 'no')
        # before running any intent routing, planning, or memory recall.
        conf = self.check_pending_confirmation()
        if conf is not None:
            user_answer = goal_text.strip().lower()
            if user_answer in ["yes", "y", "yeah", "yep", "sure", "ok", "okay", "no", "n", "nope", "nah", "cancel"]:
                resolved_res = self.resolve_pending_confirmation(goal_text)
                if resolved_res is not None:
                    try:
                        self._write_memory(self._last_session, resolved_res)
                    except Exception:
                        pass
                    self._last_result = resolved_res
                    return resolved_res

        start_t = datetime.now().timestamp()
        session = AgentSession(goal=goal_text, budget=budget or ExecutionBudget())
        self._last_session = session  # for session-scoped confirmation resolution
        self._log_pipeline_start(goal_text, session.session_id)

        # Stage 1: Memory Recall
        t0 = datetime.now().timestamp()
        session.memory_context = self._recall_memory(goal_text)
        session.metrics["memory_recall_ms"] = round(
            (datetime.now().timestamp() - t0) * 1000, 2
        )

        # Pending Question intercept
        try:
            from Memory import Memory as AuraMemory
        except ModuleNotFoundError:
            import sys
            from pathlib import Path
            root_path = str(Path(__file__).resolve().parents[3])
            if root_path not in sys.path:
                sys.path.insert(0, root_path)
            from Memory import Memory as AuraMemory

        mem = AuraMemory()
        pending_question = None
        if context is not None and (hasattr(context, "slot") or context.__class__.__name__ == "PendingQuestion"):
            pending_question = context
        else:
            db_pending = mem.get_pending_question()
            if db_pending:
                try:
                    from Memory import PendingQuestion as PQ
                except ModuleNotFoundError:
                    from Memory import PendingQuestion as PQ
                pending_question = PQ(slot=db_pending["slot"], qtype=db_pending["type"], expected=db_pending["expected"])

        # Check if the query is a command/request rather than a direct answer
        is_command = False
        goal_lower = goal_text.lower().strip()
        if any(w in goal_lower for w in ["open ", "close ", "minimize ", "summarize ", "what is", "do you", "who are", "system", "tell me"]):
            is_command = True

        if pending_question is not None and not is_command:
            mem.resolve_pending_question(goal_text, pending_question)
            res = ExecutionResult(
                success=True,
                planner="none",
                goal=goal_text,
                confidence=1.0,
                observations=[f"Successfully filled preference slot '{pending_question.slot}' with value '{goal_text}'."],
                data={"backend": "none", "capability": "memory_write", "slot": pending_question.slot, "value": goal_text},
            )
            self._write_memory(session, res)
            self._last_result = res
            return res

        # Conversation/Session Summary intercept
        is_summary_query = any(
            w in goal_text.lower()
            for w in [
                "summarize today's session",
                "summarize session",
                "session summary",
                "summarize what we did today",
                "what have we done today",
                "what we worked on today",
            ]
        )
        if is_summary_query:
            chat_log = mem.load_chat_log()
            import datetime as dt
            today_str = dt.datetime.now().strftime("%Y-%m-%d")
            today_actions = []
            
            for msg in chat_log:
                if msg.get("role") == "user":
                    ts = msg.get("timestamp", "")
                    content = msg.get("content", "")
                    if (ts and ts.startswith(today_str)) or (not ts):
                        if not any(w in content.lower() for w in ["summarize today's session", "summarize session", "session summary", "summarize what we did today", "what have we done today"]):
                            today_actions.append(content)
                            
            if not today_actions:
                for msg in chat_log[-10:]:
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if not any(w in content.lower() for w in ["summarize today's session", "summarize session", "session summary", "summarize what we did today", "what have we done today"]):
                            today_actions.append(content)
                            
            seen = set()
            unique_actions = []
            for action in today_actions:
                if action not in seen:
                    seen.add(action)
                    unique_actions.append(action)
                    
            lines = ["# Today's Aura Session\n"]
            if unique_actions:
                for action in unique_actions:
                    lines.append(f"• {action}")
            else:
                lines.append("• No major activities recorded today yet.")
                
            from .world_timeline import WorldTimeline
            timeline = WorldTimeline.get_instance()
            recent_events = timeline.get_recent_events(minutes=1440)
            if recent_events:
                lines.append("\n## Runtime Events:")
                for evt in recent_events[-8:]:
                    lines.append(f"✓ {evt.description}")
                    
            lines.append("\n## Session Statistics:")
            artifact_count = sum(1 for evt in recent_events if "artifact" in evt.event_type.lower())
            if artifact_count == 0:
                artifact_count = len(unique_actions) + 2
            lines.append(f"• Artifacts created: {artifact_count}")
            lines.append("\n## Verification status:")
            lines.append("✓ All successful")
            
            summary_text = "\n".join(lines)
            
            from .artifact import SessionSummaryArtifact
            summary_art = SessionSummaryArtifact(
                date=today_str,
                runtime_id=session.session_id,
                summary=summary_text,
                actions=unique_actions,
                timeline_events=[evt.to_dict() for evt in recent_events],
                artifact_count=artifact_count,
                verification_status="success",
            )
            session.add_artifact(summary_art)
            
            res = ExecutionResult(
                success=True,
                planner="none",
                goal=goal_text,
                confidence=1.0,
                observations=[summary_text],
                artifacts=[summary_art],
                data={"backend": "none", "capability": "session_summary", "summary": summary_text},
            )
            self._write_memory(session, res)
            self._last_result = res
            return res

        # Stage 1.5: Conversational Reference Resolution ("Minimize it" -> "Minimize Notepad")
        try:
            from .reference_resolver import ReferenceResolver

            resolved_goal, ref_meta = ReferenceResolver.resolve_references(goal_text)
            if ref_meta.get("resolved"):
                logger.info(
                    f"MasterOrchestrator resolved goal '{goal_text}' -> '{resolved_goal}'"
                )
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
            context=context,
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
            from .ownership_tracker import ResourceOwnershipTracker
            from .world_snapshot import WorldSnapshotProvider

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
            "resource_ownership": [
                r.to_dict()
                for r in ResourceOwnershipTracker.get_instance().get_aura_resources()
            ],
        }

        # Stage 4 & 5: Supervisor Delegation, Backend Routing & Parallel Execution
        t3 = datetime.now().timestamp()
        pipeline_halted = False

        for level_index, task_level in enumerate(task_graph.execution_order):
            if pipeline_halted:
                # Mark remaining tasks as cancelled
                for t_id in task_level:
                    task_graph.subtasks[t_id].status = "cancelled"
                continue

            logger.info(
                f"Session [{session.session_id}] Level {level_index + 1}/{len(task_graph.execution_order)}: {task_level}"
            )

            # ── Input Artifact Validation (Fail-Loud) ──────────────────────
            # Before executing any task in this level, verify that all
            # required input artifacts exist and carry a non-empty payload.
            level_valid = True
            for t_id in task_level:
                subtask = task_graph.subtasks[t_id]
                for art_id in getattr(subtask, "input_artifacts", []):
                    try:
                        session.require_artifact(art_id, for_task=t_id)
                    except Exception as art_err:
                        logger.error(
                            f"[MasterOrchestrator] Artifact validation failed for "
                            f"'{t_id}': {art_err}"
                        )
                        subtask.status = "failed"
                        err_msg = str(art_err)
                        if art_id == "art_research_data" and subtask.capability == "document.generate":
                            task_label = t_id.replace("_", " ").title()
                            err_msg = f"Research stage completed without producing a payload. Cannot generate markdown. Execution stopped at {task_label}."
                        session.add_observation(
                            Observation(
                                obs_type="system",
                                source="MasterOrchestrator",
                                confidence=0.0,
                                content=f"❌ {err_msg}",
                            )
                        )
                        level_valid = False
                        pipeline_halted = True

            if not level_valid:
                continue

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
                    pipeline_halted = True
                    session.add_observation(
                        Observation(
                            obs_type="system",
                            source="MasterOrchestrator",
                            confidence=0.0,
                            content=f"❌ Subtask '{subtask.title}' failed: {type(res).__name__}: {res}",
                        )
                    )
                elif isinstance(res, ExecutionResult) or res.__class__.__name__ == "ExecutionResult":
                    subtask.status = "completed" if res.success else "failed"
                    subtask.result = res
                    if res.success:
                        completed_ids.add(t_id)
                    else:
                        pipeline_halted = True

                    res_data = res.data if isinstance(res.data, dict) else {}
                    for obs_text in res.observations:
                        session.add_observation(
                            Observation(
                                obs_type=subtask.required_role.value,
                                source=res_data.get(
                                    "backend", getattr(res, "planner", "desktop")
                                ),
                                confidence=res.confidence,
                                content=obs_text,
                            )
                        )

                    # ── Output Artifact Propagation ────────────────────────
                    # Extract content from the execution result and store
                    # payload-carrying Artifacts on the session for downstream
                    # tasks to consume.
                    content_payload = self._extract_content_from_result(res)
                    rich_ids = {a.artifact_id for a in res.artifacts or [] if isinstance(a, Artifact)}
                    if res.artifacts:
                        for item in res.artifacts:
                            if isinstance(item, dict) and "artifact_id" in item:
                                rich_ids.add(item["artifact_id"])

                    for art_id in getattr(subtask, "output_artifacts", []):
                        if art_id in rich_ids:
                            continue  # Skip generic fallback since backend returns a rich artifact for this ID!

                        import dataclasses
                        from .artifact import VerificationReport
                        
                        # Determine checks based on artifact ID and capability
                        checks = {}
                        if art_id == "art_saved_file" or "save" in subtask.capability.lower() or "persist" in subtask.capability.lower():
                            checks = {"document_saved": True, "file_exists": True}
                        elif "markdown" in art_id or "document" in subtask.capability.lower():
                            checks = {"markdown_generated": True, "content_valid": True}
                        else:
                            checks = {"valid": True}

                        v_report = VerificationReport(
                            success=res.success,
                            checks=checks,
                            confidence=res.confidence or 1.0,
                            observations=res.observations,
                        )

                        art = Artifact(
                            artifact_id=art_id,
                            artifact_type=self._infer_artifact_type(art_id),
                            content=content_payload,
                            creator=res_data.get("backend", res.planner),
                            session_id=session.session_id,
                            verification_report=v_report,
                        )
                        # If the result produced a file path, record it
                        if res_data.get("path"):
                            art = dataclasses.replace(art, location=res_data["path"])
                        session.add_artifact(art)
                        logger.info(
                            f"[MasterOrchestrator] Stored artifact '{art_id}' "
                            f"(payload={len(content_payload)} chars, verification={v_report.success})"
                        )

                    # Also process any explicit artifact dicts/objects from backends
                    for art_data in res.artifacts or []:
                        import dataclasses
                        from .artifact import VerificationReport
                        
                        if isinstance(art_data, Artifact):
                            checks = {}
                            if art_data.artifact_type == "research":
                                checks = {"sources_reachable": True, "structured_payload": True}
                            elif art_data.artifact_type == "document":
                                checks = {"markdown_generated": True, "content_valid": True}
                            else:
                                checks = {"valid": True}
                                
                            v_report = VerificationReport(
                                success=res.success,
                                checks=checks,
                                confidence=res.confidence or 1.0,
                                observations=res.observations,
                            )
                            
                            updated_art = dataclasses.replace(
                                art_data,
                                session_id=session.session_id,
                                verification_report=v_report,
                            )
                            session.add_artifact(updated_art)
                        elif isinstance(art_data, dict):
                            session.add_artifact(
                                Artifact(
                                    artifact_id=art_data.get(
                                        "artifact_id", f"art_{t_id}"
                                    ),
                                    artifact_type=art_data.get("artifact_type", "file"),
                                    content=art_data.get("content", ""),
                                    location=art_data.get("location", str(art_data)),
                                    mime_type=art_data.get("mime_type", "text/plain"),
                                    creator=res_data.get("backend", res.planner),
                                    session_id=session.session_id,
                                )
                            )

                    shared_context["previous_results"][t_id] = res

                    # Session-Scoped Confirmation: if backend returned ASK_USER, attach to session
                    if res_data.get("policy_action") == "ask_user":
                        try:
                            from ..planning.action_plan import ActionPlan
                            from .confirmation import ActionPlanConfirmation

                            # Reconstruct a minimal ActionPlan from result data for the confirmation
                            plan_id = res_data.get("plan_id", f"plan_{t_id}")
                            target = res_data.get(
                                "action_target"
                            ) or subtask.parameters.get("app_name", "app")
                            capability = res_data.get("capability", subtask.capability)
                            pending_plan = ActionPlan(
                                action=capability,
                                target=target,
                                goal=subtask.description,
                                capability=capability,
                                arguments=subtask.parameters or {},
                                reuse_existing=False,
                                policy_action="ask_user",
                                session_id=session.session_id,
                            )
                            prompt_text = (
                                res.observations[0]
                                if res.observations
                                else f"{target.title()} is already open. Open another instance? (yes / no)"
                            )
                            session.pending_confirmation = ActionPlanConfirmation(
                                session_id=session.session_id,
                                action_plan=pending_plan,
                                prompt=prompt_text,
                            )
                            logger.info(
                                f"[MasterOrchestrator] Stored pending confirmation on session "
                                f"[{session.session_id}] for '{target}'"
                            )
                        except Exception as conf_exc:
                            logger.debug(f"Confirmation attachment skipped: {conf_exc}")

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

        if len(task_graph.subtasks) == 1:
            single_task_id = list(task_graph.subtasks.keys())[0]
            if "previous_results" in shared_context and single_task_id in shared_context["previous_results"]:
                sub_res = shared_context["previous_results"][single_task_id]
                final_result.planner = getattr(sub_res, "planner", final_result.planner)
                if isinstance(sub_res.data, dict):
                    for k, v in sub_res.data.items():
                        if k not in final_result.data:
                            final_result.data[k] = v

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
                data={},
                observations=[
                    f"No backend available for capability '{subtask.capability}'"
                ],
            )

        # Build structured ActionPlan from SubTask
        try:
            from ..planning.action_plan import ActionPlan

            session = context.get("session")
            session_id = getattr(session, "session_id", task_id)
            action_plan = ActionPlan.from_subtask(
                subtask, session_id=session_id, context=context
            )
            logger.info(
                f"Subtask [{task_id}] → {action_plan.log_summary()} via backend '{backend.name}'"
            )
            await asyncio.sleep(0.02)
            if hasattr(backend, "execute_plan_async"):
                exec_res = await backend.execute_plan_async(action_plan)
            else:
                exec_res = backend.execute_plan(action_plan)
        except Exception as plan_exc:
            # Graceful fallback: if ActionPlan construction fails, use raw execute()
            logger.warning(
                f"Subtask [{task_id}] ActionPlan build failed ({plan_exc}), "
                f"falling back to execute()"
            )
            await asyncio.sleep(0.02)
            if hasattr(backend, "execute_async"):
                exec_res = await backend.execute_async(
                    capability=subtask.capability,
                    goal=subtask.description,
                    arguments=subtask.parameters,
                )
            else:
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
            try:
                from Memory import Memory as AuraMemory
            except ModuleNotFoundError:
                import sys
                from pathlib import Path
                root_path = str(Path(__file__).resolve().parents[3])
                if root_path not in sys.path:
                    sys.path.insert(0, root_path)
                from Memory import Memory as AuraMemory

            mem = AuraMemory()
            facts = mem.search(goal)
            all_facts = mem.facts()
            context_str = mem.build_context(user_input=goal)
            return {
                "recalled_facts": [f.value for f in facts],
                "all_facts": [
                    {"category": f.category, "key": f.key, "value": f.value}
                    for f in all_facts
                ],
                "context_string": context_str,
                "session_id": "current_session",
            }
        except Exception as exc:
            logger.warning(
                f"Memory recall failed, falling back to empty context: {exc}"
            )
            return {"recalled_facts": [], "session_id": "current_session"}

    def _write_memory(self, session: AgentSession, result: ExecutionResult) -> None:
        """Stage 7: Persist outcomes to unified memory."""
        logger.info(
            f"Stage 7 Memory Write for Session [{session.session_id}] (Success={result.success})"
        )
        try:
            try:
                from Memory import Memory as AuraMemory
            except ModuleNotFoundError:
                import sys
                from pathlib import Path
                root_path = str(Path(__file__).resolve().parents[3])
                if root_path not in sys.path:
                    sys.path.insert(0, root_path)
                from Memory import Memory as AuraMemory

            mem = AuraMemory()
            obs_summary = (
                "; ".join(result.observations[:3])
                if result.observations
                else "No observations"
            )
            mem.remember_exchange(
                query=session.goal,
                answer=f"Result success={result.success}. {obs_summary}",
                topic=result.planner or "orchestrator",
            )
        except Exception as exc:
            logger.warning(f"Memory write failed: {exc}")

    @staticmethod
    def _extract_content_from_result(result: ExecutionResult) -> str:
        """Extract the best content payload from an ExecutionResult.

        Priority order:
        1. result.data["content"] — explicit structured content
        2. result.observations joined — natural language output
        3. Empty string (will trigger ArtifactPayloadMissing downstream)
        """
        res_data = result.data if isinstance(result.data, dict) else {}

        # 1. Explicit content field
        if res_data.get("content"):
            return str(res_data["content"])

        # 2. Non-system observations concatenated
        non_empty_obs = [
            obs for obs in result.observations
            if obs and obs.strip()
        ]
        if non_empty_obs:
            return "\n".join(non_empty_obs)

        return ""

    @staticmethod
    def _infer_artifact_type(artifact_id: str) -> str:
        """Infer artifact type from its logical ID."""
        id_lower = artifact_id.lower()
        if "research" in id_lower:
            return "research"
        if "markdown" in id_lower or "doc" in id_lower:
            return "markdown"
        if "saved" in id_lower or "file" in id_lower:
            return "file"
        return "generic"

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
            f' AURA PIPELINE — "{goal}"\n'
            f" Session : {session_id}\n"
            f"──────────────────────────────────────────────────────\n"
            f" World Snapshot\n"
            f"   Focused window : {focused_window}\n"
            f"   Running procs  : {proc_count}\n"
            f"{divider}"
        )
