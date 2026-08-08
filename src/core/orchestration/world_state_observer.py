"""
World State Observer (Real-Time Perception Engine)
Location: src/core/orchestration/world_state_observer.py

Performs real-time physical observations across Desktop, Browser, System, and Storage
domains after every single action step to drive the closed-loop perception engine.
"""

from __future__ import annotations

import logging
from typing import Any

from .world_snapshot import WorldSnapshotProvider

logger = logging.getLogger(__name__)


class WorldStateObserver:
    """
    Perception engine capturing multi-domain world observations.
    """

    _instance: WorldStateObserver | None = None

    @classmethod
    def get_instance(cls) -> WorldStateObserver:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.snapshot_provider = WorldSnapshotProvider()

    async def observe_async(
        self, domain: str = "all", browser_adapter: Any | None = None
    ) -> dict[str, Any]:
        """
        Asynchronously capture real-time physical world snapshot across specified domain.
        """
        snap = self.snapshot_provider.snapshot()
        import time

        obs: dict[str, Any] = {
            "focused_window": snap.focused_window_title,
            "running_processes_count": len(snap.running_processes),
            "timestamp": getattr(snap, "timestamp", time.time()),
        }

        # Browser perception
        if (
            domain in ["browser", "all"]
            and browser_adapter
            and hasattr(browser_adapter, "_engine")
        ):
            engine = getattr(browser_adapter, "_engine", None)
            if engine and getattr(engine, "_page", None):
                try:
                    page = engine._page
                    obs["browser_url"] = page.url
                    obs["browser_title"] = await page.title()
                    obs["is_browser_active"] = getattr(engine, "is_active", False)
                except Exception as e:
                    logger.debug(
                        f"[WorldStateObserver] Browser perception warning: {e}"
                    )

        logger.debug(f"[WorldStateObserver] Captured observation: {obs}")
        return obs

    def observe_sync(self, domain: str = "all") -> dict[str, Any]:
        """Synchronous observation snapshot."""
        snap = self.snapshot_provider.snapshot()
        return {
            "focused_window": snap.focused_window_title,
            "running_processes_count": len(snap.running_processes),
            "timestamp": snap.timestamp,
        }
