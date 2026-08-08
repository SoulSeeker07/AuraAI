"""
Cognitive Blackboard — Shared Working Memory
============================================

Every modern cognitive architecture benefits from a shared working memory.

Instead of every module calling each other, they all read/write one shared object.

    Context → Memory → Goal → Capabilities → Safety → Knowledge
    → DecisionContext → ExecutionMap → Verification → Reflection

The Blackboard dramatically reduces coupling between stages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Blackboard:
    """
    The shared working memory of the Aura Cognitive Architecture.

    All stages read from and write to this single object.
    """

    # ── Stage 0: Perception ────────────────────────────────────────────────
    user_input: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    world_state: dict[str, Any] = field(default_factory=dict)

    # ── Stage 1: Decision ──────────────────────────────────────────────────
    goal: dict[str, Any] = field(default_factory=dict)
    entities: list[dict[str, Any]] = field(default_factory=list)
    memory: list[dict[str, Any]] = field(default_factory=list)
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    safety: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    decision_context: dict[str, Any] | None = None

    # ── Stage 2: Planning ──────────────────────────────────────────────────
    execution_map: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None

    # ── Stage 3: Execution ─────────────────────────────────────────────────
    coordination: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None

    # ── Stage 4: Reflection & Learning ─────────────────────────────────────
    reflection: dict[str, Any] | None = None
    learned: list[dict[str, Any]] = field(default_factory=list)

    # ── Metadata ───────────────────────────────────────────────────────────
    session_id: str = ""
    timestamp: str = ""
    stage: str = "init"

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_input": self.user_input,
            "context": self.context,
            "world_state": self.world_state,
            "goal": self.goal,
            "entities": self.entities,
            "memory": self.memory,
            "capabilities": self.capabilities,
            "safety": self.safety,
            "knowledge": self.knowledge,
            "confidence": self.confidence,
            "decision_context": self.decision_context,
            "execution_map": self.execution_map,
            "validation": self.validation,
            "coordination": self.coordination,
            "verification": self.verification,
            "reflection": self.reflection,
            "learned": self.learned,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "stage": self.stage,
        }

    def set_stage(self, stage: str) -> None:
        """Update the current stage."""
        self.stage = stage
        logger.debug(f"Blackboard stage: {stage}")


__all__ = ["Blackboard"]
