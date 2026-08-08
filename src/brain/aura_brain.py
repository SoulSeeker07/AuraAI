"""
AuraBrain — The Executive Runtime
=================================

Aura is not a chatbot. Aura is not an intent classifier.
Aura is an AI Operating System.

AuraBrain is the Executive Runtime that coordinates the full cognitive pipeline:

    User → Observe → Context Manager → World Model → Goal Analyzer
    → Capability Selector → Execution Map Generator → Execution Map Validator
    → Execution Coordinator → Verification → Reflection → Learning → Respond

The Golden Rule:
    The Executive Brain thinks. The Planner organizes.
    The Engines execute. Reflection validates. Learning improves.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .capability_selector import CapabilitySelection, CapabilitySelector
from .context_manager import ContextManager, ContextSnapshot
from .execution_coordinator import CoordinationResult, ExecutionCoordinator
from .execution_map_generator import ExecutionMapGenerator
from .execution_map_validator import ExecutionMapValidator, ValidationResult
from .goal_analyzer import GoalAnalysis, GoalAnalyzer
from .learning import LearnedItem, LearningEngine
from .reflection import ReflectionEngine, ReflectionOutcome
from .verification import VerificationEngine, VerificationReport
from .world_model import WorldModel, WorldState

logger = logging.getLogger(__name__)


@dataclass
class AuraBrainResponse:
    """The final output of the AuraBrain Executive Runtime."""

    text: str
    success: bool
    context: ContextSnapshot | None = None
    world_state: WorldState | None = None
    goal_analysis: GoalAnalysis | None = None
    capability_selection: CapabilitySelection | None = None
    execution_map: dict[str, Any] | None = None
    validation: ValidationResult | None = None
    coordination: CoordinationResult | None = None
    verification: VerificationReport | None = None
    reflection: ReflectionOutcome | None = None
    learned: list[LearnedItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "success": self.success,
            "context": self.context.to_dict() if self.context else None,
            "world_state": self.world_state.to_dict() if self.world_state else None,
            "goal_analysis": (
                self.goal_analysis.to_dict() if self.goal_analysis else None
            ),
            "capability_selection": (
                self.capability_selection.to_dict()
                if self.capability_selection
                else None
            ),
            "execution_map": self.execution_map,
            "validation": self.validation.to_dict() if self.validation else None,
            "coordination": self.coordination.to_dict() if self.coordination else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "reflection": self.reflection.to_dict() if self.reflection else None,
            "learned": [i.to_dict() for i in self.learned],
            "metadata": self.metadata,
        }


class AuraBrain:
    """
    The Executive Runtime of Aura.

    This is the ONLY intelligent component. Everything else is deterministic.

    Pipeline:
        1. Observe — collect context and world state
        2. Understand — analyze goals
        3. Reason — select capabilities
        4. Plan — generate execution map
        5. Validate — never trust the LLM blindly
        6. Execute — coordinate engines
        7. Verify — check outcomes
        8. Reflect — self-evaluate
        9. Learn — conservative learning
        10. Respond — compose output
    """

    def __init__(
        self,
        context_manager: ContextManager | None = None,
        world_model: WorldModel | None = None,
        goal_analyzer: GoalAnalyzer | None = None,
        capability_selector: CapabilitySelector | None = None,
        execution_map_generator: ExecutionMapGenerator | None = None,
        execution_map_validator: ExecutionMapValidator | None = None,
        execution_coordinator: ExecutionCoordinator | None = None,
        verification_engine: VerificationEngine | None = None,
        reflection_engine: ReflectionEngine | None = None,
        learning_engine: LearningEngine | None = None,
        llm_client: Any | None = None,
    ):
        self.context_manager = context_manager or ContextManager()
        self.world_model = world_model or WorldModel()
        self.goal_analyzer = goal_analyzer or GoalAnalyzer()
        self.capability_selector = capability_selector or CapabilitySelector()
        self.execution_map_generator = execution_map_generator or ExecutionMapGenerator(
            llm_client=llm_client
        )
        self.execution_map_validator = (
            execution_map_validator or ExecutionMapValidator()
        )
        self.execution_coordinator = execution_coordinator or ExecutionCoordinator()
        self.verification_engine = verification_engine or VerificationEngine()
        self.reflection_engine = reflection_engine or ReflectionEngine()
        self.learning_engine = learning_engine or LearningEngine()
        self.llm_client = llm_client

        if self.execution_coordinator and llm_client is not None:
            self.execution_coordinator.set_llm_client(llm_client)

        logger.info("AuraBrain Executive Runtime initialized")

    # ── Public API ──────────────────────────────────────────────────────────

    async def process(
        self, user_input: str, extra_context: dict[str, Any] | None = None
    ) -> AuraBrainResponse:
        """
        Process a user request through the full Executive Runtime pipeline.

        Args:
            user_input: The user's raw text request.
            extra_context: Additional context from the caller.

        Returns:
            AuraBrainResponse with final output and full execution trace.
        """
        extra_context = extra_context or {}

        # ── 1. OBSERVE ──────────────────────────────────────────────────────
        logger.info(f"AuraBrain observing: {user_input[:50]}...")
        context = self.context_manager.collect(user_input, extra_context)
        world_state = self.world_model.update()

        # ── 2. UNDERSTAND (Goal Analyzer) ───────────────────────────────────
        logger.info("AuraBrain: Analyzing goals...")
        goal_analysis = self.goal_analyzer.analyze(user_input, context.to_dict())

        # ── 3. REASON (Capability Selector) ─────────────────────────────────
        logger.info("AuraBrain: Selecting capabilities...")
        capability_selection = self.capability_selector.select(goal_analysis)

        # ── 4. PLAN (Execution Map Generator) ───────────────────────────────
        logger.info("AuraBrain: Generating execution map...")
        execution_map = self.execution_map_generator.generate(
            user_input, context, world_state, goal_analysis, capability_selection
        )

        # ── 5. VALIDATE (Execution Map Validator) ───────────────────────────
        logger.info("AuraBrain: Validating execution map...")
        validation = self.execution_map_validator.validate(execution_map)

        if not validation.valid:
            logger.warning(f"Execution Map validation failed: {validation.errors}")
            return AuraBrainResponse(
                text=f"Could not create a valid execution plan: {validation.errors[0] if validation.errors else 'Unknown error'}",
                success=False,
                context=context,
                world_state=world_state,
                goal_analysis=goal_analysis,
                capability_selection=capability_selection,
                execution_map=execution_map,
                validation=validation,
                metadata={"stage": "validate", "failed": True},
            )

        # ── 6. EXECUTE (Execution Coordinator) ──────────────────────────────
        logger.info("AuraBrain: Coordinating execution...")
        coordination = await self.execution_coordinator.coordinate(execution_map)

        # ── 7. VERIFY (Verification Engine) ─────────────────────────────────
        logger.info("AuraBrain: Verifying outcome...")
        verification = self.verification_engine.verify(execution_map, coordination)

        # ── 8. REFLECT (Reflection Engine) ──────────────────────────────────
        logger.info("AuraBrain: Reflecting...")
        reflection = self.reflection_engine.reflect(coordination)

        # ── 9. LEARN (Conservative Learning) ────────────────────────────────
        logger.info("AuraBrain: Learning...")
        learned = self.learning_engine.learn_from_interaction(
            user_input, coordination, verification, context.to_dict()
        )

        # ── 10. RESPOND ─────────────────────────────────────────────────────
        response_text = self._compose_response(
            execution_map, coordination, verification, reflection, learned
        )

        return AuraBrainResponse(
            text=response_text,
            success=verification.passed,
            context=context,
            world_state=world_state,
            goal_analysis=goal_analysis,
            capability_selection=capability_selection,
            execution_map=execution_map,
            validation=validation,
            coordination=coordination,
            verification=verification,
            reflection=reflection,
            learned=learned,
            metadata={"stage": "complete"},
        )

    # ── Response Composition ────────────────────────────────────────────────

    def _compose_response(
        self,
        execution_map: dict[str, Any],
        coordination: CoordinationResult,
        verification: VerificationReport,
        reflection: ReflectionOutcome,
        learned: list[LearnedItem],
    ) -> str:
        """Compose the final user-facing response."""
        lines: list[str] = []

        if verification.passed:
            # Success — compose from observations
            observations = [
                obs for step in coordination.step_results for obs in step.observations
            ]
            if observations:
                lines.extend(observations)
            else:
                lines.append(f"✓ {execution_map.get('goal', 'Task completed')}")

            # Add verification summary
            passed_checks = sum(1 for c in verification.checks if c.passed)
            lines.append(
                f"\n✓ Verification: {passed_checks}/{len(verification.checks)} checks passed"
            )
        else:
            # Failure — explain what happened
            if reflection.user_message:
                lines.append(f"✗ {reflection.user_message}")
            else:
                lines.append(
                    f"✗ Could not complete: {execution_map.get('goal', 'task')}"
                )

            # Add recovery suggestions
            for recovery in reflection.recoveries:
                lines.append(f"  ↻ {recovery}")

        # Learning confirmation
        if learned:
            learned_types = ", ".join(i.item_type for i in learned[:3])
            lines.append(f"\n📚 Learned: {learned_types}")

        return "\n".join(lines)

    # ── Configuration ───────────────────────────────────────────────────────

    def register_behavior_store(self, store: Any) -> None:
        """Register the behavior store for learning."""
        self.learning_engine.register_behavior_store(store)

    def register_engine(self, engine: str, callback: Any) -> None:
        """Register a custom engine callback."""
        self.execution_coordinator.register_engine(engine, callback)

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for execution map generation."""
        self.llm_client = client
        self.execution_map_generator.llm_client = client
        self.execution_coordinator.set_llm_client(client)


__all__ = ["AuraBrain", "AuraBrainResponse"]
