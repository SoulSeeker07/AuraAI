"""
Memory Planner
Location: src/core/planning/memory_planner.py

Planner for handling cognitive memory actions (remembering, recalling, forgetting).
"""

from typing import Any

from .base_planner import BasePlanner


class MemoryPlanner(BasePlanner):
    """
    Subsystem planner for Memory actions.
    """

    def can_handle(self, goal_text: str) -> bool:
        goal_lower = goal_text.lower()
        return any(
            w in goal_lower
            for w in [
                "remember",
                "recall",
                "forget",
                "preference",
                "my favorite",
                "my favourite",
            ]
        )

    def create_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "role": "memory",
            "capability": capability or "memory_write",
            "goal": goal_text,
            "parameters": parameters or {},
        }

    def optimize_plan(self, plan: Any) -> Any:
        return plan

    def execute_plan(self, plan: Any) -> Any:
        return plan

    def explain_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"description": "Memory Planner execution plan"}
