"""
Execution Monitor
Monitors real-time step progress, execution duration, and context events during DesktopPlan execution.
"""

from datetime import datetime
from typing import Any

from .desktop_step import DesktopStep


class ExecutionMonitor:
    """
    Monitors DesktopPlan execution metrics and events.
    """

    def __init__(self):
        self._step_timings: dict[str, float] = {}
        self._events: list[dict[str, Any]] = []

    def on_step_start(self, step: DesktopStep) -> None:
        """Record step start."""
        self._step_timings[step.step_id] = datetime.now().timestamp()

    def on_step_finish(
        self, step: DesktopStep, success: bool, error: str | None = None
    ) -> None:
        """Record step finish."""
        start = self._step_timings.get(step.step_id, datetime.now().timestamp())
        duration_ms = (datetime.now().timestamp() - start) * 1000.0
        self._events.append(
            {
                "step_id": step.step_id,
                "capability": step.capability,
                "success": success,
                "duration_ms": duration_ms,
                "error": error,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_summary(self) -> dict[str, Any]:
        """Get execution monitoring summary."""
        total_steps = len(self._events)
        successes = sum(1 for e in self._events if e["success"])
        total_time = sum(e["duration_ms"] for e in self._events)
        return {
            "total_steps": total_steps,
            "successful_steps": successes,
            "total_duration_ms": total_time,
            "events": self._events.copy(),
        }
