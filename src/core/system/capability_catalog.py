"""
Capability Catalog
Location: src/core/system/capability_catalog.py

Exports a live snapshot of Aura's capabilities directly from the CapabilityRegistry.

This is the "dynamic" half of the identity layer.
Unlike aura_capabilities.yaml (static human-curated document),
this module reads the actual registry at runtime — so when a new manager
registers new capabilities, they appear automatically in Aura's identity context.

Usage:
    catalog = CapabilityCatalog()
    entries = catalog.export_live()
    text = catalog.export_as_text()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CatalogEntry:
    """
    A single capability entry in the live catalog.
    Derived from CapabilityDescriptor in src/desktop/native/capability_registry.py
    """

    name: str
    description: str
    category: str
    manager: str
    risk_level: str = "low"
    permission: str = "read"
    requires_confirmation: bool = False
    is_destructive: bool = False
    usage_examples: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_text_line(self) -> str:
        """Single-line text representation for LLM context."""
        examples_str = f" (e.g. {self.usage_examples[0]})" if self.usage_examples else ""
        risk_str = f" [risk:{self.risk_level}]" if self.risk_level not in ("safe", "low") else ""
        return f"  ✓ {self.name}: {self.description}{examples_str}{risk_str}"


class CapabilityCatalog:
    """
    Exports a live snapshot of capabilities from CapabilityRegistry at runtime.

    Reads directly from the CapabilityRegistry singleton.
    This means any new manager that registers capabilities is automatically
    included — no YAML edits, no prompt changes.

    Fallback: if CapabilityRegistry is unavailable, returns an empty catalog
    and logs a warning. The system continues to function.
    """

    def __init__(self) -> None:
        self._registry: Any | None = None
        self._registry_loaded = False

    def _get_registry(self) -> Any | None:
        """Lazy-load the CapabilityRegistry. Only imports on first call."""
        if not self._registry_loaded:
            try:
                from src.desktop.native.capability_registry import (
                    CapabilityRegistry,
                )
                self._registry = CapabilityRegistry()
                self._registry_loaded = True
                logger.debug("CapabilityCatalog: CapabilityRegistry loaded successfully.")
            except ImportError as e:
                logger.warning(f"CapabilityCatalog: CapabilityRegistry not available: {e}")
                self._registry_loaded = True  # mark as attempted
            except Exception as e:
                logger.error(f"CapabilityCatalog: error loading CapabilityRegistry: {e}")
                self._registry_loaded = True
        return self._registry

    def export_live(self) -> list[CatalogEntry]:
        """
        Export all capabilities from the live CapabilityRegistry.

        Returns a list of CatalogEntry objects, one per registered capability.
        Returns empty list if CapabilityRegistry is unavailable.
        """
        registry = self._get_registry()
        if registry is None:
            return []

        entries: list[CatalogEntry] = []
        try:
            for cap_name, cap_desc in registry._capabilities.items():
                entry = CatalogEntry(
                    name=cap_name,
                    description=getattr(cap_desc, "description", ""),
                    category=getattr(cap_desc, "category", "unknown"),
                    manager=getattr(cap_desc, "manager", "unknown"),
                    risk_level=getattr(
                        getattr(cap_desc, "risk_level", None), "value", "low"
                    ),
                    permission=getattr(
                        getattr(cap_desc, "permission", None), "value", "read"
                    ),
                    requires_confirmation=getattr(cap_desc, "requires_confirmation", False),
                    is_destructive=getattr(cap_desc, "is_destructive", False),
                    usage_examples=list(getattr(cap_desc, "usage_examples", [])),
                    tags=list(getattr(cap_desc, "tags", [])),
                )
                entries.append(entry)
        except Exception as e:
            logger.error(f"CapabilityCatalog: error iterating registry: {e}")

        logger.debug(f"CapabilityCatalog.export_live(): {len(entries)} capabilities exported.")
        return entries

    def export_by_category(self) -> dict[str, list[CatalogEntry]]:
        """
        Export capabilities grouped by category.

        Returns dict: category → list[CatalogEntry]
        """
        entries = self.export_live()
        grouped: dict[str, list[CatalogEntry]] = {}
        for entry in entries:
            grouped.setdefault(entry.category, []).append(entry)
        return grouped

    def export_as_text(self, max_per_category: int = 20) -> str:
        """
        Export capabilities as a concise LLM-ready text block.

        Format:
            DESKTOP (window): 12 capabilities
              ✓ list_windows: List all visible windows on the desktop
              ✓ activate_window: Activate and bring a window to the foreground
              ...

        Args:
            max_per_category: Cap per-category entries to keep the block concise.
        """
        grouped = self.export_by_category()
        if not grouped:
            return "(CapabilityRegistry unavailable — no live capabilities exported)"

        lines: list[str] = ["=== LIVE CAPABILITY CATALOG ==="]

        for category in sorted(grouped.keys()):
            entries = grouped[category]
            lines.append(f"\n{category.upper()} ({len(entries)} capabilities):")
            for entry in entries[:max_per_category]:
                lines.append(entry.to_text_line())
            if len(entries) > max_per_category:
                lines.append(f"  ... and {len(entries) - max_per_category} more")

        total = sum(len(v) for v in grouped.values())
        lines.append(f"\nTotal: {total} live capabilities across {len(grouped)} categories.")
        return "\n".join(lines)

    def count(self) -> int:
        """Total number of live registered capabilities."""
        registry = self._get_registry()
        if registry is None:
            return 0
        try:
            return len(registry._capabilities)
        except Exception:
            return 0

    def has_capability(self, name: str) -> bool:
        """Check if a specific capability name is registered."""
        registry = self._get_registry()
        if registry is None:
            return False
        try:
            return name in registry._capabilities
        except Exception:
            return False

    def get_capability(self, name: str) -> CatalogEntry | None:
        """Get a single capability entry by name. Returns None if not found."""
        registry = self._get_registry()
        if registry is None:
            return None
        try:
            cap_desc = registry._capabilities.get(name)
            if cap_desc is None:
                return None
            return CatalogEntry(
                name=name,
                description=getattr(cap_desc, "description", ""),
                category=getattr(cap_desc, "category", "unknown"),
                manager=getattr(cap_desc, "manager", "unknown"),
                risk_level=getattr(
                    getattr(cap_desc, "risk_level", None), "value", "low"
                ),
                permission=getattr(
                    getattr(cap_desc, "permission", None), "value", "read"
                ),
                requires_confirmation=getattr(cap_desc, "requires_confirmation", False),
                is_destructive=getattr(cap_desc, "is_destructive", False),
                usage_examples=list(getattr(cap_desc, "usage_examples", [])),
                tags=list(getattr(cap_desc, "tags", [])),
            )
        except Exception as e:
            logger.error(f"CapabilityCatalog.get_capability({name}): {e}")
            return None
