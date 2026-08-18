"""
Aura Filesystem Plugin
======================
Plugin for desktop filesystem operations (CRUD, search, compression, metadata).
"""

import logging
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest
from src.desktop.native.managers.file_manager import FileManager

logger = logging.getLogger(__name__)


class FilesystemPlugin(Plugin):
    """
    Filesystem Plugin for Aura.
    """

    def __init__(self, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = PluginManifest(
                name="filesystem",
                version="1.0.0",
                author="Aura AI",
                description="Filesystem management and manipulation plugin.",
                category=PluginCategory.FILESYSTEM,
                capabilities=[
                    "file.create",
                    "file.write",
                    "file.read",
                    "file.delete",
                    "file.copy",
                    "file.exists",
                    "file.info",
                    "file.list",
                    "file.size",
                    "file.find_content",
                    "file.mkdir",
                    "file.rmdir",
                    "file.compress",
                    "file.decompress",
                    "file.open_with",
                ],
            )
        super().__init__(manifest)
        self.file_manager: FileManager | None = None

    def load(self) -> bool:
        try:
            self.file_manager = FileManager()
            self.file_manager.initialize()
            self.state = "initialized"
            return True
        except Exception as e:
            logger.error(f"Failed to load Filesystem Plugin: {e}")
            self.set_error(e)
            return False

    def initialize(self) -> bool:
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        return capability.startswith("file.") or capability in self.manifest.capabilities

    def execute(self, capability: str, **kwargs: Any) -> Any:
        if not self.file_manager:
            raise RuntimeError("FileManager is not initialized")
        return self.file_manager.execute(capability=capability, arguments=kwargs)
