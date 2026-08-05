"""
Observation Model
Location: src/core/orchestration/observation.py

Standardized Observation model returned by all role planners, backends, and decision engines.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Observation:
    """
    Universal Observation model. All subsystems return Observations instead of raw dicts.
    """

    observation_id: str = field(default_factory=lambda: f"obs_{uuid.uuid4().hex[:8]}")
    obs_type: str = "general"  # general, research, desktop, coding, browser, system
    source: str = "unknown"  # Backend or Planner name
    confidence: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    content: str = ""
    attachments: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "obs_type": self.obs_type,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "content": self.content,
            "attachments": self.attachments,
            "metadata": self.metadata,
        }
