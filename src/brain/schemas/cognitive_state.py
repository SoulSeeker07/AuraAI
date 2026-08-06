"""
CognitiveState — Aura's Working Consciousness
=============================================

Formerly "Blackboard". This is not just a data structure — it's
Aura's consciousness during a request.

Contains:
    Current Goal
    Current Thoughts (DecisionContext)
    Current Plan (ExecutionMap + TaskGraph)
    Observations (Context + World)
    Working Memory
    Verification
    Reflection
    Learned
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CognitiveState:
    """
    The shared working consciousness of the Aura Cognitive Architecture.

    All stages read from and write to this single object.
    """

    # ── Stage 0: Perception ────────────────────────────────────────────────
    user_input: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    world_state: dict[str, Any] = field(default_factory=dict)

    # ── Goal Manager ───────────────────────────────────────────────────────
    goal: dict[str, Any] = field(default_factory=dict)

    # ── Stage 1: Decision ──────────────────────────────────────────────────
    entities: list[dict[str, Any]] = field(default_factory=list)
    memory: list[dict[str, Any]] = field(default_factory=list)
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    safety: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    decision_context: dict[str, Any] | None = None  # Aura's "Thought"

    # ── Policy ─────────────────────────────────────────────────────────────
    policy: dict[str, Any] = field(default_factory=dict)

    # ── Stage 2: Planning ──────────────────────────────────────────────────
    strategy: dict[str, Any] = field(default_factory=dict)
    execution_map: dict[str, Any] | None = None
    task_graph: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None

    # ── Stage 3: Execution ─────────────────────────────────────────────────
    session: dict[str, Any] | None = None
    coordination: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None

    # ── Artifacts ──────────────────────────────────────────────────────────
    artifacts: list[dict[str, Any]] = field(default_factory=list)

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
            "policy": self.policy,
            "strategy": self.strategy,
            "execution_map": self.execution_map,
            "task_graph": self.task_graph,
            "validation": self.validation,
            "session": self.session,
            "coordination": self.coordination,
            "verification": self.verification,
            "artifacts": self.artifacts,
            "reflection": self.reflection,
            "learned": self.learned,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "stage": self.stage,
        }

    def set_stage(self, stage: str) -> None:
        """Update the current stage."""
        self.stage = stage
        logger.debug(f"CognitiveState stage: {stage}")


# Backward-compatible alias
Blackboard = CognitiveState

__all__ = ["CognitiveState", "Blackboard"]