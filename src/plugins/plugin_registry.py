"""
Aura Plugin Registry

The Plugin Registry is the central management system for all Aura plugins.
It handles discovery, registration, lifecycle management, and communication
between plugins and the Brain.
"""

import importlib
import importlib.util
import logging
import os
from collections.abc import Callable
from typing import Any

from .plugin_interface import Plugin, PluginCategory, PluginManifest

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Central registry for all Aura plugins.

    The registry manages:
    - Plugin discovery and loading
    - Plugin registration and lifecycle
    - Capability discovery and routing
    - Plugin dependencies and health monitoring
    - Event publishing and subscription
    """

    def __init__(self, plugins_dir: str = "plugins"):
        """
        Initialize the plugin registry.

        Args:
            plugins_dir: Directory to scan for plugins
        """
        self.plugins_dir = plugins_dir
        self._plugins: dict[str, Plugin] = {}  # plugin_name -> Plugin instance
        self._manifests: dict[str, PluginManifest] = {}  # plugin_name -> PluginManifest
        self._capabilities: dict[str, list[str]] = {}  # capability -> [plugin_names]
        self._enabled: set[str] = set()
        self._disabled: set[str] = set()
        self._dependencies: dict[str, list[str]] = (
            {}
        )  # plugin_name -> [dependency_names]
        self._version_cache: dict[str, str] = {}  # plugin_name -> version
        self._health_checks: list[Callable] = []
        self._callbacks: dict[str, list[Callable]] = {}
        self._lock = logging.getLogger("plugin_registry").__class__(
            type(
                "PluginLock",
                (),
                {
                    "acquire": lambda self: None,
                    "release": lambda self: None,
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *args: None,
                },
            )
        )  # Mock lock

        logger.info(f"PluginRegistry initialized with plugins_dir={plugins_dir}")

    def scan_and_load_plugins(self) -> dict[str, bool]:
        """
        Scan the plugins directory and load all plugins.

        Returns:
            Dictionary mapping plugin names to load success status
        """
        logger.info(f"Scanning {self.plugins_dir} for plugins...")

        results = {}

        try:
            # Scan plugin categories
            categories = [
                "desktop",
                "filesystem",
                "browser",
                "terminal",
                "git",
                "networking",
                "vision",
                "voice",
                "office",
                "email",
                "calendar",
                "knowledge",
                "docker",
                "database",
                "mcp",
            ]

            for category in categories:
                category_dir = os.path.join(self.plugins_dir, category)
                if not os.path.exists(category_dir):
                    continue

                # Scan Python files in category
                for filename in os.listdir(category_dir):
                    if filename.endswith(".py") and not filename.startswith("__"):
                        plugin_path = os.path.join(category_dir, filename)
                        plugin_name = filename[:-3]  # Remove .py extension
                        results[plugin_name] = self.load_plugin(plugin_path)

        except Exception as e:
            logger.error(f"Error scanning plugins: {e}", exc_info=True)

        logger.info(f"Plugin scanning complete. Loaded {len(self._plugins)} plugins.")
        return results

    def load_plugin(self, plugin_path: str) -> bool:
        """
        Load a plugin from a file path.

        Args:
            plugin_path: Path to the plugin file

        Returns:
            True if loaded successfully
        """
        try:
            plugin_name = os.path.basename(plugin_path)[:-3]

            if plugin_name in self._plugins:
                logger.warning(f"Plugin {plugin_name} already loaded")
                return False

            # Create manifest from file metadata
            manifest = self._create_manifest(plugin_path)
            if not manifest:
                logger.error(f"Could not create manifest for {plugin_name}")
                return False

            # Load the plugin module
            module = self._load_plugin_module(plugin_path)

            if not module:
                logger.error(f"Could not load module for {plugin_name}")
                return False

            # Instantiate the plugin
            plugin = self._instantiate_plugin(module, manifest)

            if not plugin:
                logger.error(f"Could not instantiate plugin {plugin_name}")
                return False

            # Store plugin and manifest
            self._plugins[plugin_name] = plugin
            self._manifests[plugin_name] = manifest

            # Register capabilities
            for capability in manifest.capabilities:
                if capability not in self._capabilities:
                    self._capabilities[capability] = []
                self._capabilities[capability].append(plugin_name)

            # Register dependencies
            if manifest.dependencies:
                self._dependencies[plugin_name] = manifest.dependencies

            logger.info(
                f"Plugin loaded: {plugin_name} v{manifest.version} [{manifest.category.value}]"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to load plugin from {plugin_path}: {e}", exc_info=True
            )
            return False

    def _create_manifest(self, plugin_path: str) -> PluginManifest | None:
        """
        Create a plugin manifest from a plugin file.

        This scans the plugin file for plugin metadata and creates
        a PluginManifest instance.
        """
        try:
            with open(plugin_path, encoding="utf-8") as f:
                content = f.read()

            # Extract metadata from docstring
            # Look for pattern: @aura_plugin(name="...", version="...")
            # Or extract from module-level docstring

            # For now, create a default manifest
            # In production, this would parse the plugin file
            plugin_name = os.path.basename(plugin_path)[:-3]

            manifest = PluginManifest(
                name=plugin_name,
                version="1.0.0",
                category=PluginCategory.GENERAL,
                plugin_path=plugin_path,
                entry_point="Plugin",
            )

            return manifest

        except Exception as e:
            logger.error(f"Error creating manifest for {plugin_path}: {e}")
            return None

    def _load_plugin_module(self, plugin_path: str):
        """
        Load a plugin module from file path.

        Args:
            plugin_path: Path to the plugin file

        Returns:
            Loaded module or None if failed
        """
        try:
            spec = importlib.util.spec_from_file_location("plugin_module", plugin_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
            return None
        except Exception as e:
            logger.error(f"Error loading module from {plugin_path}: {e}")
            return None

    def _instantiate_plugin(self, module, manifest: PluginManifest) -> Plugin | None:
        """
        Instantiate a plugin from a loaded module.

        Args:
            module: Loaded Python module
            manifest: Plugin manifest

        Returns:
            Plugin instance or None if failed
        """
        try:
            # Look for the plugin class
            entry_point = manifest.entry_point

            if hasattr(module, entry_point):
                plugin_class = getattr(module, entry_point)
                plugin = plugin_class(manifest)

                # Call load()
                if not plugin.load():
                    logger.error(f"Plugin {manifest.name} failed to load")
                    return None

                # Call initialize()
                if not plugin.initialize():
                    logger.error(f"Plugin {manifest.name} failed to initialize")
                    return None

                return plugin

            # Check for common naming patterns
            for attr_name in dir(module):
                if (
                    attr_name.endswith("Plugin")
                    or attr_name.endswith("Plugin")
                    and isinstance(getattr(module, attr_name), type)
                ):
                    plugin_class = getattr(module, attr_name)
                    plugin = plugin_class(manifest)

                    if not plugin.load():
                        continue

                    if not plugin.initialize():
                        continue

                    return plugin

            return None

        except Exception as e:
            logger.error(f"Error instantiating plugin {manifest.name}: {e}")
            return None

    def get_plugin(self, name: str) -> Plugin | None:
        """
        Get a plugin instance by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None if not found
        """
        return self._plugins.get(name)

    def get_manifest(self, name: str) -> PluginManifest | None:
        """
        Get a plugin manifest by name.

        Args:
            name: Plugin name

        Returns:
            Plugin manifest or None if not found
        """
        return self._manifests.get(name)

    def get_plugins_by_category(self, category: PluginCategory) -> list[Plugin]:
        """
        Get all plugins in a category.

        Args:
            category: Plugin category

        Returns:
            List of plugins
        """
        return [
            plugin
            for name, plugin in self._plugins.items()
            if self._manifests[name].category == category
        ]

    def get_enabled_plugins(self) -> list[Plugin]:
        """
        Get all enabled plugins.

        Returns:
            List of enabled plugins
        """
        return [
            plugin
            for name, plugin in self._plugins.items()
            if name in self._enabled and plugin.get_status()["enabled"]
        ]

    def get_disabled_plugins(self) -> list[Plugin]:
        """
        Get all disabled plugins.

        Returns:
            List of disabled plugins
        """
        return [
            plugin for name, plugin in self._plugins.items() if name in self._disabled
        ]

    def get_all_capabilities(self) -> dict[str, list[str]]:
        """
        Get all capabilities and their associated plugins.

        Returns:
            Dictionary mapping capability -> [plugin_names]
        """
        return self._capabilities.copy()

    def get_capabilities_for_plugin(self, plugin_name: str) -> list[str]:
        """
        Get capabilities provided by a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            List of capabilities
        """
        manifest = self.get_manifest(plugin_name)
        if manifest:
            return manifest.capabilities
        return []

    def get_plugins_with_capability(self, capability: str) -> list[Plugin]:
        """
        Get all plugins that provide a specific capability.

        Args:
            capability: Capability name

        Returns:
            List of plugins that provide this capability
        """
        plugin_names = self._capabilities.get(capability, [])
        return [self.get_plugin(name) for name in plugin_names if self.get_plugin(name)]

    def enable_plugin(self, name: str) -> bool:
        """
        Enable a plugin.

        Args:
            name: Plugin name

        Returns:
            True if enabled successfully
        """
        if name not in self._plugins:
            logger.error(f"Plugin {name} not found")
            return False

        plugin = self._plugins[name]

        if plugin.enable():
            self._enabled.add(name)
            self._disabled.discard(name)
            logger.info(f"Plugin {name} enabled")
            return True

        return False

    def disable_plugin(self, name: str) -> bool:
        """
        Disable a plugin.

        Args:
            name: Plugin name

        Returns:
            True if disabled successfully
        """
        if name not in self._plugins:
            logger.error(f"Plugin {name} not found")
            return False

        plugin = self._plugins[name]

        if plugin.disable():
            self._disabled.add(name)
            self._enabled.discard(name)
            logger.info(f"Plugin {name} disabled")
            return True

        return False

    def reload_plugin(self, name: str) -> bool:
        """
        Reload a plugin.

        Args:
            name: Plugin name

        Returns:
            True if reloaded successfully
        """
        if name not in self._plugins:
            logger.error(f"Plugin {name} not found")
            return False

        # Unload current plugin
        self._disabled.add(name)
        self._enabled.discard(name)

        # Get plugin path
        manifest = self._manifests[name]
        plugin_path = manifest.plugin_path

        # Load fresh copy
        return self.load_plugin(plugin_path)

    def check_health(self, plugin_name: str) -> dict[str, Any]:
        """
        Check health status of a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            Health status dictionary
        """
        plugin = self.get_plugin(plugin_name)

        if not plugin:
            return {"name": plugin_name, "state": "not_found", "healthy": False}

        status = plugin.get_status()

        return {
            "name": plugin_name,
            "state": status["state"],
            "enabled": status["enabled"],
            "capabilities": status["capabilities"],
            "healthy": status["state"] in ["ready", "running", "initialized", "loaded"],
        }

    def check_all_health(self) -> dict[str, dict[str, Any]]:
        """
        Check health of all plugins.

        Returns:
            Dictionary mapping plugin names to health status
        """
        return {name: self.check_health(name) for name in self._plugins.keys()}

    def get_plugin_dependencies(self, name: str) -> list[str]:
        """
        Get dependencies for a plugin.

        Args:
            name: Plugin name

        Returns:
            List of dependency names
        """
        return self._dependencies.get(name, [])

    def resolve_dependencies(self) -> dict[str, bool]:
        """
        Resolve all plugin dependencies.

        Returns:
            Dictionary mapping plugin names to resolution status
        """
        results = {}

        for plugin_name in self._enabled:
            dependencies = self.get_plugin_dependencies(plugin_name)

            for dep_name in dependencies:
                if dep_name not in self._enabled:
                    logger.warning(
                        f"Plugin {plugin_name} requires {dep_name} but it's not enabled"
                    )
                    results[plugin_name] = False
                else:
                    results[plugin_name] = True

        return results

    def register_callback(self, event: str, callback: Callable) -> None:
        """
        Register a callback for an event.

        Args:
            event: Event name
            callback: Callback function
        """
        if event not in self._callbacks:
            self._callbacks[event] = []

        self._callbacks[event].append(callback)

    def trigger_event(self, event: str, **kwargs) -> None:
        """
        Trigger an event and notify all registered callbacks.

        Args:
            event: Event name
            **kwargs: Event data
        """
        if event in self._callbacks:
            callbacks = self._callbacks[event].copy()

            for callback in callbacks:
                try:
                    callback(**kwargs)
                except Exception as e:
                    logger.error(f"Error in event callback for {event}: {e}")

    def get_registry_info(self) -> dict[str, Any]:
        """
        Get registry information.

        Returns:
            Dictionary with registry metadata
        """
        return {
            "total_plugins": len(self._plugins),
            "enabled_plugins": len(self._enabled),
            "disabled_plugins": len(self._disabled),
            "capabilities": len(self._capabilities),
            "plugin_categories": list(
                set(m.category.value for m in self._manifests.values())
            ),
        }

    def shutdown(self) -> None:
        """
        Shutdown all plugins.
        """
        logger.info("Shutting down all plugins...")

        # Shutdown in reverse order
        for name in reversed(list(self._plugins.keys())):
            plugin = self._plugins[name]
            try:
                plugin.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")

        self._plugins.clear()
        self._manifests.clear()
        self._capabilities.clear()
        self._enabled.clear()
        self._disabled.clear()
        self._dependencies.clear()
        self._version_cache.clear()
        self._callbacks.clear()

        logger.info("All plugins shut down")
