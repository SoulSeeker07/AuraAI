"""
Plugin Manager for AuraAI

Manages loading and unloading of AuraAI plugins.
"""

import importlib
import sys
from pathlib import Path
from typing import Dict, List, Any

class PluginManager:
    """
    Manages AuraAI plugins.
    """

    def __init__(self):
        """Initialize the plugin manager."""
        self.loaded_plugins: Dict[str, Any] = {}
        self.plugin_path = Path(__file__).parent.parent

    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load a plugin.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            True if plugin was loaded successfully, False otherwise
        """
        try:
            # Get plugin module path
            plugin_path = self.plugin_path / plugin_name

            # Check if plugin exists
            if not plugin_path.exists():
                raise ImportError(f"Plugin '{plugin_name}' not found at {plugin_path}")

            # Check if plugin has __init__.py
            init_file = plugin_path / "__init__.py"
            if not init_file.exists():
                raise ImportError(f"Plugin '{plugin_name}' has no __init__.py")

            # Add plugin path to sys.path
            if str(self.plugin_path) not in sys.path:
                sys.path.insert(0, str(self.plugin_path))

            # Import plugin module
            plugin_module = importlib.import_module(plugin_name)

            # Try to get plugin class
            plugin_class_name = f"{plugin_name.capitalize()}Plugin"
            if hasattr(plugin_module, plugin_class_name):
                plugin_class = getattr(plugin_module, plugin_class_name)

                # Try to instantiate plugin
                try:
                    plugin_instance = plugin_class()
                    self.loaded_plugins[plugin_name] = plugin_instance
                    return True
                except Exception as e:
                    raise RuntimeError(f"Failed to instantiate plugin: {e}")

            # If no plugin class found, return success anyway
            return True

        except Exception as e:
            print(f"Error loading plugin '{plugin_name}': {e}")
            return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if plugin was unloaded successfully, False otherwise
        """
        try:
            if plugin_name in self.loaded_plugins:
                del self.loaded_plugins[plugin_name]
                return True
            return False
        except Exception as e:
            print(f"Error unloading plugin '{plugin_name}': {e}")
            return False

    def get_plugin(self, plugin_name: str) -> Any:
        """
        Get a loaded plugin instance.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin instance or None if not loaded
        """
        return self.loaded_plugins.get(plugin_name)

    def get_all_plugins(self) -> Dict[str, Any]:
        """
        Get all loaded plugins.

        Returns:
            Dictionary of loaded plugins
        """
        return self.loaded_plugins

    def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get information about a loaded plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin information dictionary
        """
        plugin = self.loaded_plugins.get(plugin_name)
        if not plugin:
            return {
                'loaded': False,
                'name': plugin_name,
                'status': 'Not loaded'
            }

        # Try to get plugin info
        if hasattr(plugin, 'get_info'):
            return plugin.get_info()

        return {
            'loaded': True,
            'name': plugin_name,
            'status': 'Loaded'
        }

    def get_plugin_status(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get status of a plugin (alias for get_plugin_info).

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin status dictionary
        """
        return self.get_plugin_info(plugin_name)
