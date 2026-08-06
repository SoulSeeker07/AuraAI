"""
ACABrain — Aura Cognitive Architecture Orchestrator
====================================================

Coordinates all stages through a shared Blackboard:

    Stage 0: Context & World Understanding
    Stage 1: DMM (FusionEngine + ConfidenceGate)
    Goal Manager (long-term goals)
    Stage 2: Planning & Strategy (Planner → TaskGraph)
    Policy Engine (governance)
    RuntimeSession (source of truth)
    Stage 3: Execution Coordination
    Artifact Manager (everything creates artifacts)
    Stage 4: Reflection & Learning
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..schemas.cognitive_state import CognitiveState
from ..schemas.runtime_session import RuntimeSession
from ..schemas.task_graph import TaskGraph, TaskNode
from ..schemas.artifact import Artifact
from .fusion_engine import FusionEngine
from .confidence_gate import ConfidenceGate
from .goal_manager import GoalManager, Goal
from .policy_engine import PolicyEngine, PolicyDecision
from .artifact_manager import ArtifactManager

logger = logging.getLogger(__name__)


@dataclass
class ACAResponse:
    """The final output of the ACA."""

    text: str
    success: bool
    blackboard: CognitiveState | None = None
    session: RuntimeSession | None = None
    goal: Goal | None = None
    artifacts: list[Artifact] = field(default_factory=list)
    clarification: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "success": self.success,
            "blackboard": self.blackboard.to_dict() if self.blackboard else None,
            "session": self.session.to_dict() if self.session else None,
            "goal": self.goal.to_dict() if self.goal else None,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "clarification": self.clarification,
            "metadata": self.metadata,
        }


class ACABrain:
    """
    The Aura Cognitive Architecture orchestrator.

    All stages read from and write to a shared Blackboard.
    Every execution belongs to a RuntimeSession.
    Long-term goals are tracked by the GoalManager.
    """

    def __init__(
        self,
        context_manager: Any | None = None,
        world_model: Any | None = None,
        goal_analyzer: Any | None = None,
        capability_selector: Any | None = None,
        fusion_engine: FusionEngine | None = None,
        confidence_gate: ConfidenceGate | None = None,
        goal_manager: GoalManager | None = None,
        policy_engine: PolicyEngine | None = None,
        planner: Any | None = None,
        validator: Any | None = None,
        coordinator: Any | None = None,
        verification: Any | None = None,
        artifact_manager: ArtifactManager | None = None,
        reflection: Any | None = None,
        learning: Any | None = None,
        llm_client: Any | None = None,
    ):
        self.context_manager = context_manager
        self.world_model = world_model
        self.goal_analyzer = goal_analyzer
        self.capability_selector = capability_selector
        self.fusion_engine = fusion_engine or FusionEngine()
        self.confidence_gate = confidence_gate or ConfidenceGate()
        self.goal_manager = goal_manager or GoalManager()
        self.policy_engine = policy_engine or PolicyEngine()
        self.planner = planner
        self.validator = validator
        self.coordinator = coordinator
        self.verification = verification
        self.artifact_manager = artifact_manager or ArtifactManager()
        self.reflection = reflection
        self.learning = learning
        self.llm_client = llm_client

        logger.info("ACABrain (Aura Cognitive Architecture) initialized")

    async def process(
        self, user_input: str, extra_context: dict[str, Any] | None = None
    ) -> ACAResponse:
        """
        Process a user request through all cognitive stages.

        Args:
            user_input: The user's raw text request.
            extra_context: Additional context from the caller.

        Returns:
            ACAResponse with final output, session, goal, and artifacts.
        """
        extra_context = extra_context or {}
        bb = CognitiveState()
        bb.user_input = user_input

        # ── Stage 0: Context & World Understanding ──────────────────────────
        bb.set_stage("stage0_perception")
        if self.context_manager:
            ctx = self.context_manager.collect(user_input, extra_context)
            bb.context = ctx.to_dict()
        if self.world_model:
            world = self.world_model.update()
            bb.world_state = world.to_dict()

        # ── Goal Manager: find or create long-term goal ─────────────────────
        goal = self.goal_manager.find_goal_for_request(user_input)
        if goal is None:
            goal = self.goal_manager.create_goal(description=user_input)
        bb.goal = goal.to_dict()

        # ── Stage 1: DMM (Decision Making Module) ───────────────────────────
        bb.set_stage("stage1_decision")

        # 1a. Goal Understanding
        goal_data: dict[str, Any] = {}
        ga = None
        if self.goal_analyzer:
            ga = self.goal_analyzer.analyze(user_input, bb.context)
            goal_data = ga.to_dict()
            bb.goal = goal_data

        # 1b. Capability Retrieval
        cap_data: list[dict[str, Any]] = []
        if self.capability_selector and ga:
            caps = self.capability_selector.select(ga)
            cap_data = [c.to_dict() for c in caps.capabilities]
            bb.capabilities = cap_data

        # 1c. Memory Retrieval
        memory_data: list[dict[str, Any]] = []
        if bb.context.get("memory_facts"):
            memory_data = bb.context["memory_facts"]
            bb.memory = memory_data

        # 1d. Safety Evaluation
        safety_data = {"safe": True, "risk_level": "low", "reasons": []}
        bb.safety = safety_data

        # 1e. Confidence Scores
        confidence_data = {
            "goal": 0.95,
            "entity": 0.90,
            "memory": 0.80 if memory_data else 0.50,
            "capability": 0.95 if cap_data else 0.50,
            "safety": 1.0,
        }
        bb.confidence = confidence_data

        # 1f. Fusion Engine — produce DecisionContext
        decision_context = self.fusion_engine.fuse(
            user_input=user_input,
            context=bb.context,
            world=bb.world_state,
            memory=memory_data,
            goal=goal_data,
            capabilities=cap_data,
            knowledge=bb.knowledge,
            safety=safety_data,
            confidence=confidence_data,
        )
        bb.decision_context = decision_context.to_dict()

        # 1g. Confidence Gate
        gate_result = self.confidence_gate.evaluate(decision_context.confidence)
        if gate_result.clarification_needed:
            logger.info(f"ACA needs clarification: {gate_result.clarification_question}")
            return ACAResponse(
                text=gate_result.clarification_question,
                success=False,
                blackboard=bb,
                clarification=gate_result.clarification_question,
                metadata={"stage": "stage1_decision", "gate": gate_result.to_dict()},
            )

        # ── Policy Engine: governance before planning ───────────────────────
        policy_decision = self.policy_engine.evaluate(decision_context)
        if not policy_decision.approved:
            return ACAResponse(
                text=f"Request blocked by policy: {policy_decision.reason}",
                success=False,
                blackboard=bb,
                goal=goal,
                metadata={"stage": "policy", "policy": policy_decision.to_dict()},
            )

        # ── Stage 2: Planning & Strategy ────────────────────────────────────
        bb.set_stage("stage2_planning")

        # 2a. Create RuntimeSession for this execution
        session = RuntimeSession(goal=user_input)
        session.start()

        # 2b. Planner produces TaskGraph (DAG, not linear)
        task_graph: TaskGraph | None = None
        execution_map: dict[str, Any] | None = None

        if self.planner:
            # Convert ExecutionMap to TaskGraph
            execution_map = self.planner.create_plan(decision_context)
            bb.execution_map = execution_map

            task_graph = TaskGraph(goal=execution_map.get("goal", user_input))
            for i, step in enumerate(execution_map.get("steps", [])):
                node_id = f"node_{i + 1}"
                task_graph.add_node(
                    engine=step.get("engine", ""),
                    action=step.get("action", ""),
                    parameters=step.get("parameters", {}),
                    description=f"{step.get('engine')}: {step.get('action')}",
                )
            session.set_task_graph(task_graph)

        # 2c. Validate
        validation = None
        if self.validator and execution_map:
            validation = self.validator.validate(execution_map)
            bb.validation = validation.to_dict() if hasattr(validation, "to_dict") else validation
            if not validation.valid:
                session.fail("Execution Map validation failed")
                return ACAResponse(
                    text=f"Could not create a valid execution plan: {validation.errors[0] if validation.errors else 'Unknown error'}",
                    success=False,
                    blackboard=bb,
                    session=session,
                    goal=goal,
                    metadata={"stage": "stage2_planning", "validation_failed": True},
                )

        # ── Stage 3: Execution Coordination ─────────────────────────────────
        bb.set_stage("stage3_execution")
        coordination = None
        verification = None

        if self.coordinator and execution_map:
            coordination = await self.coordinator.coordinate(execution_map)
            bb.coordination = coordination.to_dict() if hasattr(coordination, "to_dict") else coordination

            # Update session from coordination
            if coordination.success:
                session.complete()
            else:
                session.fail("Execution failed")

        if self.verification and execution_map and coordination:
            verification = self.verification.verify(execution_map, coordination)
            bb.verification = verification.to_dict() if hasattr(verification, "to_dict") else verification

        # ── Artifact Manager: collect everything Aura created ───────────────
        artifacts = self.artifact_manager.collect_from_execution(
            coordination, session_id=session.session_id
        )
        for art in artifacts:
            session.add_artifact(art.to_dict())
        bb.artifacts = [a.to_dict() for a in artifacts]

        # ── Stage 4: Reflection & Learning ──────────────────────────────────
        bb.set_stage("stage4_reflection")
        reflection = None
        learned: list[dict[str, Any]] = []

        if self.reflection and coordination:
            reflection = self.reflection.reflect(coordination)
            bb.reflection = reflection.to_dict() if hasattr(reflection, "to_dict") else reflection

        if self.learning:
            learned_items = self.learning.learn_from_interaction(
                user_input, coordination, verification, bb.context
            )
            learned = [i.to_dict() for i in learned_items]
            bb.learned = learned

        # ── Update Goal Manager ─────────────────────────────────────────────
        self.goal_manager.add_session(goal.goal_id, session.session_id)
        for art in artifacts[:5]:
            self.goal_manager.add_artifact(goal.goal_id, art.artifact_id)
        if verification and verification.passed:
            self.goal_manager.update_progress(goal.goal_id, 100.0)

        # ── Compose Response ────────────────────────────────────────────────
        response_text = self._compose_response(execution_map, coordination, verification, reflection, learned, artifacts)

        overall_success = (
            bool(verification.passed)
            if verification is not None
            else bool(coordination and coordination.success)
        )

        return ACAResponse(
            text=response_text,
            success=overall_success,
            blackboard=bb,
            session=session,
            goal=goal,
            artifacts=artifacts,
            metadata={"stage": "complete"},
        )

    def _compose_response(
        self,
        execution_map: dict[str, Any] | None,
        coordination: Any | None,
        verification: Any | None,
        reflection: Any | None,
        learned: list[dict[str, Any]],
        artifacts: list[Artifact],
    ) -> str:
        """Compose the final user-facing response."""
        lines: list[str] = []

        is_successful = (
            verification.passed
            if verification is not None
            else bool(coordination and coordination.success)
        )

        if is_successful:
            observations = []
            if coordination and hasattr(coordination, "step_results"):
                observations = [
                    obs
                    for step in coordination.step_results
                    for obs in step.observations
                ]
            if observations:
                lines.extend(observations)
            else:
                lines.append(f"✓ {execution_map.get('goal', 'Task completed') if execution_map else 'Task completed'}")

            if verification and hasattr(verification, "checks"):
                passed_checks = sum(1 for c in verification.checks if c.passed)
                lines.append(f"\n✓ Verification: {passed_checks}/{len(verification.checks)} checks passed")

            # Artifact summary
            if artifacts:
                types = ", ".join(a.artifact_type for a in artifacts[:5])
                lines.append(f"📦 Artifacts: {types}")
        else:
            if reflection and hasattr(reflection, "user_message") and reflection.user_message:
                lines.append(f"✗ {reflection.user_message}")
            else:
                lines.append(f"✗ Could not complete: {execution_map.get('goal', 'task') if execution_map else 'task'}")

            if reflection and hasattr(reflection, "recoveries"):
                for recovery in reflection.recoveries:
                    lines.append(f"  ↻ {recovery}")

        if learned:
            learned_types = ", ".join(i.get("item_type", "") for i in learned[:3])
            lines.append(f"\n📚 Learned: {learned_types}")

        return "\n".join(lines)

    def register_behavior_store(self, store: Any) -> None:
        """Register the behavior store for learning."""
        if self.learning and hasattr(self.learning, "register_behavior_store"):
            self.learning.register_behavior_store(store)

    def register_engine(self, engine: str, callback: Any) -> None:
        """Register a custom engine callback."""
        if self.coordinator and hasattr(self.coordinator, "register_engine"):
            self.coordinator.register_engine(engine, callback)

    def add_policy(self, policy: dict[str, Any]) -> None:
        """Add a custom policy."""
        self.policy_engine.add_policy(policy)

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client."""
        self.llm_client = client
        if self.planner and hasattr(self.planner, "set_llm_client"):
            self.planner.set_llm_client(client)


__all__ = ["ACABrain", "ACAResponse"]
