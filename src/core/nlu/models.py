"""
NLU Perception Models
Location: src/core/nlu/models.py

Data models for the Natural Language Understanding perception layer.
NLU is pure perception ("What did the human mean?"), producing structured
representations for DMM and downstream planning.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NLUResult:
    """
    Structured perception result produced by NLUEngine.

    Attributes:
        raw_text: Original raw input text from the user.
        normalized_text: Cleaned, typo-corrected, shorthand-expanded text.
        intent_hint: Non-binding suggested intent (e.g. 'open_app', 'search', 'coding').
        entities: Extracted entities (app_name, target_file, query, url, etc.).
        confidence: Perception confidence score (0.0 to 1.0).
        is_ambiguous: True if perception confidence is low or key slots are missing.
        clarification_prompt: Suggested user prompt if clarification is needed.
        metadata: Diagnostic details (fast_path used, typos fixed, etc.).
    """

    raw_text: str
    normalized_text: str
    intent_hint: str = "chat"
    entities: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    is_ambiguous: bool = False
    clarification_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "intent_hint": self.intent_hint,
            "entities": self.entities,
            "confidence": self.confidence,
            "is_ambiguous": self.is_ambiguous,
            "clarification_prompt": self.clarification_prompt,
            "metadata": self.metadata,
        }
