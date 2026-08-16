"""
Memory World Model Provider
Location: src/brain/providers/memory_provider.py

Provides cognitive memory perception: user preferences, past decisions, and session context.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Executor
from typing import Any

from .base import IWorldProvider, ProviderFact

logger = logging.getLogger(__name__)


class MemoryProvider(IWorldProvider):
    """
    World model provider for M17 Cognitive Memory access.
    """

    def __init__(
        self,
        memory_manager: Any = None,
        executor: Executor | None = None,
    ):
        self.memory_manager = memory_manager
        self._executor = executor

    @property
    def domain(self) -> str:
        return "memory"

    def _get_sync_memory_state(self) -> dict[str, Any]:
        """Synchronously query underlying memory store."""
        if not self.memory_manager:
            return {"preferences": {}, "decisions": [], "session_history": []}

        try:
            if hasattr(self.memory_manager, "get_all_preferences"):
                prefs = self.memory_manager.get_all_preferences()
            else:
                prefs = {}
            return {
                "preferences": prefs,
                "decisions": [],
                "session_history": [],
            }
        except Exception as e:
            logger.debug(f"[MemoryProvider] Error reading memory state: {e}")
            return {"preferences": {}, "decisions": [], "session_history": []}

    async def get_state(self) -> dict[str, Any]:
        """Fetch full memory perception dictionary."""
        loop = asyncio.get_running_loop()
        if self._executor:
            return await loop.run_in_executor(self._executor, self._get_sync_memory_state)
        return self._get_sync_memory_state()

    async def query(self, entity: str) -> list[ProviderFact]:
        """
        Query memory domain for specific entities.
        
        Supported entity queries:
          - "user_preferences" / "preferences"
          - "past_decisions" / "decisions"
          - "session_history" / "history"
        """
        facts: list[ProviderFact] = []
        entity_norm = entity.strip().lower()
        state = await self.get_state()

        if entity_norm in ("user_preferences", "preferences", "preference", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="user_preferences",
                    value=state.get("preferences", {}),
                )
            )

        if entity_norm in ("past_decisions", "decisions", "decision", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="past_decisions",
                    value=state.get("decisions", []),
                )
            )

        if entity_norm in ("session_history", "history", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="session_history",
                    value=state.get("session_history", []),
                )
            )

        return facts
