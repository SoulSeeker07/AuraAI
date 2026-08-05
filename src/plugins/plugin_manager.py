"""
Aura Plugin Manager

The Plugin Manager orchestrates plugin lifecycle and coordinates
communication between plugins and the Brain.
"""

import logging
from collections.abc import Callable
from typing import Any

from .plugin_interface import Plugin, PluginCategory
from .plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Orchestrates plugin lifecycle and coordinates plugin interactions.

    The Plugin Manager:
    - Manages plugin lifecycle (load, initialize, execute, shutdown)
    - Coordinates plugin execution through the Tool Execution Engine
    - Handles plugin-to-Brain communication
    - Manages plugin dependencies and health
    """

    def __init__(
        self, registry: PluginRegistry | None = None, enable_auto_discovery: bool = True
    ):
        """
        Initialize the plugin manager.

        Args:
            registry: PluginRegistry instance
            enable_auto_discovery: Whether to scan and load plugins on startup
        """
        self.registry = registry or PluginRegistry()

        self.enable_auto_discovery = enable_auto_discovery
        self._initialized = False

        logger.info("PluginManager initialized")

    def initialize(self) -> bool:
        """
        Initialize the plugin manager and load all plugins.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            logger.warning("PluginManager already initialized")
            return True

        try:
            # Enable auto-discovery
            if self.enable_auto_discovery:
                self.registry.scan_and_load_plugins()

            self._initialized = True
            logger.info("PluginManager initialized successfully")
            return True

        except Exception as e:
            logger.error(f"PluginManager initialization failed: {e}", exc_info=True)
            return False

    def get_registry(self) -> PluginRegistry:
        """Get the plugin registry."""
        return self.registry

    def get_plugin(self, name: str) -> Plugin | None:
        """
        Get a plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self.registry.get_plugin(name)

    def execute_capability(self, capability: str, **kwargs) -> dict[str, Any]:
        """
        Execute a capability through the appropriate plugin.

        The Brain uses this method to delegate capability execution
        to the appropriate plugin.

        Args:
            capability: Capability to execute
            **kwargs: Execution parameters

        Returns:
            Execution result with success status and output
        """
        # Find plugins that can handle this capability
        plugins = self.registry.get_plugins_with_capability(capability)

        if not plugins:
            logger.warning(f"No plugin found for capability: {capability}")
            return {
                "success": False,
                "error": f"No plugin found for capability: {capability}",
                "output": None,
            }

        # Execute through the first enabled plugin
        for plugin in plugins:
            if not plugin.get_status()["enabled"]:
                continue

            try:
                logger.info(
                    f"Executing capability '{capability}' through plugin {plugin.manifest.name}"
                )

                # Execute the capability
                result = plugin.execute(capability, **kwargs)

                logger.info(f"Capability '{capability}' executed successfully")

                return {
                    "success": True,
                    "plugin": plugin.manifest.name,
                    "output": result,
                }

            except Exception as e:
                logger.error(
                    f"Error executing capability '{capability}' through plugin {plugin.manifest.name}: {e}",
                    exc_info=True,
                )

                # Check if plugin crashed
                if plugin.get_error():
                    logger.error(
                        f"Plugin {plugin.manifest.name} crashed: {plugin.get_error()}"
                    )

        # If all plugins failed
        logger.error(f"All plugins failed to execute capability: {capability}")
        return {
            "success": False,
            "error": f"All plugins failed to execute capability: {capability}",
            "output": None,
        }

    def execute_capability_through_plugin(
        self, plugin_name: str, capability: str, **kwargs
    ) -> dict[str, Any]:
        """
        Execute a capability through a specific plugin.

        Args:
            plugin_name: Plugin name
            capability: Capability to execute
            **kwargs: Execution parameters

        Returns:
            Execution result
        """
        plugin = self.registry.get_plugin(plugin_name)

        if not plugin:
            return {
                "success": False,
                "error": f"Plugin not found: {plugin_name}",
                "output": None,
            }

        if not plugin.get_status()["enabled"]:
            return {
                "success": False,
                "error": f"Plugin is disabled: {plugin_name}",
                "output": None,
            }

        if not plugin.can_handle(capability):
            return {
                "success": False,
                "error": f"Plugin {plugin_name} does not support capability: {capability}",
                "output": None,
            }

        try:
            result = plugin.execute(capability, **kwargs)

            return {"success": True, "plugin": plugin_name, "output": result}

        except Exception as e:
            logger.error(
                f"Error executing capability '{capability}' through plugin {plugin_name}: {e}",
                exc_info=True,
            )

            return {"success": False, "error": str(e), "output": None}

    def register_plugin_event_handler(self, event: str, handler: Callable) -> None:
        """
        Register a handler for plugin events.

        Events can be triggered by plugins to notify the Brain
        of important events (e.g., download complete, git commit).

        Args:
            event: Event name
            handler: Handler function
        """
        self.registry.register_callback(event, handler)

    def execute_plugin_command(
        self, plugin_name: str, command: str, **kwargs
    ) -> dict[str, Any]:
        """
        Execute a command on a plugin.

        Commands are plugin-specific operations (e.g., "reload", "status").

        Args:
            plugin_name: Plugin name
            command: Command to execute
            **kwargs: Command parameters

        Returns:
            Command result
        """
        plugin = self.registry.get_plugin(plugin_name)

        if not plugin:
            return {
                "success": False,
                "error": f"Plugin not found: {plugin_name}",
                "output": None,
            }

        if not plugin.get_status()["enabled"]:
            return {
                "success": False,
                "error": f"Plugin is disabled: {plugin_name}",
                "output": None,
            }

        # Check if plugin has a command handler
        command_handler = plugin.get_capability_handler(f"command:{command}")

        if not command_handler:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} does not support command: {command}",
                "output": None,
            }

        try:
            result = command_handler(**kwargs)

            return {
                "success": True,
                "plugin": plugin_name,
                "command": command,
                "output": result,
            }

        except Exception as e:
            logger.error(
                f"Error executing command '{command}' on plugin {plugin_name}: {e}",
                exc_info=True,
            )

            return {"success": False, "error": str(e), "output": None}

    def get_plugin_status(self, plugin_name: str) -> dict[str, Any]:
        """
        Get status information for a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            Status dictionary
        """
        plugin = self.registry.get_plugin(plugin_name)

        if not plugin:
            return {"name": plugin_name, "state": "not_found", "healthy": False}

        return plugin.get_status()

    def get_all_plugin_statuses(self) -> dict[str, dict[str, Any]]:
        """
        Get status for all plugins.

        Returns:
            Dictionary mapping plugin names to status
        """
        return self.registry.check_all_health()

    def enable_plugin(self, plugin_name: str) -> bool:
        """
        Enable a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            True if enabled successfully
        """
        if not self.registry.enable_plugin(plugin_name):
            return False

        logger.info(f"Plugin {plugin_name} enabled via PluginManager")
        self.registry.trigger_event("plugin_enabled", plugin_name=plugin_name)

        return True

    def disable_plugin(self, plugin_name: str) -> bool:
        """
        Disable a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            True if disabled successfully
        """
        if not self.registry.disable_plugin(plugin_name):
            return False

        logger.info(f"Plugin {plugin_name} disabled via PluginManager")
        self.registry.trigger_event("plugin_disabled", plugin_name=plugin_name)

        return True

    def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            True if reloaded successfully
        """
        if not self.registry.reload_plugin(plugin_name):
            return False

        logger.info(f"Plugin {plugin_name} reloaded via PluginManager")
        self.registry.trigger_event("plugin_reloaded", plugin_name=plugin_name)

        return True

    def get_all_capabilities(self) -> dict[str, list[str]]:
        """
        Get all capabilities and their providers.

        Returns:
            Dictionary mapping capability -> [plugin_names]
        """
        return self.registry.get_all_capabilities()

    def get_plugin_categories(self) -> list[PluginCategory]:
        """
        Get all registered plugin categories.

        Returns:
            List of categories
        """
        return list(set(m.category for m in self.registry._manifests.values()))

    def get_stats(self) -> dict[str, Any]:
        """
        Get plugin manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "initialized": self._initialized,
            "auto_discovery_enabled": self.enable_auto_discovery,
            "total_plugins": len(self.registry._plugins),
            "enabled_plugins": len(self.registry._enabled),
            "disabled_plugins": len(self.registry._disabled),
            "capabilities_count": len(self.registry._capabilities),
            "categories": len(self.get_plugin_categories()),
            "registry_info": self.registry.get_registry_info(),
        }

    def shutdown(self) -> None:
        """
        Shutdown all plugins.
        """
        logger.info("PluginManager shutting down...")

        # Shutdown via registry
        self.registry.shutdown()

        logger.info("PluginManager shut down successfully")
