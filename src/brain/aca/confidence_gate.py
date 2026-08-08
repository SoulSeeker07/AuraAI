"""
ConfidenceGate — Per-Domain Confidence Evaluation
==================================================

Don't use one confidence. Use multiple.

    Goal: 0.99
    Entity: 0.61
    Memory: 0.95
    Capability: 0.98

Now Aura can reason like this:

    "I understand the request.
     But I don't know WHICH Chrome window.
     Ask clarification."

That's much better than: Confidence = 0.82
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..schemas.decision_context import Confidence

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """The result of the confidence gate evaluation."""

    passed: bool
    confidence: Confidence
    clarification_needed: bool = False
    clarification_question: str = ""
    low_confidence_areas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "confidence": self.confidence.to_dict(),
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question,
            "low_confidence_areas": self.low_confidence_areas,
        }


class ConfidenceGate:
    """
    Evaluates per-domain confidence scores and decides whether
    to proceed, ask for clarification, or refuse.
    """

    # Thresholds for each domain
    THRESHOLDS = {
        "goal": 0.7,
        "entity": 0.5,
        "memory": 0.4,
        "capability": 0.6,
        "safety": 0.8,
    }

    def evaluate(self, confidence: Confidence) -> GateResult:
        """
        Evaluate the confidence scores.

        Args:
            confidence: Per-domain confidence scores.

        Returns:
            GateResult with pass/fail and clarification info.
        """
        low_areas: list[str] = []
        for domain, threshold in self.THRESHOLDS.items():
            score = getattr(confidence, domain, 0.0)
            if score < threshold:
                low_areas.append(domain)

        passed = len(low_areas) == 0
        clarification_needed = confidence.needs_clarification

        # Build clarification question
        question = ""
        if clarification_needed:
            if "entity" in low_areas:
                question = "I'm not sure which specific item you're referring to. Could you clarify?"
            elif "goal" in low_areas:
                question = "I'm not fully certain what you'd like me to do. Could you rephrase?"
            elif "capability" in low_areas:
                question = "I'm not sure I have the right capability for this. Could you clarify what you need?"
            else:
                question = "Could you provide more details?"

        logger.info(
            f"ConfidenceGate: passed={passed}, "
            f"low={low_areas}, clarification={clarification_needed}"
        )

        return GateResult(
            passed=passed,
            confidence=confidence,
            clarification_needed=clarification_needed,
            clarification_question=question,
            low_confidence_areas=low_areas,
        )


__all__ = ["ConfidenceGate", "GateResult"]
