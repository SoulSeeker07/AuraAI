"""
Generic Base Adapter Factory Framework

Generic factory base class providing automatic priority sorting, availability checks,
and fallback selection across all native hardware/API adapter factories.
"""

from typing import List, TypeVar, Generic, Type, Optional
import logging

from .base_adapter import BaseNativeAdapter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseNativeAdapter)


class BaseAdapterFactory(Generic[T]):
    """
    Generic factory base class for native system adapters.

    Subclasses define `_adapter_classes` containing concrete adapter types.
    """

    _adapter_classes: List[Type[T]] = []

    @classmethod
    def get_adapter(cls) -> T:
        """
        Get the highest priority available adapter instance.

        Returns:
            An instance of an available adapter subclass.
        """
        sorted_classes = sorted(
            cls._adapter_classes,
            key=lambda c: getattr(c, "PRIORITY", 100)
        )

        for adapter_cls in sorted_classes:
            try:
                instance = adapter_cls()
                if instance.is_available():
                    logger.info(f"Selected '{cls.__name__}' active adapter: '{instance.name}'")
                    return instance
            except Exception as e:
                logger.debug(f"Adapter '{adapter_cls.__name__}' availability check failed: {e}")

        # Fallback to last class if defined
        if cls._adapter_classes:
            fallback_cls = cls._adapter_classes[-1]
            return fallback_cls()

        raise RuntimeError(f"No adapter classes configured for factory '{cls.__name__}'")

    @classmethod
    def get_all_adapters(cls) -> List[T]:
        """
        Instantiate all registered adapter classes for diagnostic inspection.

        Returns:
            List of initialized adapter instances.
        """
        instances = []
        for adapter_cls in cls._adapter_classes:
            try:
                instances.append(adapter_cls())
            except Exception as e:
                logger.warning(f"Could not instantiate adapter class '{adapter_cls.__name__}': {e}")
        return instances
