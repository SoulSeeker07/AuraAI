"""
Aura Plugin System

A modular, extensible plugin ecosystem for Aura AI.
All plugins must implement the Plugin interface for consistent behavior.
"""

from .plugin_interface import Plugin, PluginCategory, PluginManifest, PluginState
from .plugin_manager import PluginManager
from .plugin_registry import PluginRegistry

__version__ = "1.0.0"
__all__ = [
    "Plugin",
    "PluginManifest",
    "PluginState",
    "PluginCategory",
    "PluginRegistry",
    "PluginManager",
]
