"""
World Model Provider Base Types
Location: src/brain/providers/base.py

Core abstractions for domain-specific perception providers.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderFact:
    """
    A verified fact about system state returned by a perception provider.
    """
    domain: str             # "desktop", "workspace", "browser", "symbol", "memory"
    entity: str             # target entity, e.g. "active_window", "git_branch", "class:App"
    value: Any              # string, dict, or structured object
    confidence: float = 1.0 # Reserved for future probabilistic ranking (defaults to 1.0)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "entity": self.entity,
            "value": self.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class QueryResult:
    """
    Aggregated response to a WorldModel query across one or more providers.
    """
    entity: str
    facts: list[ProviderFact] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "facts": [f.to_dict() for f in self.facts],
            "summary": self.summary,
        }


class IWorldProvider(ABC):
    """
    Abstract interface for all domain-specific world model perception providers.
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain identifier (e.g. 'desktop', 'workspace', 'browser', 'symbol', 'memory')."""
        pass

    @abstractmethod
    async def get_state(self) -> dict[str, Any]:
        """Fetch full domain state dictionary."""
        pass

    @abstractmethod
    async def query(self, entity: str) -> list[ProviderFact]:
        """Query domain for facts matching an entity or topic."""
        pass
