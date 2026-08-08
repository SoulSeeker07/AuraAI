"""
Memory Backend Adapter
Location: src/core/backends/adapters/memory_backend.py

Integrates the unified memory database as a registered Backend Adapter.
"""

import logging
from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class MemoryBackend(BaseBackendAdapter):
    """
    Backend adapter for memory operations.
    """

    @property
    def name(self) -> str:
        return "MemoryBackend"

    @property
    def capabilities(self) -> list[str]:
        return ["memory_write", "memory_read", "memory.write", "memory.read"]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 1.0,
            "cost": 0.0,
            "is_local": True,
            "version": "1.0.0",
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        logger = logging.getLogger(__name__)
        logger.info(
            f"MemoryBackend executing capability '{capability}' for goal: '{goal}'"
        )

        try:
            from Memory import Memory
        except ModuleNotFoundError:
            import sys
            from pathlib import Path

            root_path = str(Path(__file__).resolve().parents[4])
            if root_path not in sys.path:
                sys.path.insert(0, root_path)
            from Memory import Memory
        mem = Memory()

        if capability in ["memory_read", "memory.read"]:
            facts = mem.search(goal)
            if not facts:
                # Fallback: search key from goal
                goal_clean = goal.lower().replace(" ", "_")
                for cat in [
                    "preference",
                    "profile",
                    "skill",
                    "project",
                    "goal",
                    "important",
                ]:
                    for fact in mem.find(cat):
                        if (
                            fact.key in goal_clean
                            or goal_clean in fact.key
                            or fact.key.replace("_", "") in goal_clean
                        ):
                            facts.append(fact)
            obs = []
            if facts:
                obs.append(f"Found remembered facts: {facts}")
                direct_answers = []
                for f in facts:
                    direct_answers.append(
                        f"Your {f.key.replace('_', ' ')} is {f.value}."
                    )
                if direct_answers:
                    obs.append("\n".join(direct_answers))
            else:
                obs.append(
                    "I couldn't find any facts matching that query in my memory."
                )

            return ExecutionResult(
                success=True,
                planner="memory",
                goal=goal,
                confidence=1.0,
                observations=obs,
                data={
                    "backend": self.name,
                    "capability": capability,
                    "facts": [f.value for f in facts],
                },
            )

        # Extract facts from goal (memory_write)
        facts = mem.extract_facts(goal)
        for fact in facts:
            mem.upsert_fact(fact.category, fact.key, fact.value)

        obs = (
            [f"Successfully remembered facts: {facts}"]
            if facts
            else ["Successfully executed memory operation."]
        )

        return ExecutionResult(
            success=True,
            planner="memory",
            goal=goal,
            confidence=1.0,
            observations=obs,
            data={
                "backend": self.name,
                "capability": capability,
                "facts": [f.value for f in facts],
            },
        )


# Alias for backward/naming compatibility
MemoryBackendAdapter = MemoryBackend
