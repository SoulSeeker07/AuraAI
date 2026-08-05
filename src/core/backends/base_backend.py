"""
Base Backend Adapter API
Abstract contract for all Aura execution backends (Desktop Engine, Groq, Gemini CLI, Antigravity CLI, Browser Engine).
"""

from abc import ABC, abstractmethod
from typing import Any

from ..planning.execution_result import ExecutionResult


class BaseBackendAdapter(ABC):
    """
    Abstract contract implemented by all Aura backend execution adapters.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """List of capability strings supported by this backend."""
        pass

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """
        Describe backend metadata, capabilities, health, latency, and cost.

        Returns:
            Dictionary containing metadata.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if backend is healthy and available."""
        pass

    @abstractmethod
    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        """
        Execute a capability on this backend.

        Args:
            capability: Capability string
            goal: Goal description
            arguments: Execution parameters

        Returns:
            ExecutionResult
        """
        pass
