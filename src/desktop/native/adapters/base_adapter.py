"""
Base Native Adapter Framework

Abstract base class for all hardware/API adapters in Aura desktop subsystem.
Decouples native managers from specific Windows APIs or third-party libraries
(e.g., PyCAW, WMI, WinMM, CoreAudio, Bluetooth).
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseNativeAdapter(ABC):
    """
    Abstract base class for native system adapters.

    All hardware/API adapters implement this contract to provide interchangeable
    backends with automatic fallback support.
    """

    NAME: str = "base_adapter"
    PRIORITY: int = 100

    def __init__(self):
        """Initialize adapter."""
        self._available: bool | None = None

    @property
    def name(self) -> str:
        """Get adapter name."""
        return getattr(self, "NAME", self.__class__.__name__.lower())

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this adapter backend is available on the current system.

        Returns:
            True if all required libraries and APIs are functional.
        """
        raise NotImplementedError

    def get_details(self) -> dict[str, Any]:
        """
        Get diagnostic details for this adapter.

        Returns:
            Dict containing adapter state, priority, and availability.
        """
        return {
            "name": self.name,
            "priority": getattr(self, "PRIORITY", 100),
            "available": self.is_available(),
        }
