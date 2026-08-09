"""
M19.6 Capability Registry
=========================
Location: src/core/capabilities/capability_registry.py

Uniform capability registry for native tools, scripts, and adapters with typed schemas,
risk classifications, and permission contracts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.orchestration.autonomy_mode import ActionRisk

logger = logging.getLogger(__name__)


@dataclass
class CapabilityDefinition:
    """Standardized metadata definition for a tool or engine capability."""

    name: str  # e.g., "filesystem.read", "browser.open"
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: ActionRisk = ActionRisk.LOW
    permissions: list[str] = field(default_factory=list)
    availability: str = "online"  # "online", "offline", "conditional"
    execution_backend: str = "local"  # "local", "remote", "subprocess"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, ActionRisk) else str(self.risk_level),
            "permissions": self.permissions,
            "availability": self.availability,
            "execution_backend": self.execution_backend,
        }


class CapabilityRegistry:
    """Singleton registry holding all active capabilities in Aura."""

    _instance: CapabilityRegistry | None = None

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}
        self._register_default_capabilities()

    @classmethod
    def get_instance(cls) -> CapabilityRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def register(self, cap: CapabilityDefinition) -> None:
        """Register a new capability definition."""
        self._capabilities[cap.name] = cap
        logger.info(f"Capability registered: {cap.name} (Risk: {cap.risk_level.value})")

    def get(self, name: str) -> CapabilityDefinition | None:
        """Retrieve a registered capability definition by name."""
        return self._capabilities.get(name)

    def discover(self) -> list[CapabilityDefinition]:
        """Discover and return all currently registered capabilities."""
        return list(self._capabilities.values())

    def _register_default_capabilities(self) -> None:
        """Register core baseline capabilities."""
        defaults = [
            CapabilityDefinition(
                name="filesystem.read",
                description="Read contents of a file",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                risk_level=ActionRisk.LOW,
                permissions=["read"],
            ),
            CapabilityDefinition(
                name="filesystem.write",
                description="Write contents to a file",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
                risk_level=ActionRisk.MEDIUM,
                permissions=["write"],
            ),
            CapabilityDefinition(
                name="filesystem.delete",
                description="Delete a file or directory",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                risk_level=ActionRisk.HIGH,
                permissions=["delete"],
            ),
            CapabilityDefinition(
                name="browser.open",
                description="Open a browser page",
                input_schema={"type": "object", "properties": {"url": {"type": "string"}}},
                risk_level=ActionRisk.LOW,
                permissions=["browser"],
            ),
            CapabilityDefinition(
                name="browser.checkout",
                description="Perform financial or e-commerce checkout",
                input_schema={"type": "object", "properties": {"cart_id": {"type": "string"}}},
                risk_level=ActionRisk.CRITICAL,
                permissions=["purchase", "browser"],
            ),
        ]

        for cap in defaults:
            self._capabilities[cap.name] = cap


__all__ = ["CapabilityDefinition", "CapabilityRegistry"]
