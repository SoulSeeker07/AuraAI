"""
Browser World Model Provider
Location: src/brain/providers/browser_provider.py

Provides browser perception: open tabs, active URLs, domains, and browser states.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import Executor
from typing import Any

try:
    from browser.world_model import BrowserContext, BrowserStateProbe
except (ImportError, ModuleNotFoundError):
    try:
        from src.browser.world_model import BrowserContext, BrowserStateProbe
    except Exception:
        BrowserContext = None  # type: ignore
        BrowserStateProbe = None  # type: ignore
from .base import IWorldProvider, ProviderFact


class BrowserProvider(IWorldProvider):
    """
    World model provider for browser context perception.
    """

    def __init__(
        self,
        playwright_engine: Any = None,
        executor: Executor | None = None,
    ):
        self.playwright_engine = playwright_engine
        self._executor = executor

    @property
    def domain(self) -> str:
        return "browser"

    def _probe_sync(self) -> BrowserContext:
        """Synchronously probe browser state."""
        return BrowserStateProbe.probe_state(self.playwright_engine)

    async def get_state(self) -> dict[str, Any]:
        """Fetch full browser perception dictionary."""
        loop = asyncio.get_running_loop()
        if self._executor:
            ctx = await loop.run_in_executor(self._executor, self._probe_sync)
        else:
            ctx = self._probe_sync()

        return ctx.to_dict()

    async def query(self, entity: str) -> list[ProviderFact]:
        """
        Query browser domain for specific entities.
        
        Supported entity queries:
          - "active_tab" / "current_url"
          - "open_tabs" / "tabs"
          - "running_browsers" / "browsers"
        """
        facts: list[ProviderFact] = []
        entity_norm = entity.strip().lower()
        state = await self.get_state()

        if entity_norm in ("active_tab", "current_url", "tab", "all"):
            open_tabs = state.get("open_tabs", [])
            active_tab = open_tabs[0] if open_tabs else {}
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="active_tab",
                    value=active_tab.get("url", "") or active_tab.get("title", ""),
                )
            )

        if entity_norm in ("open_tabs", "tabs", "browser_tabs", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="open_tabs",
                    value=state.get("open_tabs", []),
                )
            )

        if entity_norm in ("running_browsers", "browsers", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="running_browsers",
                    value=state.get("running_browsers", []),
                )
            )

        return facts
