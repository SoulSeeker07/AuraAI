"""
Engine Interface — Every Engine Implements This
================================================

Instead of:
    BrowserEngine, DesktopEngine, ResearchEngine

Define:
    class Engine:
        def execute(step): ...
        def verify(result): ...

Every engine implements it. Then ACA doesn't care which engine exists.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class Engine(ABC):
    """Abstract contract for all execution engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The engine's name (e.g., 'desktop', 'browser', 'research')."""
        ...

    @abstractmethod
    def execute(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Execute an action.

        Args:
            action: The action to perform (e.g., 'launch_application').
            parameters: Action parameters.

        Returns:
            Result dict with 'success', 'observations', and optional 'data'.
        """
        ...

    @abstractmethod
    def verify(self, result: dict[str, Any]) -> bool:
        """
        Verify an execution result.

        Args:
            result: The result from execute().

        Returns:
            True if the result is verified.
        """
        ...


ALL_ENGINE_NAMES: tuple[str, ...] = (
    "desktop",
    "browser",
    "research",
    "engineering",
    "memory",
    "voice",
    "vision",
    "plugin",
    "workflow",
)


class EngineRegistry:
    """
    Registry of all available engines.

    No imports. No if statements. Just resolve by name.
    """

    _instance: EngineRegistry | None = None

    def __init__(self):
        self._engines: dict[str, Engine] = {}

    @classmethod
    def get_instance(cls) -> EngineRegistry:
        """Get global EngineRegistry singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset global EngineRegistry singleton instance."""
        cls._instance = None

    def register(self, engine: Any, name: str | None = None) -> None:
        """Register an engine, optionally with a custom alias name."""
        key = name or getattr(engine, "name", "unknown")
        self._engines[key] = engine
        if hasattr(engine, "name") and engine.name:
            self._engines[engine.name] = engine
        logger.info(f"EngineRegistry registered: {key}")

    def resolve(self, name: str) -> Engine | None:
        """Resolve an engine by name."""
        return self._engines.get(name)

    def list_engines(self) -> list[str]:
        """List all registered engine names."""
        return list(self._engines.keys())

    def has_engine(self, name: str) -> bool:
        """Check if an engine is registered."""
        return name in self._engines


__all__ = ["Engine", "EngineRegistry", "ALL_ENGINE_NAMES"]
