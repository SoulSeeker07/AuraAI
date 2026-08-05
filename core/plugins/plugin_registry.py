"""
Plugin Registry

Manages registered plugins and their capabilities.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PluginBase:
    """Base class for all plugins."""

    def get_plugin_name(self) -> str:
        """Get the name of the plugin."""
        raise NotImplementedError

    def get_plugin_version(self) -> str:
        """Get the version of the plugin."""
        raise NotImplementedError

    def get_plugin_description(self) -> str:
        """Get the description of the plugin."""
        raise NotImplementedError

    def get_plugin_capabilities(self) -> list[str]:
        """Get list of capabilities provided by this plugin."""
        raise NotImplementedError

    def on_load(self):
        """Called when plugin is loaded."""
        pass

    def on_unload(self):
        """Called when plugin is unloaded."""
        pass


class PluginRegistry:
    """
    Manages registered plugins.

    Responsibilities:
        - Discover plugins from files
        - Register plugins
        - Execute plugin tools
        - Track plugin lifecycle
    """

    def __init__(self):
        """Initialize the plugin registry."""
        self._plugins: dict[str, PluginBase] = {}
        self._capabilities: dict[str, list[str]] = {}
        logger.info("Plugin Registry initialized")

    def register(self, plugin: PluginBase):
        """
        Register a plugin.

        Args:
            plugin: Plugin instance to register
        """
        plugin_name = plugin.get_plugin_name()
        self._plugins[plugin_name] = plugin

        # Register capabilities
        capabilities = plugin.get_plugin_capabilities()
        self._capabilities[plugin_name] = capabilities

        logger.info(f"Registered plugin: {plugin_name} v{plugin.get_plugin_version()}")

    def unregister(self, plugin_name: str):
        """
        Unregister a plugin.

        Args:
            plugin_name: Name of plugin to unregister
        """
        if plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            try:
                plugin.on_unload()
            except Exception as e:
                logger.warning(f"Error unloading plugin {plugin_name}: {e}")

            del self._plugins[plugin_name]
            if plugin_name in self._capabilities:
                del self._capabilities[plugin_name]

            logger.info(f"Unregistered plugin: {plugin_name}")

    def get_plugin(self, plugin_name: str) -> PluginBase | None:
        """
        Get a registered plugin.

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(plugin_name)

    def get_available_tools(self) -> dict[str, Any]:
        """
        Get all available tools from registered plugins.

        Returns:
            Dictionary of plugin tools
        """
        tools = {}

        for plugin_name, plugin in self._plugins.items():
            capabilities = plugin.get_plugin_capabilities()

            for capability in capabilities:
                # Register plugin as a tool
                tools[plugin_name] = {
                    "name": plugin_name,
                    "description": plugin.get_plugin_description(),
                    "async": False,
                    "handler": lambda params, plugin=plugin: self._execute_plugin(
                        plugin, params
                    ),
                    "metadata": {
                        "plugin_name": plugin_name,
                        "version": plugin.get_plugin_version(),
                    },
                }

        return tools

    def _execute_plugin(self, plugin: PluginBase, params: dict) -> str:
        """
        Execute a plugin's capability.

        Args:
            plugin: Plugin to execute
            params: Parameters for the execution

        Returns:
            Execution result
        """
        # This is a placeholder - actual plugin execution would be more sophisticated
        return f"Executed {plugin.get_plugin_name()}: {params}"

    def has_plugin(self, plugin_name: str) -> bool:
        """
        Check if a plugin is registered.

        Args:
            plugin_name: Name of plugin

        Returns:
            True if plugin is registered
        """
        return plugin_name in self._plugins

    def list_plugins(self) -> list[str]:
        """
        List all registered plugins.

        Returns:
            List of plugin names
        """
        return list(self._plugins.keys())
