"""
Aura Terminal Plugin
====================
Plugin for shell command execution and background terminal sessions.
"""

import logging
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest
from src.desktop.native.managers.terminal_manager import TerminalManager

logger = logging.getLogger(__name__)


class TerminalPlugin(Plugin):
    """
    Terminal / Shell Plugin for Aura.
    """

    def __init__(self, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = PluginManifest(
                name="terminal",
                version="1.0.0",
                author="Aura AI",
                description="Terminal and shell execution plugin.",
                category=PluginCategory.TERMINAL,
                capabilities=[
                    "terminal.execute",
                    "terminal.execute_async",
                    "terminal.send_input",
                    "terminal.kill_session",
                    "terminal.get_output",
                    "terminal.list_sessions",
                    "terminal.get_cwd",
                    "terminal.set_cwd",
                    "terminal.get_env",
                    "terminal.set_env",
                ],
            )
        super().__init__(manifest)
        self.terminal_manager: TerminalManager | None = None

    def load(self) -> bool:
        try:
            self.terminal_manager = TerminalManager()
            self.terminal_manager.initialize()
            self.state = "initialized"
            return True
        except Exception as e:
            logger.error(f"Failed to load Terminal Plugin: {e}")
            self.set_error(e)
            return False

    def initialize(self) -> bool:
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        return capability in self.manifest.capabilities or capability.startswith("terminal.")

    def execute(self, capability: str, **kwargs: Any) -> Any:
        if not self.terminal_manager:
            raise RuntimeError("TerminalManager is not initialized")
        return self.terminal_manager.execute(capability=capability, arguments=kwargs)
