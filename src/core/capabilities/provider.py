"""
M19 Capability Provider Interface
=================================
Location: src/core/capabilities/provider.py

Defines the abstract base contract for all domain capability providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.capabilities.models import Capability


class ICapabilityProvider(ABC):
    """Abstract interface implemented by all domain capability providers."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the unique domain identifier (e.g. 'desktop', 'coding', 'browser', 'memory', 'research', 'mcp')."""
        pass

    @abstractmethod
    def list_capabilities(self) -> list[Capability]:
        """List all capabilities supported by this domain provider."""
        pass

    @abstractmethod
    def get_capability(self, name: str) -> Capability | None:
        """Get a capability by name or None if not owned by this provider."""
        pass

    def has_capability(self, name: str) -> bool:
        """Check if this provider owns the capability."""
        return self.get_capability(name) is not None
