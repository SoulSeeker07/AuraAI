"""
AuraAI Plugins Package

This package contains all AuraAI plugins including:
- desktop, filesystem, vision, voice
- engineering, git, calendar, email
- networking, office, terminal
- knowledge, mcp, browser
"""

from .shared.plugin_manager import PluginManager

__all__ = ["PluginManager"]
