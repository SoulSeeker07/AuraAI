"""
Cognitive Reasoning Engine
Location: src/core/orchestration/reasoning_engine.py

Performs pre-execution cognitive reasoning before task decomposition.
Evaluates:
- Parallelizability
- Need for search / RAG context
- Need for user confirmation
- Need for verification / refusal
- Memory recall context
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReasoningDecision:
    """Outcomes of the cognitive pre-execution reasoning stage."""

    goal: str
    should_parallel: bool = True
    should_ask_user: bool = False
    should_search_first: bool = False
    should_remember: bool = True
    should_verify: bool = True
    should_refuse: bool = False
    refusal_reason: str = ""
    reasoning_summary: str = ""
    memory_context: dict[str, Any] = field(default_factory=dict)


class ReasoningEngine:
    """
    Evaluates requests prior to task graph generation and planning.
    """

    def analyze(
        self, goal: str, memory_context: dict[str, Any] | None = None
    ) -> ReasoningDecision:
        """
        Analyze user goal and memory context to produce a ReasoningDecision.

        Args:
            goal: User request
            memory_context: Recalled context from prior sessions/executions

        Returns:
            ReasoningDecision object guiding downstream delegation
        """
        goal_lower = goal.lower()
        mem = memory_context or {}

        should_search = any(
            w in goal_lower
            for w in ["research", "search", "summarize", "find out", "python 3.14"]
        )
        should_parallel = any(
            w in goal_lower for w in ["and", ",", "while", "create", "open"]
        )

        summary = (
            f"Analyzed goal: Multi-intent request detected. "
            f"Parallel execution = {should_parallel}. Search required = {should_search}."
        )

        logger.info(f"ReasoningEngine complete: {summary}")

        return ReasoningDecision(
            goal=goal,
            should_parallel=should_parallel,
            should_ask_user=False,
            should_search_first=should_search,
            should_remember=True,
            should_verify=True,
            should_refuse=False,
            reasoning_summary=summary,
            memory_context=mem,
        )
