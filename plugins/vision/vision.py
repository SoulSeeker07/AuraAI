"""
Aura Vision Plugin
==================
Plugin for integrating Vision System into Aura's Plugin System.
Provides desktop screenshot analysis, OCR, and object detection.
"""

import logging
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest
from src.vision.vision_manager import VisionManager

logger = logging.getLogger(__name__)


class VisionPlugin(Plugin):
    """
    Vision Plugin for Aura.

    Provides vision capabilities including:
    - Screenshot capture and analysis
    - Object detection (buttons, menus, dialogs)
    - Layout analysis
    - UI element detection
    - OCR support
    """

    def __init__(self, manifest: PluginManifest | None = None):
        """Initialize Vision Plugin."""
        if manifest is None:
            manifest = PluginManifest(
                name="vision",
                version="1.0.0",
                author="Aura AI",
                description="Vision system plugin for desktop capture, OCR, and UI analysis.",
                category=PluginCategory.VISION,
                capabilities=[
                    "screenshot",
                    "ocr",
                    "object_detection",
                    "layout_analysis",
                    "ui_analysis",
                ],
            )
        super().__init__(manifest)
        self.vision_manager: VisionManager | None = None

    def load(self) -> bool:
        """Load the Vision plugin and instantiate VisionManager."""
        try:
            logger.info("Loading Vision Plugin...")
            self.vision_manager = VisionManager()
            self.state = "initialized"
            logger.info("Vision Plugin loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Vision Plugin: {e}")
            self.set_error(e)
            return False

    def initialize(self) -> bool:
        """Initialize Vision plugin."""
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        """Check if plugin handles capability."""
        return capability in self.manifest.capabilities

    def execute(self, capability: str, **kwargs) -> Any:
        """Execute a vision capability."""
        if not self.vision_manager:
            raise RuntimeError("VisionManager is not initialized")

        if capability == "screenshot":
            return self.vision_manager.capture_and_analyze(**kwargs)
        elif capability == "ocr":
            return self.vision_manager.capture_and_analyze(
                capture_type="full_screen", **kwargs
            )
        else:
            return self.vision_manager.capture_and_analyze(**kwargs)
