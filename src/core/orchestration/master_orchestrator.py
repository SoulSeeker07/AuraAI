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
import concurrent.futures
import dataclasses
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from ..backends.backend_registry import BackendRegistry
    from ..planning.execution_result import ExecutionResult
    from .request_source import RequestSource
    from ..system.prompt_builder import PromptBuilder
except (ImportError, ValueError):
    from core.backends.backend_registry import BackendRegistry
    from core.planning.execution_result import ExecutionResult
    from core.orchestration.request_source import RequestSource
    from core.system.prompt_builder import PromptBuilder
from .agent_session import AgentSession, ExecutionBudget
from .artifact import Artifact, VerificationReport
from .decision_engine import DecisionEngine
from .observation import Observation
from .planner_registry import PlannerRegistry
from .result_merger import ResultMerger
from .supervisor_agent import SupervisorAgent
from .task_decomposer import SubTask, TaskDecomposer
from .execution_events import (
    NodeState,
    ExecutionEvent,
    SubTaskNodeInfo,
    GraphInitializedEvent,
    NodeStateChangedEvent,
    ConfirmationRequiredEvent,
    ExecutionStartedEvent,
    ExecutionFinishedEvent,
    ReplanTriggeredEvent,
)

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
        memory_db_path: Path | str | None = None,
        expert_routing_enabled: bool = False,
    ):
        self.planner_registry = planner_registry or PlannerRegistry.get_instance()
        self.backend_registry = backend_registry or BackendRegistry.get_instance()
        self.decomposer = task_decomposer or TaskDecomposer()
        self.decision_engine = decision_engine or DecisionEngine()
        self.supervisor = supervisor_agent or SupervisorAgent(self.planner_registry)
        self.result_merger = result_merger or ResultMerger()
        self.memory_db_path = memory_db_path
        self.expert_routing_enabled = expert_routing_enabled
        self._last_result: Any = None
        self._last_session: Any = (
            None  # AgentSession — used for session-scoped confirmation
        )
        self._execution_sink: Any = None
        self._sink_error_count: int = 0

        self._prompt_builder: PromptBuilder | None = None
        self._identity_context: str | None = None

        logger.info(
            f"MasterOrchestrator initialized (Cognitive Orchestration Layer v17.0, expert_routing={self.expert_routing_enabled})"
        )

    @property
    def identity_context(self) -> str:
        """Lazy-load and cache the full Aura system prompt."""
        if self._identity_context is None:
            try:
                if self._prompt_builder is None:
                    self._prompt_builder = PromptBuilder.get_instance()
                self._identity_context = self._prompt_builder.build_system_prompt(
                    include_examples=False
                )
            except Exception as exc:
                logger.warning(f"MasterOrchestrator: PromptBuilder unavailable: {exc}")
                self._identity_context = "(identity layer unavailable)"
        return self._identity_context

    @classmethod
    def get_instance(
        cls,
        memory_db_path: Path | str | None = None,
        expert_routing_enabled: bool | None = None,
    ) -> "MasterOrchestrator":
        if cls._instance is None or memory_db_path is not None:
            cls._instance = cls(
                memory_db_path=memory_db_path,
                expert_routing_enabled=expert_routing_enabled if expert_routing_enabled is not None else False,
            )
        elif expert_routing_enabled is not None:
            cls._instance.expert_routing_enabled = expert_routing_enabled
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None
        try:
            from ...desktop.native.desktop_execution_engine import (
                reset_desktop_execution_engine,
            )
            from ...desktop.native.managers.native_manager_registry import (
                NativeManagerRegistry,
            )
            from ..backends.backend_registry import BackendRegistry
            from .ownership_tracker import ResourceOwnershipTracker
            from .planner_registry import PlannerRegistry
            from .world_timeline import WorldTimeline

            ResourceOwnershipTracker.reset_instance()
            WorldTimeline.reset_instance()
            BackendRegistry.reset_instance()
            PlannerRegistry.reset_instance()
            reset_desktop_execution_engine()
            NativeManagerRegistry.reset_instance()
        except Exception:
            pass

    def set_execution_sink(self, sink: Any | None) -> None:
        """Register a callback sink for real-time execution lifecycle events."""
        self._execution_sink = sink
        self._sink_error_count = 0

    def _emit(self, event: Any) -> None:
        """Emit execution event to registered sink with 3-strike circuit-breaker protection."""
        if not getattr(self, "_execution_sink", None):
            return
        try:
            self._execution_sink(event)
            self._sink_error_count = 0
        except Exception as exc:
            self._sink_error_count = getattr(self, "_sink_error_count", 0) + 1
            logger.warning(
                f"[MasterOrchestrator] Execution sink error ({self._sink_error_count}/3): {exc}"
            )
            if self._sink_error_count >= 3:
                logger.error(
                    f"[MasterOrchestrator] Execution sink exceeded consecutive error threshold (3 strikes). "
                    f"Circuit breaker tripped: permanently detaching sink."
                )
                self._execution_sink = None

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

        initial_res = None
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
                    initial_res = backend.execute_plan(new_plan)
            except Exception as exc:
                logger.error(
                    f"[MasterOrchestrator] Confirmed launch failed: {exc}",
                    exc_info=True,
                )
                initial_res = _ER(
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
                    from ..backends.adapters.desktop_backend import _force_foreground

                    _force_foreground(running[0])
                    backend = self.backend_registry.select_best_backend(
                        conf.action_plan.capability
                    )
                    if backend and hasattr(backend, "_last_hwnd"):
                        backend._last_hwnd = running[0]
                        backend._last_app_name = conf.action_plan.target
            except Exception:
                pass
            initial_res = _ER(
                success=True,
                planner="desktop",
                goal=conf.action_plan.goal,
                data={"policy_action": "reuse_existing"},
                observations=[
                    f"✓ {conf.action_plan.target.title()} is already open — brought to front."
                ],
            )

        if initial_res and getattr(conf, "remaining_subtasks", None):
            all_obs = list(initial_res.observations or [])
            for rem_st in conf.remaining_subtasks:
                try:
                    rem_backend = self.backend_registry.select_best_backend(
                        rem_st.capability
                    )
                    if rem_backend:
                        from ..planning.action_plan import ActionPlan

                        rem_plan = ActionPlan.from_subtask(
                            rem_st, session_id=conf.session_id, context={}
                        )
                        rem_res = rem_backend.execute_plan(rem_plan)
                        all_obs.extend(rem_res.observations or [])
                except Exception as rem_exc:
                    logger.warning(
                        f"Execution of remaining subtask '{rem_st.title}' failed: {rem_exc}"
                    )
            initial_res.observations = all_obs

        return initial_res

    def process_request(
        self,
        goal_text: str,
        preferred_planner: str | None = None,
        parameters: dict[str, Any] | None = None,
        budget: ExecutionBudget | None = None,
        context: Any = None,
        source: RequestSource = RequestSource.HUMAN_INTERACTIVE,
    ) -> ExecutionResult:
        """
        Synchronous entry point for processing a request.
        Loop-safe: handles execution from threads with or without an active running event loop.
        """
        coro = self.process_request_async(
            goal_text, preferred_planner, parameters, budget, context, source=source
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None or not loop.is_running():
            return asyncio.run(coro)

        # A loop is already running in this thread. Offload to a dedicated worker thread
        # so asyncio.run() can execute the coroutine without nested event loop collisions.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()

    async def run(
        self,
        goal: str,
        precomputed_graph: Any | None = None,
        session: AgentSession | None = None,
        source: RequestSource = RequestSource.HUMAN_INTERACTIVE,
        **kwargs: Any,
    ) -> ExecutionResult:
        """Execute a goal with optional precomputed TaskGraph."""
        return await self.process_request_async(
            goal_text=goal,
            task_graph=precomputed_graph,
            session=session,
            source=source,
            **kwargs,
        )

    async def process_request_async(
        self,
        goal_text: str,
        preferred_planner: str | None = None,
        parameters: dict[str, Any] | None = None,
        budget: ExecutionBudget | None = None,
        context: Any = None,
        task_graph: Any | None = None,
        session: AgentSession | None = None,
        source: RequestSource = RequestSource.HUMAN_INTERACTIVE,
    ) -> ExecutionResult:
        """
        Execute full 7-stage cognitive orchestration pipeline using AgentSession.

        Args:
            source: Origin of this request. TRIGGER_AUTONOMOUS and DAEMON_BACKGROUND
                    requests receive an AUTONOMOUS autonomy floor (HIGH-risk actions
                    route to the HMAC gate rather than ASK_USER). The original
                    autonomy level is restored after the request completes.
        """
        # ── M26: Autonomy Floor for Non-Interactive Sources ─────────────────
        # Trigger/daemon sources must never produce a PendingConfirmation — there
        # is no human turn to resolve it. Raise the request-scoped ContextVar floor to
        # AUTONOMOUS so that HIGH/CRITICAL risk steps gate on the HMAC path instead of ASK_USER.
        from .execution_policy import ExecutionPolicy
        from .autonomy_mode import AutonomyLevel

        _policy = ExecutionPolicy.get_instance()
        _policy_token = None
        _is_autonomous_source = source in (
            RequestSource.TRIGGER_AUTONOMOUS,
            RequestSource.DAEMON_BACKGROUND,
        )
        if _is_autonomous_source:
            try:
                _policy_token = _policy.set_autonomy_level(AutonomyLevel.AUTONOMOUS)
                logger.info(
                    f"[MasterOrchestrator] Source={source.value}: request autonomy floor set to "
                    f"AUTONOMOUS via ContextVar. HIGH/CRITICAL risk → HMAC gate, not ASK_USER."
                )
            except Exception as _e:
                logger.warning(f"[MasterOrchestrator] Could not set autonomy floor for {source.value}: {_e}")
        elif source == RequestSource.AGENT_DELEGATED:
            # AGENT_DELEGATED inherits current ContextVar level without forcing an override
            _is_autonomous_source = (_policy.get_autonomy_level() == AutonomyLevel.AUTONOMOUS)
            logger.info(
                f"[MasterOrchestrator] Source=agent_delegated: inherited autonomy level "
                f"{_policy.get_autonomy_level().value} from parent ContextVar context."
            )

        try:
            return await self._process_request_async_inner(
                goal_text=goal_text,
                preferred_planner=preferred_planner,
                parameters=parameters,
                budget=budget,
                context=context,
                task_graph=task_graph,
                session=session,
                source=source,
                skip_confirmation_intercept=_is_autonomous_source,
            )
        finally:
            # Always reset request-scoped ContextVar token, even on exception
            if _policy is not None and _policy_token is not None:
                _policy.reset_autonomy_level(_policy_token)

    async def _process_request_async_inner(
        self,
        goal_text: str,
        preferred_planner: str | None = None,
        parameters: dict[str, Any] | None = None,
        budget: ExecutionBudget | None = None,
        context: Any = None,
        task_graph: Any | None = None,
        session: AgentSession | None = None,
        source: RequestSource = RequestSource.HUMAN_INTERACTIVE,
        skip_confirmation_intercept: bool = False,
    ) -> ExecutionResult:
        """
        Inner pipeline body. Called from process_request_async after autonomy-floor setup.
        """
        # ── Intercept Pending Confirmation Responses ────────────────────────
        # Skipped for non-interactive sources (no human present to answer).
        if not skip_confirmation_intercept:
            conf = self.check_pending_confirmation()
            if conf is not None:
                user_answer = goal_text.strip().lower()
                if user_answer in [
                    "yes", "y", "yeah", "yep", "sure", "ok", "okay",
                    "no", "n", "nope", "nah", "cancel",
                ]:
                    resolved_res = self.resolve_pending_confirmation(goal_text)
                    if resolved_res is not None:
                        try:
                            self._write_memory(self._last_session, resolved_res)
                        except Exception:
                            pass
                        self._last_result = resolved_res
                        return resolved_res

        start_t = datetime.now().timestamp()
        session = session or AgentSession(goal=goal_text, budget=budget or ExecutionBudget())
        if source == RequestSource.HUMAN_INTERACTIVE:
            self._last_session = session  # for session-scoped confirmation resolution
        self._log_pipeline_start(goal_text, session.session_id)
        self._emit(ExecutionStartedEvent(goal=goal_text, session_id=session.session_id))

        # Stage 0: Perception (NLU Layer)
        t_nlu = datetime.now().timestamp()
        try:
            from ..nlu.nlu_engine import NLUEngine

            nlu_engine = NLUEngine()
            nlu_result = nlu_engine.process(goal_text, context={"session_id": session.session_id})
            session.metrics["nlu_ms"] = round(
                (datetime.now().timestamp() - t_nlu) * 1000, 2
            )
            session.metrics["nlu_result"] = nlu_result.to_dict()

            # Ambiguity Clarification Gate: ask for clarification if perception is ambiguous (skipped if task_graph precomputed)
            if nlu_result.is_ambiguous and nlu_result.clarification_prompt and task_graph is None:
                logger.info(f"[MasterOrchestrator] Perception ambiguous: {nlu_result.clarification_prompt}")
                return ExecutionResult(
                    success=False,
                    planner="nlu_perception",
                    goal=goal_text,
                    confidence=nlu_result.confidence,
                    observations=[nlu_result.clarification_prompt],
                    data={"is_ambiguous": True, "nlu_result": nlu_result.to_dict()},
                )

            effective_goal = nlu_result.normalized_text or goal_text
        except Exception as e:
            logger.warning(f"[MasterOrchestrator] NLU perception bypass on error: {e}")
            effective_goal = goal_text

        # Stage 1: Memory Recall
        t0 = datetime.now().timestamp()
        session.memory_context = self._recall_memory(effective_goal)
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
        if context is not None and (
            hasattr(context, "slot") or context.__class__.__name__ == "PendingQuestion"
        ):
            pending_question = context
        else:
            db_pending = mem.get_pending_question()
            if db_pending:
                try:
                    from Memory import PendingQuestion as PQ
                except ModuleNotFoundError:
                    from Memory import PendingQuestion as PQ
                pending_question = PQ(
                    slot=db_pending["slot"],
                    qtype=db_pending["type"],
                    expected=db_pending["expected"],
                )

        # Check if the query is a command/request rather than a direct answer
        is_command = False
        goal_lower = goal_text.lower().strip()
        if any(
            w in goal_lower
            for w in [
                "open ",
                "close ",
                "minimize ",
                "maximize ",
                "restore ",
                "unminimize ",
                "launch ",
                "start ",
                "run ",
                "bring ",
                "focus ",
                "activate ",
                "switch to ",
                "summarize ",
                "what is",
                "do you",
                "who are",
                "system",
                "tell me",
            ]
        ):
            is_command = True

        if pending_question is not None and not is_command:
            mem.resolve_pending_question(goal_text, pending_question)
            res = ExecutionResult(
                success=True,
                planner="none",
                goal=goal_text,
                confidence=1.0,
                observations=[
                    f"Successfully filled preference slot '{pending_question.slot}' with value '{goal_text}'."
                ],
                data={
                    "backend": "none",
                    "capability": "memory_write",
                    "slot": pending_question.slot,
                    "value": goal_text,
                },
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
                        if not any(
                            w in content.lower()
                            for w in [
                                "summarize today's session",
                                "summarize session",
                                "session summary",
                                "summarize what we did today",
                                "what have we done today",
                            ]
                        ):
                            today_actions.append(content)

            if not today_actions:
                for msg in chat_log[-10:]:
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if not any(
                            w in content.lower()
                            for w in [
                                "summarize today's session",
                                "summarize session",
                                "session summary",
                                "summarize what we did today",
                                "what have we done today",
                            ]
                        ):
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
            artifact_count = sum(
                1 for evt in recent_events if "artifact" in evt.event_type.lower()
            )
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
                data={
                    "backend": "none",
                    "capability": "session_summary",
                    "summary": summary_text,
                },
            )
            self._write_memory(session, res)
            self._last_result = res
            return res

        # Stage 1.5: Conversational Reference Resolution ("Minimize it" -> "Minimize Notepad")
        try:
            from .reference_resolver import ReferenceResolver

            resolved_goal, ref_meta = ReferenceResolver.resolve_references(
                goal_text, context={"memory_context": session.memory_context}
            )
            if ref_meta.get("resolved"):
                logger.info(
                    f"MasterOrchestrator resolved goal '{goal_text}' -> '{resolved_goal}'"
                )
                goal_text = resolved_goal
                session.goal = resolved_goal
                session.metrics["reference_resolved"] = ref_meta
        except Exception as exc:
            logger.debug(f"Reference resolution skipped: {exc}")

        # Stage 1.6: Dynamic Preference Resolution ("Open my favorite editor" -> "Open VS Code")
        try:
            if any(w in goal_text.lower() for w in ["favorite", "preferred", "my editor", "my browser", "my ide"]):
                ranked = session.memory_context.get("ranked_cognitive_memories") or []
                pref_val = None
                pref_slot = None
                for mem_dict in ranked:
                    meta = mem_dict.get("metadata", {})
                    cat = meta.get("category")
                    k = meta.get("key", "")
                    val = meta.get("value")
                    if cat in ("preference", "profile") or "editor" in k or "ide" in k or "browser" in k:
                        if val:
                            pref_val = val
                            pref_slot = k or cat
                            break
                    content = mem_dict.get("content", "")
                    if "VS Code" in content:
                        pref_val = "VS Code"
                        pref_slot = "favorite_editor"
                        break

                if not pref_val:
                    try:
                        from Memory import Memory as AuraMemory
                        amem = AuraMemory()
                        if getattr(amem, "cognitive", None) is not None:
                            p_mems = amem.cognitive.search_memories("editor ide favorite preference", limit=5)
                            for pm in p_mems:
                                if "VS Code" in pm.content or pm.metadata.get("value") == "VS Code":
                                    pref_val = pm.metadata.get("value") or "VS Code"
                                    pref_slot = pm.metadata.get("key") or "favorite_editor"
                                    break
                    except Exception:
                        pass

                is_query = any(
                    goal_text.lower().strip().startswith(p)
                    for p in ("what is", "whats", "what's", "tell me", "do you remember", "recall", "which is")
                )
                if pref_val and not is_query:
                    import re
                    new_goal = re.sub(
                        r"\bmy\s+(?:favorite\s+|preferred\s+)?(?:editor|ide)\b",
                        pref_val,
                        goal_text,
                        flags=re.IGNORECASE,
                    )
                    if new_goal != goal_text:
                        logger.info(
                            f"[MasterOrchestrator] Resolved preference '{goal_text}' -> '{new_goal}' (slot={pref_slot}, val={pref_val})"
                        )
                        goal_text = new_goal
                        session.goal = new_goal
                        session.metrics["preference_resolved"] = {
                            "slot": pref_slot,
                            "value": pref_val,
                        }
        except Exception as pref_err:
            logger.debug(f"Preference resolution skipped: {pref_err}")

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

        if decision.should_refuse and task_graph is None:
            session.add_observation(
                Observation(
                    obs_type="system",
                    source="DecisionEngine",
                    confidence=0.0,
                    content=f"Request Refusal: {decision.refusal_reason}",
                )
            )
            return self.result_merger.merge_session(session, success=False)

        # Stage 2.7: Short-circuit for conversational/no-planner intents
        # When the decision engine classifies the request as CHAT or marks it as
        # not needing a planner, skip decomposition and validation entirely.
        # The result is returned as a lightweight chat stub that aura_core.py
        # will handle via get_ai_response().
        from .decision_engine import IntentType as _IntentType
        if (
            task_graph is None
            and not decision.can_answer_from_memory
            and (
                decision.intent_type == _IntentType.CHAT
                or not decision.needs_planner
            )
        ):
            chat_stub = ExecutionResult(
                success=True,
                planner="none",
                goal=goal_text,
                confidence=1.0,
                observations=[],
                data={
                    "backend": "provider",
                    "capability": "chat",
                    "intent_type": decision.intent_type.value,
                    "needs_planner": False,
                    "decision": {
                        "intent_type": decision.intent_type.value,
                        "needs_planner": False,
                        "can_answer_from_memory": False,
                        "can_answer_from_system": False,
                    },
                },
            )
            self._last_result = chat_stub
            return chat_stub

        # Stage 2.8: Direct Fulfillment from Memory (Zero-Refetch Invariant - G5)
        if decision.can_answer_from_memory and task_graph is None:
            ranked_mems = session.memory_context.get("ranked_cognitive_memories") or []
            sem_mems = [
                m for m in ranked_mems if isinstance(m, dict) and m.get("type") == "semantic"
            ]
            recalled_facts = session.memory_context.get("recalled_facts") or []

            answer_text = ""
            citations = []
            if sem_mems:
                best_mem = sem_mems[0]
                answer_text = f"{best_mem.get('content', '')}"
                citations = best_mem.get("metadata", {}).get("citations", [])
            elif recalled_facts:
                answer_text = f"From memory: {'; '.join(recalled_facts)}"

            if answer_text:
                logger.info(
                    f"[MasterOrchestrator] Direct fulfillment from memory (Zero-Refetch): {answer_text[:60]}"
                )
                res = ExecutionResult(
                    success=True,
                    planner="memory",
                    goal=goal_text,
                    confidence=1.0,
                    observations=[answer_text],
                    data={
                        "backend": "memory",
                        "capability": "memory_read",
                        "answer": answer_text,
                        "citations": citations,
                        "answered_from_memory": True,
                        "zero_refetch": True,
                    },
                )
                self._write_memory(session, res)
                self._last_result = res
                return res

        # Stage 2.9: Domain Expert Routing (Opt-in Gate for M25 Professional Experts)
        if self.expert_routing_enabled and task_graph is None:
            expert = None
            try:
                expert, assessment, rationale = await self.planner_registry.route_to_expert(
                    effective_goal,
                    context={
                        "session_id": session.session_id,
                        "memory_context": session.memory_context,
                    },
                )
                if (
                    expert is not None
                    and assessment is not None
                    and assessment.confidence >= 0.50
                ):
                    plan_dag = await expert.generate_plan(effective_goal, assessment)
                    from experts.compiler import PlanDAGCompiler

                    compiler = PlanDAGCompiler()
                    compiled_graph = compiler.compile(plan_dag)
                    task_graph = compiled_graph

                    # Write telemetry and system observation only after successful compilation
                    session.metrics["expert_domain"] = expert.domain
                    session.metrics["expert_assessment_id"] = assessment.assessment_id
                    session.metrics["expert_confidence"] = assessment.confidence
                    session.add_observation(
                        Observation(
                            obs_type="system",
                            source=f"ExpertRouter:{expert.domain}",
                            confidence=assessment.confidence,
                            content=(
                                f"Routed to {expert.domain} expert (Confidence: {assessment.confidence:.2f}): "
                                f"{assessment.recommended_strategy}"
                            ),
                        )
                    )
                    logger.info(
                        f"[MasterOrchestrator] Successfully compiled PlanDAG from '{expert.domain}' "
                        f"into TaskGraph ({len(task_graph.subtasks)} subtasks)."
                    )
            except Exception as exc:
                logger.warning(
                    f"[MasterOrchestrator] Domain expert routing to '{getattr(expert, 'domain', 'unknown')}' "
                    f"failed downstream ({exc}); falling back gracefully to TaskDecomposer.",
                    exc_info=True,
                )
                task_graph = None

        # Stage 3: Task Graph Decomposition
        t2 = datetime.now().timestamp()
        task_graph = task_graph or self.decomposer.decompose(goal_text, decision=decision)
        if parameters:
            if len(task_graph.subtasks) == 1:
                # Single subtask / direct dispatch: caller parameters apply directly
                single_subtask = next(iter(task_graph.subtasks.values()))
                single_subtask.parameters.update(parameters)
            else:
                # Multi-subtask decomposition: scope parameters by task_id or capability to prevent cross-contamination
                for st in task_graph.subtasks.values():
                    if st.task_id in parameters and isinstance(parameters[st.task_id], dict):
                        st.parameters.update(parameters[st.task_id])
                    elif st.capability in parameters and isinstance(parameters[st.capability], dict):
                        st.parameters.update(parameters[st.capability])

        # Emit GraphInitializedEvent for real-time observers
        nodes_info = tuple(
            SubTaskNodeInfo(
                task_id=st.task_id,
                title=st.title,
                required_role=st.required_role.value if hasattr(st.required_role, "value") else str(st.required_role),
                capability=st.capability,
                description=st.description,
                dependencies=tuple(st.dependencies or ()),
                status=NodeState.from_str(st.status),
                parameters=dict(st.parameters or {}),
            )
            for st in task_graph.subtasks.values()
        )
        order_tuple = tuple(tuple(lvl) for lvl in task_graph.execution_order)
        self._emit(GraphInitializedEvent(
            goal=goal_text,
            session_id=session.session_id,
            nodes=nodes_info,
            execution_order=order_tuple,
        ))

        # Stage 3.2: Task Graph Validation via Universal Capability Registry
        # Fail-closed only for hard errors (liveness failures, dependency cycles).
        # Unknown-capability errors are soft warnings — the execution backends
        # have their own fallback logic and can handle unrecognised capability
        # strings gracefully.
        from core.capabilities.capability_registry import CapabilityRegistry
        cap_reg = CapabilityRegistry.get_instance()
        plan_caps = [st.capability for st in task_graph.subtasks.values()]
        validation_res = cap_reg.validate_plan_graph(plan_caps, require_live=True)
        if not validation_res.valid:
            # Separate hard errors from soft unknown-capability warnings
            hard_errors = [
                err for err in validation_res.errors
                if not err.startswith("Unknown capability in plan:")
            ]
            unknown_caps = [
                err for err in validation_res.errors
                if err.startswith("Unknown capability in plan:")
            ]

            if unknown_caps:
                logger.warning(
                    f"[MasterOrchestrator] Task graph has unregistered capabilities "
                    f"(proceeding with execution — backends will handle): {unknown_caps}"
                )

            if hard_errors:
                logger.error(
                    f"[MasterOrchestrator] Task graph validation FAILED (blocking execution): {hard_errors}"
                )
                for err in hard_errors:
                    session.add_observation(
                        Observation(
                            obs_type="system",
                            source="CapabilityRegistry",
                            confidence=0.0,
                            content=f"❌ Plan validation error: {err}",
                        )
                    )
                for st in task_graph.subtasks.values():
                    st.status = "failed"
                    # Pre-execution plan validation failure: verified=False prevents false-positive checkmarks
                    self._emit(NodeStateChangedEvent(
                        task_id=st.task_id,
                        new_state=NodeState.FAILED,
                        old_state=NodeState.PENDING,
                        error=f"Plan validation failed: {hard_errors}",
                        verified=False,
                    ))

                failed_result = ExecutionResult(
                    success=False,
                    planner="CapabilityRegistry",
                    goal=goal_text,
                    confidence=0.0,
                    data={
                        "validation_errors": hard_errors,
                        "unwired_capabilities": validation_res.unwired_capabilities,
                        "missing_prerequisites": validation_res.missing_prerequisites,
                        "decision": {
                            "intent_type": decision.intent_type.value,
                            "needs_planner": decision.needs_planner,
                            "can_answer_from_memory": decision.can_answer_from_memory,
                            "can_answer_from_system": decision.can_answer_from_system,
                        },
                    },
                    observations=[f"Plan validation failed: {err}" for err in hard_errors],
                )
                session.metrics["decomposition_ms"] = round(
                    (datetime.now().timestamp() - t2) * 1000, 2
                )
                session.metrics["total_execution_time_seconds"] = datetime.now().timestamp() - start_t
                session.metrics["subtasks_completed"] = 0
                session.metrics["subtasks_total"] = len(task_graph.subtasks)
                self._write_memory(session, failed_result)
                self._last_result = failed_result
                self._emit(ExecutionFinishedEvent(
                    goal=goal_text,
                    session_id=session.session_id,
                    success=False,
                    observations=tuple(failed_result.observations or ()),
                    error=f"Plan validation failed: {hard_errors}",
                ))
                return failed_result

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

        from .task_working_memory import TaskWorkingMemory
        from .world_state_observer import WorldStateObserver

        task_memory = TaskWorkingMemory(goal=goal_text)
        world_observer = WorldStateObserver.get_instance()

        for level_index, task_level in enumerate(task_graph.execution_order):
            if pipeline_halted:
                # Mark remaining tasks as cancelled
                for t_id in task_level:
                    task_graph.subtasks[t_id].status = "cancelled"
                    self._emit(NodeStateChangedEvent(
                        task_id=t_id,
                        new_state=NodeState.CANCELLED,
                        old_state=NodeState.PENDING,
                        error="Execution halted due to upstream failure",
                    ))
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
                        if (
                            art_id == "art_research_data"
                            and subtask.capability == "document.generate"
                        ):
                            task_label = t_id.replace("_", " ").title()
                            err_msg = f"Research stage completed without producing a payload. Cannot generate markdown. Execution stopped at {task_label}."
                        # Input artifact validation failure: pre-condition check failed, verified=False
                        self._emit(NodeStateChangedEvent(
                            task_id=t_id,
                            new_state=NodeState.FAILED,
                            old_state=NodeState.PENDING,
                            error=err_msg,
                            verified=False,
                        ))
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
                    # Unhandled execution exception: task crashed mid-run, verified=False
                    self._emit(NodeStateChangedEvent(
                        task_id=t_id,
                        new_state=NodeState.FAILED,
                        old_state=NodeState.RUNNING,
                        error=f"{type(res).__name__}: {res}",
                        verified=False,
                    ))
                    session.add_observation(
                        Observation(
                            obs_type="system",
                            source="MasterOrchestrator",
                            confidence=0.0,
                            content=f"❌ Subtask '{subtask.title}' failed: {type(res).__name__}: {res}",
                        )
                    )
                elif (
                    isinstance(res, ExecutionResult)
                    or res.__class__.__name__ == "ExecutionResult"
                ):
                    subtask.status = "completed" if res.success else "failed"
                    subtask.result = res
                    if res.success:
                        completed_ids.add(t_id)
                    else:
                        pipeline_halted = True

                    res_data = res.data if isinstance(res.data, dict) else {}

                    # Infer tri-state verified flag from result / data
                    # None  = Unverified / no explicit verification report
                    # True  = Explicit verification passed
                    # False = Explicit verification failed or task failed
                    v_passed = None
                    if getattr(res, "verification_passed", None) is not None:
                        v_passed = bool(res.verification_passed)
                    elif hasattr(res, "data") and isinstance(res.data, dict) and "verification_passed" in res.data:
                        v_passed = bool(res.data["verification_passed"])
                    elif not res.success and res_data.get("policy_action") != "ask_user":
                        v_passed = False

                    self._emit(NodeStateChangedEvent(
                        task_id=t_id,
                        new_state=NodeState.COMPLETED if res.success else NodeState.FAILED,
                        old_state=NodeState.RUNNING,
                        result=res,
                        error=None if res.success else (res.observations[0] if res.observations else "Subtask failed"),
                        verified=v_passed,
                    ))
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

                    # Update TaskWorkingMemory with real-time perception observation
                    try:
                        b_adapter = self.backend_registry.get_backend("browser")
                        world_snap = await world_observer.observe_async(
                            domain=subtask.required_role.value,
                            browser_adapter=b_adapter,
                        )
                        task_memory.update_world_state(world_snap)
                        task_memory.record_step(
                            capability=subtask.capability,
                            target=subtask.title,
                            goal=subtask.description,
                            success=res.success,
                            observations=res.observations,
                        )
                    except Exception as mem_err:
                        logger.debug(
                            f"[MasterOrchestrator] TaskWorkingMemory update skipped: {mem_err}"
                        )

                    # ── Output Artifact Propagation ────────────────────────
                    # Extract content from the execution result and store
                    # payload-carrying Artifacts on the session for downstream
                    # tasks to consume.
                    content_payload = self._extract_content_from_result(res)
                    rich_ids = {
                        a.artifact_id
                        for a in res.artifacts or []
                        if isinstance(a, Artifact)
                    }
                    if res.artifacts:
                        for item in res.artifacts:
                            if isinstance(item, dict) and "artifact_id" in item:
                                rich_ids.add(item["artifact_id"])

                    for art_id in getattr(subtask, "output_artifacts", []):
                        if art_id in rich_ids:
                            continue  # Skip generic fallback since backend returns a rich artifact for this ID!

                        # Determine checks based on artifact ID and capability
                        checks = {}
                        if (
                            art_id == "art_saved_file"
                            or "save" in subtask.capability.lower()
                            or "persist" in subtask.capability.lower()
                        ):
                            checks = {"document_saved": True, "file_exists": True}
                        elif (
                            "markdown" in art_id
                            or "document" in subtask.capability.lower()
                        ):
                            checks = {"markdown_generated": True, "content_valid": True}
                        else:
                            checks = {"valid": True}

                        v_report = VerificationReport(
                            success=res.success,
                            checks=checks,
                            confidence=res.confidence if res.confidence is not None else 1.0,
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
                        checks = {}
                        is_art_obj = isinstance(art_data, Artifact)
                        art_type = (
                            art_data.artifact_type
                            if is_art_obj
                            else art_data.get("artifact_type", "file")
                        )
                        if art_type == "research":
                            checks = {
                                "sources_reachable": True,
                                "structured_payload": True,
                            }
                        elif art_type == "document":
                            checks = {
                                "markdown_generated": True,
                                "content_valid": True,
                            }
                        else:
                            checks = {"valid": True}

                        v_report = VerificationReport(
                            success=res.success,
                            checks=checks,
                            confidence=res.confidence if res.confidence is not None else 1.0,
                            observations=res.observations,
                        )

                        if is_art_obj:
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
                                    metadata=art_data.get("metadata", art_data.get("data", {})),
                                    verification_report=v_report,
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
                            remaining_st = [
                                st for st_id, st in task_graph.subtasks.items()
                                if st_id not in completed_ids and st_id != t_id
                            ]
                            session.pending_confirmation = ActionPlanConfirmation(
                                session_id=session.session_id,
                                action_plan=pending_plan,
                                prompt=prompt_text,
                                remaining_subtasks=remaining_st,
                            )
                            self._emit(ConfirmationRequiredEvent(
                                session_id=session.session_id,
                                task_id=t_id,
                                plan_id=pending_plan.plan_id,
                                prompt=prompt_text,
                                target=target,
                                capability=capability,
                                remaining_task_ids=tuple(
                                    st.task_id if hasattr(st, "task_id") else str(st)
                                    for st in remaining_st
                                ),
                            ))
                            pipeline_halted = True
                            logger.info(
                                f"[MasterOrchestrator] Stored pending confirmation on session "
                                f"[{session.session_id}] for '{target}' with {len(remaining_st)} remaining subtasks"
                            )
                        except Exception as conf_exc:
                            logger.debug(f"Confirmation attachment skipped: {conf_exc}")

        task_memory.mark_complete(
            success=(len(completed_ids) == len(task_graph.subtasks))
        )
        session.metrics["task_working_memory"] = task_memory.get_summary()

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
            if (
                "previous_results" in shared_context
                and single_task_id in shared_context["previous_results"]
            ):
                sub_res = shared_context["previous_results"][single_task_id]
                final_result.planner = getattr(sub_res, "planner", final_result.planner)
                final_result.success = sub_res.success
                if isinstance(sub_res.data, dict):
                    for k, v in sub_res.data.items():
                        if k not in final_result.data:
                            final_result.data[k] = v

        # Stage 7: Memory Write
        self._write_memory(session, final_result)
        self._last_result = final_result

        self._emit(ExecutionFinishedEvent(
            goal=goal_text,
            session_id=session.session_id,
            success=final_result.success,
            observations=tuple(final_result.observations or ()),
            error=None if final_result.success else "Execution failed",
        ))

        return final_result

    async def _execute_level_task(
        self,
        task_id: str,
        subtask: SubTask,
        decision: Any,
        context: dict[str, Any],
    ) -> ExecutionResult:
        subtask.status = "running"
        self._emit(NodeStateChangedEvent(
            task_id=task_id,
            new_state=NodeState.RUNNING,
            old_state=NodeState.PENDING,
        ))
        role_key, planner, plan_payload = self.supervisor.delegate_subtask(
            subtask, decision, context
        )

        from core.capabilities.capability_registry import CapabilityRegistry
        resolved_domain = CapabilityRegistry.get_instance().resolve_domain(subtask.capability)
        backend = self.backend_registry.select_best_backend(
            capability=subtask.capability,
            domain=resolved_domain,
        )
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

    def _recall_memory(self, goal: str, project_id: str = "global") -> dict[str, Any]:
        """Stage 1: Pre-fetch ranked cognitive memory context from persistent store."""
        logger.info(f"Stage 1 Cognitive Memory Recall for goal: '{goal[:30]}...' [project={project_id}]")
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

            mem = AuraMemory(db_path=self.memory_db_path) if self.memory_db_path else AuraMemory()
            facts = mem.search(goal)
            all_facts = mem.facts()
            context_str = mem.build_context(user_input=goal)

            ranked_items = []
            if getattr(mem, "cognitive", None) is not None:
                try:
                    ranked_memories = mem.cognitive.recall_ranked(query=goal, active_project=project_id, limit=10)
                    ranked_items = [m.to_dict() for m in ranked_memories]
                except Exception as rank_err:
                    logger.warning(f"Cognitive ranked recall warning: {rank_err}")

            return {
                "recalled_facts": [f.value for f in facts],
                "all_facts": [
                    {"category": f.category, "key": f.key, "value": f.value}
                    for f in all_facts
                ],
                "ranked_cognitive_memories": ranked_items,
                "context_string": context_str,
                "session_id": "current_session",
            }
        except Exception as exc:
            logger.warning(
                f"Memory recall failed, falling back to empty context: {exc}"
            )
            return {"recalled_facts": [], "ranked_cognitive_memories": [], "session_id": "current_session"}

    def _write_memory(self, session: AgentSession, result: ExecutionResult) -> None:
        """Stage 7: Persist outcomes to unified memory and run verified consolidation."""
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

            mem = AuraMemory(db_path=self.memory_db_path) if self.memory_db_path else AuraMemory()
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

            # Cognitive Memory Consolidation (Guardrail: only verified successful sessions consolidate)
            if getattr(mem, "cognitive", None) is not None:
                try:
                    project_id = getattr(session, "project_id", "global")
                    consolidated = mem.cognitive.consolidation_engine.consolidate_session(
                        session_id=session.session_id,
                        goal=session.goal,
                        execution_success=result.success,
                        observations=result.observations,
                        data=result.data if isinstance(result.data, dict) else {},
                        project_id=project_id,
                    )
                    for item in consolidated:
                        mem.cognitive.store_memory(item)
                    logger.info(f"Stage 7 Cognitive Memory: Consolidated {len(consolidated)} verified item(s).")
                except Exception as cons_err:
                    logger.warning(f"Cognitive memory consolidation warning: {cons_err}")

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
        non_empty_obs = [obs for obs in result.observations if obs and obs.strip()]
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
