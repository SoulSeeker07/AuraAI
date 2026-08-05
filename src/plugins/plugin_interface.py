"""
Aura Plugin Interface

This module defines the contract that all plugins must implement.
Plugins follow a consistent lifecycle to ensure stability and predictability.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any


class PluginState(Enum):
    """Plugin state values."""

    LOADED = "loaded"
    INITIALIZED = "initialized"
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"
    DISABLED = "disabled"
    UPDATING = "updating"
    CRASHED = "crashed"
    UNLOADED = "unloaded"


class PluginCategory(Enum):
    """Plugin categories."""

    DESKTOP = "desktop"
    FILESYSTEM = "filesystem"
    BROWSER = "browser"
    TERMINAL = "terminal"
    GIT = "git"
    NETWORKING = "networking"
    VISION = "vision"
    VOICE = "voice"
    OFFICE = "office"
    EMAIL = "email"
    CALENDAR = "calendar"
    KNOWLEDGE = "knowledge"
    DOCKER = "docker"
    DATABASE = "database"
    MCP = "mcp"
    GENERAL = "general"


class PluginManifest:
    """
    Plugin metadata and configuration.

    This class contains all information about a plugin that Aura needs
    to discover, validate, load, and manage it.
    """

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        author: str = "",
        description: str = "",
        category: PluginCategory = PluginCategory.GENERAL,
        capabilities: list[str] = None,
        permissions: list[str] = None,
        dependencies: list[str] = None,
        min_aura_version: str = "1.0.0",
        max_aura_version: str = "",
        is_optional: bool = False,
        is_system: bool = False,
        plugin_path: str = "",
        entry_point: str = "Plugin",
    ):
        """
        Initialize plugin manifest.

        Args:
            name: Plugin name
            version: Plugin version (semver format)
            author: Plugin author
            description: Plugin description
            category: Plugin category
            capabilities: List of capabilities this plugin provides
            permissions: List of permissions this plugin requires
            dependencies: List of plugin dependencies (name, version)
            min_aura_version: Minimum Aura version required
            max_aura_version: Maximum Aura version supported
            is_optional: Whether plugin is optional
            is_system: Whether plugin is a system plugin
            plugin_path: File path to the plugin
            entry_point: Name of the main plugin class
        """
        self.name = name
        self.version = version
        self.author = author
        self.description = description
        self.category = category
        self.capabilities = capabilities or []
        self.permissions = permissions or []
        self.dependencies = dependencies or []
        self.min_aura_version = min_aura_version
        self.max_aura_version = max_aura_version
        self.is_optional = is_optional
        self.is_system = is_system
        self.plugin_path = plugin_path
        self.entry_point = entry_point
        self.loaded_at = datetime.now()
        self.loaded_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "category": self.category.value,
            "capabilities": self.capabilities,
            "permissions": self.permissions,
            "dependencies": self.dependencies,
            "min_aura_version": self.min_aura_version,
            "max_aura_version": self.max_aura_version,
            "is_optional": self.is_optional,
            "is_system": self.is_system,
            "plugin_path": self.plugin_path,
            "entry_point": self.entry_point,
            "loaded_at": self.loaded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
        """Create manifest from dictionary."""
        category = PluginCategory(data.get("category", "general"))
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            description=data.get("description", ""),
            category=category,
            capabilities=data.get("capabilities", []),
            permissions=data.get("permissions", []),
            dependencies=data.get("dependencies", []),
            min_aura_version=data.get("min_aura_version", "1.0.0"),
            max_aura_version=data.get("max_aura_version", ""),
            is_optional=data.get("is_optional", False),
            is_system=data.get("is_system", False),
            plugin_path=data.get("plugin_path", ""),
            entry_point=data.get("entry_point", "Plugin"),
        )


class Plugin(ABC):
    """
    Abstract base class for all plugins.

    All Aura plugins must implement this interface to ensure
    consistent lifecycle and behavior.
    """

    def __init__(self, manifest: PluginManifest):
        """
        Initialize the plugin.

        Args:
            manifest: Plugin manifest with metadata
        """
        self.manifest = manifest
        self.state = PluginState.UNLOADED
        self.logger = logging.getLogger(f"plugin.{manifest.name}")
        self._enabled = True
        self._error: Exception | None = None
        self._capabilities: dict[str, Callable] = {}
        self._context: dict[str, Any] | None = None

    @abstractmethod
    def load(self) -> bool:
        """
        Load the plugin.

        Called when plugin is first discovered.

        Returns:
            True if loaded successfully

        Raises:
            PluginLoadError: If loading fails
        """
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the plugin.

        Called after load() is successful.
        This is where the plugin should set up its internal state.

        Returns:
            True if initialized successfully

        Raises:
            PluginInitError: If initialization fails
        """
        pass

    def can_handle(self, capability: str) -> bool:
        """
        Check if plugin can handle a capability.

        Args:
            capability: Capability to check

        Returns:
            True if plugin can handle this capability
        """
        return capability in self.manifest.capabilities

    @abstractmethod
    def execute(self, capability: str, **kwargs) -> Any:
        """
        Execute a capability.

        Args:
            capability: Capability to execute
            **kwargs: Execution parameters

        Returns:
            Execution result

        Raises:
            PluginExecutionError: If execution fails
        """
        pass

    def register_capability(self, name: str, handler: Callable) -> None:
        """
        Register a capability handler.

        Args:
            name: Capability name
            handler: Function to handle the capability
        """
        self._capabilities[name] = handler

    def get_capability_handler(self, capability: str) -> Callable | None:
        """
        Get a capability handler.

        Args:
            capability: Capability name

        Returns:
            Handler function or None if not found
        """
        return self._capabilities.get(capability)

    def shutdown(self) -> bool:
        """
        Shutdown the plugin.

        Called when plugin is being unloaded.

        Returns:
            True if shutdown successfully
        """
        try:
            self.state = PluginState.UNLOADED
            self._enabled = False
            return True
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")
            return False

    def enable(self) -> bool:
        """Enable the plugin."""
        if self.state in (PluginState.DISABLED, PluginState.FAILED):
            self._enabled = True
            self.logger.info(f"Plugin {self.manifest.name} enabled")
            return True
        return False

    def disable(self) -> bool:
        """Disable the plugin."""
        self._enabled = False
        self.state = PluginState.DISABLED
        self.logger.info(f"Plugin {self.manifest.name} disabled")
        return True

    def get_status(self) -> dict[str, Any]:
        """
        Get plugin status information.

        Returns:
            Status dictionary with current state and metadata
        """
        return {
            "name": self.manifest.name,
            "version": self.manifest.version,
            "category": self.manifest.category.value,
            "state": self.state.value,
            "enabled": self._enabled,
            "is_optional": self.manifest.is_optional,
            "capabilities": len(self.manifest.capabilities),
            "loaded_at": (
                self.manifest.loaded_at.isoformat() if self.manifest.loaded_at else None
            ),
            "error": str(self._error) if self._error else None,
        }

    def get_error(self) -> Exception | None:
        """Get the last error that occurred."""
        return self._error

    def set_error(self, error: Exception) -> None:
        """Set an error for this plugin."""
        self._error = error
        if self.state != PluginState.FAILED:
            self.state = PluginState.FAILED

    def __repr__(self) -> str:
        return f"<Plugin {self.manifest.name} v{self.manifest.version} [{self.state.value}]>"
