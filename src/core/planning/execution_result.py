"""
Universal Execution Result
Standardized result format returned by all Aura planners and execution subsystems.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .execution_trace import ExecutionTrace


@dataclass
class ExecutionResult:
    """
    Universal result returned by all planners (Desktop, Research, Coding, Browser).
    """

    success: bool
    planner: str  # 'desktop', 'research', 'coding', 'browser'
    goal: str
    confidence: float = 1.0
    execution_time_seconds: float = 0.0
    trace: ExecutionTrace | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    memory_updates: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    error: str | None = None

    def __post_init__(self) -> None:
        if self.error is None and not self.success:
            if self.data and isinstance(self.data, dict) and self.data.get("error"):
                self.error = str(self.data["error"])
            elif self.observations:
                for obs in self.observations:
                    if obs and isinstance(obs, str):
                        clean_obs = obs.lstrip("❌ ").strip()
                        if (
                            "failed" in obs.lower()
                            or "error" in obs.lower()
                            or "not found" in obs.lower()
                            or "exception" in obs.lower()
                            or "prohibited" in obs.lower()
                        ):
                            self.error = clean_obs
                            break
                if not self.error and self.observations:
                    self.error = self.observations[0].lstrip("❌ ").strip()
            elif self.warnings:
                self.error = self.warnings[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "planner": self.planner,
            "goal": self.goal,
            "confidence": self.confidence,
            "execution_time_seconds": self.execution_time_seconds,
            "trace": self.trace.to_dict() if self.trace else None,
            "artifacts": self.artifacts,
            "observations": self.observations,
            "warnings": self.warnings,
            "memory_updates": self.memory_updates,
            "data": self.data,
            "timestamp": self.timestamp,
            "error": self.error,
        }
