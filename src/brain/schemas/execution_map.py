"""
ExecutionMap — Structured Machine-Readable Action Plan
======================================================

The Planner produces an ExecutionMap, not free-form instructions.

Every execution map should contain:
    goal, steps, verification, fallback, expected_result, confidence
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""

    engine: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:6]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "engine": self.engine,
            "action": self.action,
            "parameters": self.parameters,
        }


@dataclass
class FallbackOption:
    """A fallback strategy if a step fails."""

    trigger: str
    action: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "action": self.action,
            "description": self.description,
        }


@dataclass
class VerificationCriterion:
    """A verification criterion for the execution."""

    description: str
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "passed": self.passed,
        }


@dataclass
class ExecutionMap:
    """
    The structured output of the Planner.

    This is the ONLY thing the Planner produces.
    """

    goal: str
    steps: list[ExecutionStep] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    fallbacks: list[FallbackOption] = field(default_factory=list)
    expected_result: str = ""
    confidence: float = 0.0
    capabilities: list[str] = field(default_factory=list)
    map_id: str = field(default_factory=lambda: f"map_{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "verification": self.verification,
            "fallbacks": [f.to_dict() for f in self.fallbacks],
            "expected_result": self.expected_result,
            "confidence": self.confidence,
            "capabilities": self.capabilities,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionMap:
        """Reconstruct an ExecutionMap from a dict."""
        return cls(
            goal=data.get("goal", ""),
            steps=[
                ExecutionStep(
                    engine=s.get("engine", ""),
                    action=s.get("action", ""),
                    parameters=s.get("parameters", {}),
                    step_id=s.get("step_id", f"step_{uuid.uuid4().hex[:6]}"),
                )
                for s in data.get("steps", [])
            ],
            verification=data.get("verification", []),
            fallbacks=[
                FallbackOption(
                    trigger=f.get("trigger", ""),
                    action=f.get("action", ""),
                    description=f.get("description", ""),
                )
                for f in data.get("fallbacks", [])
            ],
            expected_result=data.get("expected_result", ""),
            confidence=data.get("confidence", 0.0),
            capabilities=data.get("capabilities", []),
            map_id=data.get("map_id", f"map_{uuid.uuid4().hex[:8]}"),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


__all__ = ["ExecutionMap", "ExecutionStep", "FallbackOption", "VerificationCriterion"]
