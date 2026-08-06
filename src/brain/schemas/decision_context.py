"""
DecisionContext — Aura's Internal "Thought"
===========================================

Everything should revolve around this object.

Instead of:
    GoalAnalyzer → CapabilitySelector → Planner

Do:
    Goal → Memory → Context → Capabilities → Safety → Knowledge → Fusion → DecisionContext

Then:
    Planner → DecisionContext

This becomes Aura's internal "thought."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Goal:
    """The understood user goal."""

    description: str
    objective: str = ""
    sub_goals: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "objective": self.objective,
            "sub_goals": self.sub_goals,
            "entities": self.entities,
            "confidence": self.confidence,
        }


@dataclass
class Entity:
    """An entity mentioned in the user request."""

    name: str
    entity_type: str = "unknown"
    confidence: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "confidence": self.confidence,
            "attributes": self.attributes,
        }


@dataclass
class Confidence:
    """Per-domain confidence scores."""

    goal: float = 0.0
    entity: float = 0.0
    memory: float = 0.0
    capability: float = 0.0
    safety: float = 1.0

    def to_dict(self) -> dict[str, float]:
        return {
            "goal": self.goal,
            "entity": self.entity,
            "memory": self.memory,
            "capability": self.capability,
            "safety": self.safety,
        }

    @property
    def overall(self) -> float:
        """Weighted overall confidence."""
        return (
            self.goal * 0.3
            + self.entity * 0.2
            + self.memory * 0.1
            + self.capability * 0.3
            + self.safety * 0.1
        )

    @property
    def needs_clarification(self) -> bool:
        """Whether clarification is needed based on confidence."""
        return self.goal < 0.7 or self.entity < 0.5 or self.capability < 0.6


@dataclass
class SafetyAssessment:
    """Safety evaluation of the request."""

    safe: bool = True
    risk_level: str = "low"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "risk_level": self.risk_level,
            "reasons": self.reasons,
        }


@dataclass
class DecisionContext:
    """
    The fused decision context produced by the FusionEngine.

    This is the ONLY thing the Planner consumes.
    """

    goal: Goal = field(default_factory=Goal)
    objective: str = ""
    entities: list[Entity] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    world: dict[str, Any] = field(default_factory=dict)
    memory: list[dict[str, Any]] = field(default_factory=list)
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    safety: SafetyAssessment = field(default_factory=SafetyAssessment)
    confidence: Confidence = field(default_factory=Confidence)
    knowledge: dict[str, Any] = field(default_factory=dict)
    raw_input: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal.to_dict(),
            "objective": self.objective,
            "entities": [e.to_dict() for e in self.entities],
            "context": self.context,
            "world": self.world,
            "memory": self.memory,
            "capabilities": self.capabilities,
            "safety": self.safety.to_dict(),
            "confidence": self.confidence.to_dict(),
            "knowledge": self.knowledge,
            "raw_input": self.raw_input,
        }


__all__ = ["DecisionContext", "Goal", "Entity", "Confidence", "SafetyAssessment"]