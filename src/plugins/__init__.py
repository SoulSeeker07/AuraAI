"""
Aura Plugin System

A modular, extensible plugin ecosystem for Aura AI.
All plugins must implement the Plugin interface for consistent behavior.
"""

from .plugin_interface import Plugin, PluginCategory, PluginManifest, PluginState
from .plugin_manager import PluginManager
from .plugin_registry import PluginRegistry

# Extend package path to include the root plugins directory so that plugin submodules
# (plugins.calendar, plugins.email, etc.) are always resolvable regardless of whether
# sys.path prioritizes 'src' or project root.
from pathlib import Path
_root_plugins = (Path(__file__).resolve().parents[2] / "plugins").resolve()
if _root_plugins.is_dir() and str(_root_plugins) not in __path__:
    __path__.append(str(_root_plugins))

__version__ = "1.0.0"
__all__ = [
    "Plugin",
    "PluginManifest",
    "PluginState",
    "PluginCategory",
    "PluginRegistry",
    "PluginManager",
]
