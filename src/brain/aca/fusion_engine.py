"""
FusionEngine — The Brain Inside the Brain
=========================================

Takes:
    Goal, Memory, Context, World, Knowledge, Capabilities, Safety

Produces:
    DecisionContext

Nothing else should know about the individual retrieval systems.
Planner shouldn't call Memory. Planner shouldn't call Context.
Planner shouldn't call WorldModel. Everything comes through Fusion.
"""

from __future__ import annotations

import logging
from typing import Any

from ..schemas.thought import (
    Thought,
    Goal,
    Entity,
    Confidence,
    SafetyAssessment,
)

logger = logging.getLogger(__name__)


class FusionEngine:
    """
    Fuses all retrieval systems into a single DecisionContext.

    This is the ONLY way to produce a DecisionContext.
    """

    def fuse(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
        world: dict[str, Any] | None = None,
        memory: list[dict[str, Any]] | None = None,
        goal: dict[str, Any] | None = None,
        capabilities: list[dict[str, Any]] | None = None,
        knowledge: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
        confidence: dict[str, float] | None = None,
    ) -> Thought:
        """
        Fuse all inputs into a single DecisionContext.

        Args:
            user_input: The user's raw request.
            context: Context snapshot from Context Manager.
            world: World state from World Model.
            memory: Memory facts.
            goal: Goal analysis.
            capabilities: Capability selection.
            knowledge: Knowledge base.
            safety: Safety assessment.
            confidence: Per-domain confidence scores.

        Returns:
            Thought — Aura's internal reasoning state.
        """
        context = context or {}
        world = world or {}
        memory = memory or []
        goal = goal or {}
        capabilities = capabilities or []
        knowledge = knowledge or {}
        safety = safety or {}
        confidence = confidence or {}

        # ── Build Goal ──────────────────────────────────────────────────────
        goal_obj = Goal(
            description=goal.get("primary_goal", user_input),
            objective=goal.get("objective", ""),
            sub_goals=goal.get("sub_goals", []),
            entities=goal.get("entities", []),
            confidence=confidence.get("goal", 0.0),
        )

        # ── Build Entities ──────────────────────────────────────────────────
        entities: list[Entity] = []
        for entity_name in goal.get("entities", []):
            entities.append(
                Entity(
                    name=entity_name,
                    entity_type="unknown",
                    confidence=confidence.get("entity", 0.0),
                )
            )

        # ── Build Safety ────────────────────────────────────────────────────
        safety_obj = SafetyAssessment(
            safe=safety.get("safe", True),
            risk_level=safety.get("risk_level", "low"),
            reasons=safety.get("reasons", []),
        )

        # ── Build Confidence ────────────────────────────────────────────────
        confidence_obj = Confidence(
            goal=confidence.get("goal", 0.0),
            entity=confidence.get("entity", 0.0),
            memory=confidence.get("memory", 0.0),
            capability=confidence.get("capability", 0.0),
            safety=confidence.get("safety", 1.0),
        )

        # ── Build DecisionContext ───────────────────────────────────────────
        decision_context = Thought(
            goal=goal_obj,
            objective=goal.get("objective", ""),
            entities=entities,
            context=context,
            world=world,
            memory=memory,
            capabilities=capabilities,
            safety=safety_obj,
            confidence=confidence_obj,
            knowledge=knowledge,
            raw_input=user_input,
        )

        logger.info(
            f"FusionEngine produced Thought: "
            f"goal='{goal_obj.description}', "
            f"entities={len(entities)}, "
            f"capabilities={len(capabilities)}, "
            f"confidence={confidence_obj.overall:.2f}"
        )

        return decision_context


__all__ = ["FusionEngine"]