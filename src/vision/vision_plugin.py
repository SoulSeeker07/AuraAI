"""
Vision Plugin

Plugin for integrating Vision System into Aura's Plugin System.
Provides vision capabilities to Aura through the plugin interface.
"""

import logging
from typing import Any

# Import plugin base class (assuming it exists in the project)
try:
    from plugins.plugin_base import Plugin
except ImportError:
    # Fallback if plugin base doesn't exist yet
    class Plugin:
        """Minimal Plugin base class for testing."""

        pass


from .models import ImageType, OCRSettings, ScreenshotSettings
from .vision_manager import VisionManager

logger = logging.getLogger(__name__)


class VisionPlugin(Plugin):
    """
    Vision Plugin for Aura.

    Provides vision capabilities including:
    - Screenshot capture and analysis
    - Object detection (buttons, menus, dialogs)
    - Layout analysis
    - UI element detection
    - Diagram analysis
    - Code snippet detection

    This plugin gives Aura "eyes" to understand the user's desktop.
    """

    def __init__(self):
        """Initialize the Vision Plugin."""
        super().__init__()

        # Vision Manager instance
        self.vision_manager: VisionManager | None = None

        # Plugin configuration
        self.config = {
            "enabled": True,
            "screenshot_settings": {
                "capture_type": "full_screen",
                "include_cursor": True,
                "include_timestamp": False,
            },
            "ocr_settings": {
                "provider": "local",
                "language": "eng",
                "table_detection": False,
                "code_detection": False,
                "diagram_detection": False,
            },
            "features": {
                "object_detection": True,
                "layout_analysis": True,
                "ui_analysis": True,
                "diagram_analysis": True,
                "code_detection": True,
            },
        }

        logger.info("Vision Plugin initialized")

    def on_load(self, config: dict[str, Any] = None) -> bool:
        """
        Called when the plugin is loaded.

        Args:
            config: Plugin configuration

        Returns:
            True if load successful
        """
        logger.info("Loading Vision Plugin")

        # Update configuration
        if config:
            self.config.update(config)

        # Check if enabled
        if not self.config.get("enabled", True):
            logger.warning("Vision Plugin is disabled")
            return False

        # Initialize Vision Manager
        try:
            screenshot_settings = ScreenshotSettings(
                **self.config.get("screenshot_settings", {})
            )
            ocr_settings = OCRSettings(**self.config.get("ocr_settings", {}))
            self.vision_manager = VisionManager(screenshot_settings, ocr_settings)

            # Configure features
            self._configure_features()

            logger.info("Vision Plugin loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Vision Plugin: {e}")
            return False

    def on_unload(self) -> bool:
        """
        Called when the plugin is unloaded.

        Returns:
            True if unload successful
        """
        logger.info("Unloading Vision Plugin")

        # Clean up resources
        self.vision_manager = None

        logger.info("Vision Plugin unloaded")
        return True

    def on_enable(self) -> bool:
        """
        Called when the plugin is enabled.

        Returns:
            True if enable successful
        """
        logger.info("Enabling Vision Plugin")

        if self.vision_manager:
            try:
                self._configure_features()
                logger.info("Vision Plugin enabled")
                return True
            except Exception as e:
                logger.error(f"Failed to enable Vision Plugin: {e}")
                return False
        return False

    def on_disable(self) -> bool:
        """
        Called when the plugin is disabled.

        Returns:
            True if disable successful
        """
        logger.info("Disabling Vision Plugin")

        # Vision Manager doesn't need special cleanup
        logger.info("Vision Plugin disabled")
        return True

    def on_config_change(self, new_config: dict[str, Any]) -> bool:
        """
        Called when plugin configuration changes.

        Args:
            new_config: New configuration

        Returns:
            True if configuration accepted
        """
        logger.info("Configuration changed for Vision Plugin")

        try:
            # Update configuration
            self.config.update(new_config)

            # Reload plugin with new configuration
            if self.vision_manager:
                self.on_unload()
                self.on_load(new_config)

            logger.info("Configuration change applied")
            return True
        except Exception as e:
            logger.error(f"Failed to apply configuration change: {e}")
            return False

    def _configure_features(self):
        """
        Configure vision features based on settings.
        """
        if not self.vision_manager:
            return

        # Configure screenshot settings
        screenshot_config = self.config.get("screenshot_settings", {})
        for key, value in screenshot_config.items():
            if hasattr(self.vision_manager.screenshot_settings, key):
                setattr(self.vision_manager.screenshot_settings, key, value)

        # Configure OCR settings
        ocr_config = self.config.get("ocr_settings", {})
        for key, value in ocr_config.items():
            if hasattr(self.vision_manager.ocr_settings, key):
                setattr(self.vision_manager.ocr_settings, key, value)

        # Enable/disable specific features
        features = self.config.get("features", {})
        for feature, enabled in features.items():
            self.vision_manager.enable_feature(feature, enabled)

    # Public API methods

    def capture_and_analyze(
        self, capture_type: str = "full_screen", **kwargs
    ) -> dict[str, Any]:
        """
        Capture screen and analyze it.

        Args:
            capture_type: Type of capture (full_screen, active_monitor, active_window, selected_region)
            **kwargs: Additional settings

        Returns:
            Dictionary with analysis results
        """
        if not self.vision_manager:
            return {"error": "Vision Manager not initialized"}

        try:
            context = self.vision_manager.capture_and_analyze(capture_type, **kwargs)

            # Convert context to dictionary
            result = self._context_to_dict(context)
            return result
        except Exception as e:
            logger.error(f"Capture and analyze failed: {e}")
            return {"error": str(e)}

    def capture_active_window_and_analyze(
        self, window_title: str = None
    ) -> dict[str, Any]:
        """
        Capture active window and analyze it.

        Args:
            window_title: Optional window title

        Returns:
            Dictionary with analysis results
        """
        if not self.vision_manager:
            return {"error": "Vision Manager not initialized"}

        try:
            context = self.vision_manager.capture_active_window_and_analyze(
                window_title
            )

            # Convert context to dictionary
            result = self._context_to_dict(context)
            return result
        except Exception as e:
            logger.error(f"Capture active window failed: {e}")
            return {"error": str(e)}

    def analyze_image(
        self, image_path: str, image_type: ImageType = None
    ) -> dict[str, Any]:
        """
        Analyze an existing image file.

        Args:
            image_path: Path to image file
            image_type: Type of image (optional)

        Returns:
            Dictionary with analysis results
        """
        if not self.vision_manager:
            return {"error": "Vision Manager not initialized"}

        try:
            context = self.vision_manager.analyze_image(image_path, image_type)

            # Convert context to dictionary
            result = self._context_to_dict(context)
            return result
        except Exception as e:
            logger.error(f"Analyze image failed: {e}")
            return {"error": str(e)}

    def get_last_context_info(self) -> dict[str, Any]:
        """
        Get information about the last analyzed context.

        Returns:
            Dictionary with context information
        """
        if not self.vision_manager:
            return {"error": "Vision Manager not initialized"}

        return self.vision_manager.get_context_info()

    def get_last_image_path(self) -> str | None:
        """
        Get path of last analyzed image.

        Returns:
            Path to last image or None
        """
        if not self.vision_manager:
            return None
        return self.vision_manager.get_last_image_path()

    def get_last_context(self) -> dict[str, Any] | None:
        """
        Get the last processed vision context.

        Returns:
            Vision context dictionary or None
        """
        if not self.vision_manager:
            return None

        context = self.vision_manager.get_last_context()
        if context:
            return self._context_to_dict(context)
        return None

    def get_capabilities(self) -> dict[str, Any]:
        """
        Get plugin capabilities.

        Returns:
            Dictionary with capabilities
        """
        return {
            "name": "Vision System",
            "version": "1.0.0",
            "description": "Provides vision capabilities including screenshot analysis, object detection, layout analysis, UI element detection, diagram analysis, and code snippet detection.",
            "capabilities": [
                "Screenshot capture",
                "Object detection",
                "Layout analysis",
                "UI element detection",
                "Diagram analysis",
                "Code snippet detection",
                "OCR support",
            ],
            "features": self.config.get("features", {}),
            "supported_image_types": [
                "screenshot",
                "document",
                "diagram",
                "code",
                "ui",
                "network",
                "whiteboard",
                "photo",
            ],
        }

    def _context_to_dict(self, context) -> dict[str, Any]:
        """
        Convert VisionContext to dictionary.

        Args:
            context: VisionContext object

        Returns:
            Dictionary representation
        """
        if not hasattr(context, "__dict__"):
            return {}

        result = {}
        for key, value in context.__dict__.items():
            # Convert numpy arrays and complex objects to serializable formats
            if hasattr(value, "tolist"):
                result[key] = value.tolist()
            elif isinstance(value, (list, dict, str, int, float, bool)):
                result[key] = value
            else:
                result[key] = str(value)

        return result

    @staticmethod
    def get_plugin_info() -> dict[str, Any]:
        """
        Get plugin metadata.

        Returns:
            Dictionary with plugin metadata
        """
        return {
            "name": "vision",
            "version": "1.0.0",
            "author": "Aura AI",
            "description": "Vision System Plugin",
            "category": "vision",
            "dependencies": ["opencv-python", "numpy", "Pillow"],
        }
