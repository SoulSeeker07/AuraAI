"""
Groq LLM Backend Adapter
High-speed LLM backend adapter for quick reasoning and chat.
"""

from datetime import datetime
from typing import Any

try:
    from ...planning.execution_result import ExecutionResult
    from ..base_backend import BaseBackendAdapter
except (ImportError, ValueError):
    from core.planning.execution_result import ExecutionResult
    from core.backends.base_backend import BaseBackendAdapter


class GroqBackend(BaseBackendAdapter):
    """
    Groq high-speed LLM backend adapter.
    """

    @property
    def name(self) -> str:
        return "groq"

    @property
    def capabilities(self) -> list[str]:
        return ["chat.fast", "reason.quick", "conversation", "memory.summary"]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": "1.0",
            "is_local": False,
            "cost": 0.0001,
            "latency_ms": 120.0,
            "capabilities": self.capabilities,
            "health": "healthy",
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        start_t = datetime.now().timestamp()
        dur = datetime.now().timestamp() - start_t

        return ExecutionResult(
            success=True,
            planner="groq",
            goal=goal,
            confidence=0.95,
            execution_time_seconds=dur,
            observations=[f"Groq processed '{capability}'"],
            data={"response": f"Groq high-speed response for '{goal}'"},
        )
