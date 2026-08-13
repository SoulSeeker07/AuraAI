"""
Domain Expert Capability Registry
Location: src/experts/expert_registry.py

Singleton registry for discovering and resolving Professional Expert Systems by domain.
Answers: "Which expert handles this domain?"
Does NOT make executive routing or policy decisions.
"""

from __future__ import annotations

import logging
from typing import Any

from .base_expert import BaseExpertSystem
from .models import DomainType

logger = logging.getLogger(__name__)


class DomainExpertRegistry:
    """
    Singleton registry for discovering and resolving Professional Expert Systems.
    """

    _instance: DomainExpertRegistry | None = None

    def __init__(self) -> None:
        self._experts: dict[str, BaseExpertSystem] = {}

    @classmethod
    def get_instance(cls) -> DomainExpertRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def register(self, expert: BaseExpertSystem, domain: DomainType | str | None = None) -> None:
        """Register a domain expert system instance."""
        if domain is None:
            key = expert.domain.value if hasattr(expert.domain, "value") else str(expert.domain)
        elif hasattr(domain, "value"):
            key = domain.value
        else:
            key = str(domain).lower().strip()

        self._experts[key] = expert
        logger.info(f"[DomainExpertRegistry] Registered expert '{expert.__class__.__name__}' for domain '{key}'")

    def resolve(self, domain: DomainType | str) -> BaseExpertSystem | None:
        """
        Resolve a domain expert system by DomainType or domain string.
        Returns None if domain is unknown / unsupported.
        """
        if hasattr(domain, "value"):
            key = domain.value
        else:
            key = str(domain).lower().strip()

        expert = self._experts.get(key)
        if not expert:
            logger.warning(f"[DomainExpertRegistry] No expert registered for domain '{key}'")
            return None
        return expert

    def has_expert(self, domain: DomainType | str) -> bool:
        """Check if an expert is registered for a domain."""
        return self.resolve(domain) is not None

    def list_domains(self) -> list[str]:
        """List all registered domain keys."""
        return list(self._experts.keys())
