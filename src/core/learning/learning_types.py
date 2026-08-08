"""
Adaptive Learning Runtime Type Definitions
Location: src/core/learning/learning_types.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class RuleType(str, Enum):
    FACT = "fact"
    BEHAVIOR = "behavior"
    WORKFLOW = "workflow"
    PREFERENCE = "preference"


@dataclass(frozen=True)
class LearningRule:
    """
    Unified learned customization or behavior rule inside the Adaptive Learning Engine.
    """

    rule_id: str
    rule_type: RuleType
    trigger: str
    behavior: Any
    scope: str = "global"
    confidence: float = 1.0
    created_by: str = "user"
    verified: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type.value,
            "trigger": self.trigger,
            "behavior": self.behavior,
            "scope": self.scope,
            "confidence": self.confidence,
            "created_by": self.created_by,
            "verified": self.verified,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
