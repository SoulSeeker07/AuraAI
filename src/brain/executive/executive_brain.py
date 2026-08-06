"""
Executive Brain — The Cognitive Center of Aura
==============================================

The Executive Brain is the only component that "thinks."
Everything else simply executes.

Pipeline:
    Observe
        ↓
    Understand
        ↓
    Reason
        ↓
    Plan
        ↓
    Execute
        ↓
    Verify
        ↓
    Reflect
        ↓
    Learn
        ↓
    Respond
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .execution_map import ExecutionMap
from .dmm import DecisionMakingModule, ClarificationRequest
from .planner import ExecutivePlanner, ExecutionPlan
from .executor import ExecutiveExecutor, PlanResult
from .reflection import ReflectionEngine, ReflectionOutcome
from .learning import LearningEngine, LearnedItem

logger = logging.getLogger(__name__)


@dataclass
class BrainResponse:
    """The final output of the Executive Brain."""

    text: str
    success: bool
    execution_map: ExecutionMap | None = None
    plan: ExecutionPlan | None = None
    plan_result: PlanResult | None = None
    reflection: ReflectionOutcome | None = None
    learned: list[LearnedItem] = field(default_factory=list)
    clarification: ClarificationRequest | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "success": self.success,
            "execution_map": (
                self.execution_map.to_dict() if self.execution_map else None
            ),
            "plan": self.plan.to_dict() if self.plan else None,
            "plan_result": (
                self.plan_result.to_dict() if self.plan_result else None
            ),
            "reflection": (
                self.reflection.to_dict() if self.reflection else None
            ),
            "learned": [i.to_dict() for i in self.learned],
            "clarification": (
                self.clarification.to_dict() if self.clarification else None
            ),
            "metadata": self.metadata,
        }


class ExecutiveBrain:
    """
    The Executive Brain — the only intelligent component of Aura.

    Implements the Executive Thinking Loop:
        Observe → Understand → Reason → Plan → Execute → Verify → Reflect → Learn

    The Brain NEVER executes directly.
    It produces ExecutionMaps, delegates to the Planner, Executor,
    validates via Reflection, and improves via Learning.
    """

    def __init__(
        self,
        dmm: DecisionMakingModule | None = None,
        planner: ExecutivePlanner | None = None,
        executor: ExecutiveExecutor | None = None,
        reflection: ReflectionEngine | None = None,
        learning: LearningEngine | None = None,
        llm_client: Any | None = None,
    ):
        """
        Initialize the Executive Brain with its five layers.

        Args:
            dmm: Layer 1 — Decision Making Module
            planner: Layer 2 — Planner
            executor: Layer 3 — Executor
            reflection: Layer 4 — Reflection
            learning: Layer 5 — Learning
            llm_client: Optional Groq/LLM client
        """
        self.dmm = dmm or DecisionMakingModule(llm_client=llm_client)
        self.planner = planner or ExecutivePlanner()
        self.executor = executor or ExecutiveExecutor()
        self.reflection = reflection or ReflectionEngine()
        self.learning = learning or LearningEngine()
        self.llm_client = llm_client

        # Wire the LLM client to the executor for provider fallback
        if self.executor and llm_client is not None:
            self.executor.set_llm_client(llm_client)

        logger.info("ExecutiveBrain initialized (5-layer architecture)")

    # ── Public API ──────────────────────────────────────────────────────────

    async def process(
        self, user_input: str, context: dict[str, Any] | None = None
    ) -> BrainResponse:
        """
        Process a user request through the full Executive Thinking Loop.

        Args:
            user_input: The user's raw text request.
            context: Optional context dict (workspace state, memory, behavior store).

        Returns:
            BrainResponse with final output and full execution trace.
        """
        context = context or {}

        # ── 1. OBSERVE ──────────────────────────────────────────────────────
        logger.info(f"ExecutiveBrain observing request: {user_input[:50]}...")

        # ── 2. UNDERSTAND + REASON (DMM) ────────────────────────────────────
        logger.info("ExecutiveBrain: Understanding and reasoning...")
        dmm_output = self.dmm.analyze(user_input, context)

        # If the DMM needs clarification, ask the user
        if isinstance(dmm_output, ClarificationRequest):
            logger.info(f"ExecutiveBrain needs clarification: {dmm_output.question}")
            return BrainResponse(
                text=dmm_output.question,
                success=False,
                clarification=dmm_output,
                metadata={"stage": "understand", "needs_clarification": True},
            )

        execution_map: ExecutionMap = dmm_output
        logger.info(f"ExecutiveBrain produced {execution_map.log_summary()}")

        # ── 3. PLAN ─────────────────────────────────────────────────────────
        logger.info("ExecutiveBrain: Planning...")
        plan = self.planner.create_plan(execution_map)
        logger.info(f"ExecutiveBrain created plan [{plan.plan_id}] with {plan.total_steps} steps")

        # ── 4. EXECUTE ──────────────────────────────────────────────────────
        logger.info("ExecutiveBrain: Executing...")
        plan_result = await self.executor.execute_plan(plan)

        # ── 5. VERIFY (ExecutionMap verification criteria) ──────────────────
        verification_passed = self._verify(execution_map, plan_result)

        # ── 6. REFLECT ──────────────────────────────────────────────────────
        logger.info("ExecutiveBrain: Reflecting...")
        reflection_outcome = self.reflection.reflect(plan_result)

        # ── 7. LEARN ────────────────────────────────────────────────────────
        logger.info("ExecutiveBrain: Learning...")
        learned_items = self.learning.learn_from_interaction(
            user_input, plan_result, reflection_outcome, context
        )

        # ── 8. RESPOND ──────────────────────────────────────────────────────
        response_text = self._compose_response(
            execution_map, plan_result, reflection_outcome, learned_items, verification_passed
        )

        return BrainResponse(
            text=response_text,
            success=plan_result.success and verification_passed,
            execution_map=execution_map,
            plan=plan,
            plan_result=plan_result,
            reflection=reflection_outcome,
            learned=learned_items,
            metadata={
                "verification_passed": verification_passed,
                "stage": "complete",
            },
        )

    # ── Internal Helpers ────────────────────────────────────────────────────

    def _verify(self, execution_map: ExecutionMap, plan_result: PlanResult) -> bool:
        """Verify the execution against the map's success criteria."""
        if execution_map.verification.require_all:
            return plan_result.success and len(plan_result.failed_steps) == 0
        return plan_result.success

    def _compose_response(
        self,
        execution_map: ExecutionMap,
        plan_result: PlanResult,
        reflection: ReflectionOutcome,
        learned: list[LearnedItem],
        verification_passed: bool,
    ) -> str:
        """Compose the final user-facing response."""
        lines: list[str] = []

        if plan_result.success and verification_passed:
            # Success — compose from observations or goal
            observations = [
                obs
                for step in plan_result.step_results
                for obs in step.observations
            ]
            if observations:
                lines.extend(observations)
            else:
                lines.append(f"✓ {execution_map.expected_result}")

            # Add reflection note
            if reflection.reflections:
                lines.append(f"\n{reflection.reflections[0]}")
        else:
            # Failure — explain what happened
            if reflection.user_message:
                lines.append(f"✗ {reflection.user_message}")
            else:
                lines.append(
                    f"✗ Could not complete: {execution_map.goal}"
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
        """Register the behavior store for both DMM and Learning layers."""
        self.learning.register_behavior_store(store)
        self.dmm.register_rules_store(store)

    def register_callback(self, capability: str, callback: Any) -> None:
        """Register a custom engine callback for a capability."""
        self.executor.register_callback(capability, callback)

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for capability inference and provider fallback."""
        self.llm_client = client
        self.executor.set_llm_client(client)


__all__ = ["ExecutiveBrain", "BrainResponse"]