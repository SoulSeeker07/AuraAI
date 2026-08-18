"""
Aura Desktop Control Plugin
===========================
Plugin for native desktop operations (window, audio, power, display, input).
"""

import logging
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest
from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry

logger = logging.getLogger(__name__)


class DesktopPlugin(Plugin):
    """
    Desktop Automation Plugin for Aura.
    """

    def __init__(self, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = PluginManifest(
                name="desktop",
                version="1.0.0",
                author="Aura AI",
                description="Desktop automation plugin for Windows OS control.",
                category=PluginCategory.DESKTOP,
                capabilities=[
                    "window.open",
                    "window.close",
                    "window.minimize",
                    "window.maximize",
                    "window.activate",
                    "audio.volume",
                    "audio.mute",
                    "power.sleep",
                    "power.lock",
                    "input.click",
                    "input.type_text",
                    "input.hotkey",
                ],
            )
        super().__init__(manifest)
        self.registry: NativeManagerRegistry | None = None

    def load(self) -> bool:
        try:
            self.registry = NativeManagerRegistry.get_instance()
            self.registry.discover()
            self.state = "initialized"
            return True
        except Exception as e:
            logger.error(f"Failed to load Desktop Plugin: {e}")
            self.set_error(e)
            return False

    def initialize(self) -> bool:
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        return True

    def execute(self, capability: str, **kwargs: Any) -> Any:
        if not self.registry:
            raise RuntimeError("NativeManagerRegistry is not initialized")
        mgr = self.registry.resolve(capability)
        if not mgr:
            raise ValueError(f"No manager found for capability: {capability}")
        return mgr.execute(capability=capability, arguments=kwargs)
