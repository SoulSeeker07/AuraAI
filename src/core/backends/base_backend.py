"""
Base Backend Adapter API
Abstract contract for all Aura execution backends (Desktop Engine, Groq, Gemini CLI, Antigravity CLI, Browser Engine).
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..planning.execution_result import ExecutionResult

if TYPE_CHECKING:
    from ..planning.action_plan import ActionPlan


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

    def execute_plan(self, plan: "ActionPlan") -> ExecutionResult:
        """
        Execute a structured ActionPlan on this backend.

        Default implementation is a compatibility shim that delegates to execute().
        Override in concrete backends to use ActionPlan directly for structured logging,
        replay, and typed argument extraction.

        Args:
            plan: Structured ActionPlan with typed fields

        Returns:
            ExecutionResult
        """
        return self.execute(
            capability=plan.capability,
            goal=plan.goal,
            arguments=plan.arguments,
        )
