"""
Desktop Engine Backend Adapter
Wraps native DesktopExecutionEngine as a core backend adapter.
"""

from datetime import datetime
from typing import Any

from desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    get_desktop_execution_engine,
)

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class DesktopEngineBackend(BaseBackendAdapter):
    """
    Backend adapter for Desktop Execution Engine.
    """

    def __init__(self, engine: DesktopExecutionEngine | None = None):
        self.engine = engine or get_desktop_execution_engine()

    @property
    def name(self) -> str:
        return "desktop_engine"

    @property
    def capabilities(self) -> list[str]:
        return list(self.engine.registry._capabilities.keys())

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": "1.0",
            "is_local": True,
            "cost": 0.0,
            "latency_ms": 10.0,
            "capabilities": self.capabilities,
            "health": "healthy" if self.health_check() else "unhealthy",
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        start_t = datetime.now().timestamp()
        res = self.engine.execute(goal=goal, capability=capability, arguments=arguments)
        dur = datetime.now().timestamp() - start_t

        return ExecutionResult(
            success=res.success,
            planner="desktop",
            goal=goal,
            confidence=0.98 if res.success else 0.0,
            execution_time_seconds=dur,
            observations=[f"Executed native desktop capability '{capability}'"],
            warnings=[res.error] if res.error else [],
            data=res.data,
        )
