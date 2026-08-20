"""
Memory Backend Adapter
Location: src/core/backends/adapters/memory_backend.py

Integrates the unified memory database as a registered Backend Adapter.
"""

import logging
from typing import Any

try:
    from ...planning.execution_result import ExecutionResult
    from ..base_backend import BaseBackendAdapter
except (ImportError, ValueError):
    from core.planning.execution_result import ExecutionResult
    from core.backends.base_backend import BaseBackendAdapter


class MemoryBackend(BaseBackendAdapter):
    """
    Backend adapter for memory operations.
    """

    @property
    def name(self) -> str:
        return "MemoryBackend"

    @property
    def capabilities(self) -> list[str]:
        return [
            "memory_write",
            "memory_read",
            "memory.write",
            "memory.read",
            "memory.store",
            "memory.recall",
            "memory.search",
        ]

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

        args = arguments or {}

        # Read / Recall / Search Operations
        if capability in ["memory_read", "memory.read", "memory.recall", "memory.search"]:
            search_query = args.get("query") or args.get("key") or goal
            facts = mem.search(search_query)
            if not facts:
                # Fallback: search key from goal
                goal_clean = search_query.lower().replace(" ", "_")
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
                direct_answers = []
                for f in facts:
                    direct_answers.append(
                        f"Your {f.key.replace('_', ' ')} is {f.value}."
                    )
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

        # Write / Store Operations
        elif capability in ["memory_write", "memory.write", "memory.store"]:
            facts = []
            if "key" in args and "value" in args:
                cat = args.get("category", "preference")
                mem.upsert_fact(cat, str(args["key"]), str(args["value"]))
                from Memory import MemoryFact
                facts.append(MemoryFact(category=cat, key=str(args["key"]), value=str(args["value"])))

            extracted = mem.extract_facts(goal)
            for fact in extracted:
                mem.upsert_fact(fact.category, fact.key, fact.value)
                facts.append(fact)

            if facts:
                saved = [f"{f.key.replace('_', ' ')}: {f.value}" for f in facts]
                obs = [f"I remembered: {', '.join(saved)}."]
            else:
                obs = ["I noted that."]

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

        # Unknown / Unhandled Capability (Fail-Closed)
        return ExecutionResult(
            success=False,
            planner="memory",
            goal=goal,
            confidence=0.0,
            observations=[f"MemoryBackend does not support capability '{capability}'."],
            data={"backend": self.name, "capability": capability, "error": "unsupported_capability"},
        )


# Alias for backward/naming compatibility
MemoryBackendAdapter = MemoryBackend
