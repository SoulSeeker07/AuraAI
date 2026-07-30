"""
Aura Plugin System

A modular, extensible plugin ecosystem for Aura AI.
All plugins must implement the Plugin interface for consistent behavior.
"""

from .plugin_interface import (
    Plugin,
    PluginManifest,
    PluginState,
    PluginCategory
)

from .plugin_registry import PluginRegistry
from .plugin_manager import PluginManager

__version__ = "1.0.0"
__all__ = [
    'Plugin',
    'PluginManifest',
    'PluginState',
    'PluginCategory',
    'PluginRegistry',
    'PluginManager'
]
