"""
Plugin Registry

Registers and discovers capabilities provided by plugins.

The router should not know specific plugins.
It should ask a registry for available capabilities.

This ensures new capabilities appear automatically when plugins are installed.
"""

import logging
from typing import Any

from .capability_types import CapabilityType

logger = logging.getLogger(__name__)


class PluginCapability:
    """Represents a capability provided by a plugin."""

    def __init__(
        self,
        name: str,
        capability_type: CapabilityType,
        description: str,
        supported_operations: list[str] = None,
        priority: str = "medium",
    ):
        """
        Initialize a plugin capability.

        Args:
            name: Name of the capability
            capability_type: Type of capability
            description: Description of what the capability does
            supported_operations: List of operation names
            priority: Priority level
        """
        self.name = name
        self.capability_type = capability_type
        self.description = description
        self.supported_operations = supported_operations or []
        self.priority = priority
        self.metadata: dict[str, Any] = {}

    def can_handle(self, operation: str) -> bool:
        """
        Check if plugin can handle a specific operation.

        Args:
            operation: Operation name

        Returns:
            True if plugin can handle it
        """
        return operation.lower() in [op.lower() for op in self.supported_operations]

    def __repr__(self) -> str:
        """String representation."""
        return f"PluginCapability({self.name}, {self.capability_type.value})"


class PluginRegistry:
    """
    Registry for plugin-provided capabilities.

    This enables dynamic discovery of capabilities without hardcoding.
    """

    def __init__(self):
        """Initialize plugin registry."""
        self.capabilities: list[PluginCapability] = []
        self.plugins: dict[str, Any] = {}  # Plugin name -> plugin instance
        logger.info("Plugin Registry initialized")

    def register_plugin(self, plugin_name: str, plugin_instance: Any) -> None:
        """
        Register a plugin.

        Args:
            plugin_name: Name of the plugin
            plugin_instance: Plugin instance
        """
        self.plugins[plugin_name] = plugin_instance
        logger.info(f"Registered plugin: {plugin_name}")

    def unregister_plugin(self, plugin_name: str) -> None:
        """
        Unregister a plugin.

        Args:
            plugin_name: Name of the plugin
        """
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
        logger.info(f"Unregistered plugin: {plugin_name}")

    def discover_capabilities(self, plugin_instance: Any) -> list[PluginCapability]:
        """
        Discover capabilities from a plugin instance.

        This method should be called by plugins to register their capabilities.

        Args:
            plugin_instance: Plugin instance

        Returns:
            List of capabilities provided by the plugin
        """
        try:
            # Check if plugin has a get_capabilities method
            if hasattr(plugin_instance, "get_capabilities"):
                capabilities = plugin_instance.get_capabilities()

                # Register each capability
                for capability in capabilities:
                    self.register_capability(
                        name=capability.get("name", "Unknown"),
                        capability_type=capability.get("capability_type", "unknown"),
                        description=capability.get("description", ""),
                        supported_operations=capability.get("supported_operations", []),
                        priority=capability.get("priority", "medium"),
                    )

                logger.info(f"Discovered {len(capabilities)} capabilities from plugin")

                return capabilities
        except Exception as e:
            logger.error(
                f"Error discovering capabilities from plugin: {e}", exc_info=True
            )

        return []

    def register_capability(
        self,
        name: str,
        capability_type: str,
        description: str,
        supported_operations: list[str] = None,
        priority: str = "medium",
    ) -> None:
        """
        Register a capability manually.

        Args:
            name: Name of the capability
            capability_type: Type of capability (CapabilityType enum value)
            description: Description of capability
            supported_operations: List of supported operations
            priority: Priority level
        """
        try:
            # Convert capability type string to enum
            from .capability_types import CapabilityType as CT

            # Try to convert to enum
            try:
                capability_enum = CT(capability_type)
            except ValueError:
                # Unknown capability type, default to unknown
                logger.warning(f"Unknown capability type: {capability_type}")
                capability_enum = CT.PLUGIN

            capability = PluginCapability(
                name=name,
                capability_type=capability_enum,
                description=description,
                supported_operations=supported_operations,
                priority=priority,
            )

            self.capabilities.append(capability)
            logger.info(f"Registered capability: {name} ({capability_enum.value})")

        except Exception as e:
            logger.error(f"Error registering capability: {e}", exc_info=True)

    def get_capability(
        self, capability_type: CapabilityType
    ) -> PluginCapability | None:
        """
        Get a specific capability.

        Args:
            capability_type: The capability type

        Returns:
            PluginCapability if found, None otherwise
        """
        for capability in self.capabilities:
            if capability.capability_type == capability_type:
                return capability
        return None

    def get_capabilities_for_operation(self, operation: str) -> list[PluginCapability]:
        """
        Get all capabilities that can handle a specific operation.

        Args:
            operation: Operation name

        Returns:
            List of matching capabilities
        """
        matching = []
        for capability in self.capabilities:
            if capability.can_handle(operation):
                matching.append(capability)
        return matching

    def get_all_capabilities(self) -> list[PluginCapability]:
        """
        Get all registered capabilities.

        Returns:
            List of all capabilities
        """
        return self.capabilities

    def get_capabilities_by_type(
        self, capability_type: CapabilityType
    ) -> list[PluginCapability]:
        """
        Get all capabilities of a specific type.

        Args:
            capability_type: The capability type

        Returns:
            List of capabilities of that type
        """
        return [
            cap for cap in self.capabilities if cap.capability_type == capability_type
        ]

    def get_plugin_by_capability(self, capability_type: CapabilityType) -> Any | None:
        """
        Get the plugin that provides a specific capability.

        Args:
            capability_type: The capability type

        Returns:
            Plugin instance if found, None otherwise
        """
        for plugin_name, plugin_instance in self.plugins.items():
            capabilities = self.get_capabilities_by_plugin(plugin_name)
            for capability in capabilities:
                if capability.capability_type == capability_type:
                    return plugin_instance
        return None

    def get_capabilities_by_plugin(self, plugin_name: str) -> list[PluginCapability]:
        """
        Get all capabilities provided by a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            List of capabilities from that plugin
        """
        return [
            cap
            for cap in self.capabilities
            if hasattr(cap, "name") and cap.name.lower() == plugin_name.lower()
        ]
