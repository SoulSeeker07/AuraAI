"""
Vision Manager

Main orchestrator for the Vision System.
Coordinates all vision components to provide desktop vision capabilities.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np

from .code_detector import CodeDetector
from .diagram_analyzer import DiagramAnalyzer
from .image_loader import ImageLoader
from .layout_analyzer import LayoutAnalyzer
from .models import (
    ImageType,
    OCRSettings,
    ScreenshotSettings,
    VisionContext,
    VisionProvider,
)
from .object_detector import ObjectDetector
from .preprocessing import ImagePreprocessor
from .screenshot_manager import ScreenshotManager
from .ui_analyzer import UIAnalyzer
from .vision_context import VisionContextCoordinator

logger = logging.getLogger(__name__)


class VisionManager:
    """
    Main coordinator for the Vision System.

    The Vision Manager provides Aura's "eyes" by coordinating:
    - Screenshot capture
    - Image preprocessing
    - OCR processing
    - Object detection
    - Layout analysis
    - UI analysis
    - Vision model integration
    """

    def __init__(
        self,
        screenshot_settings: ScreenshotSettings = None,
        ocr_settings: OCRSettings = None,
    ):
        """
        Initialize the vision manager.

        Args:
            screenshot_settings: Settings for screenshot capture
            ocr_settings: Settings for OCR processing
        """
        self.screenshot_settings = screenshot_settings or ScreenshotSettings()
        self.ocr_settings = ocr_settings or OCRSettings()

        # Initialize components
        self.screenshot_manager = ScreenshotManager(self.screenshot_settings)
        self.image_loader = ImageLoader()
        self.image_preprocessor = ImagePreprocessor(self.ocr_settings)
        self.coordinator = VisionContextCoordinator()

        # Initialize analyzers
        self.object_detector = ObjectDetector()
        self.layout_analyzer = LayoutAnalyzer()
        self.ui_analyzer = UIAnalyzer()
        self.diagram_analyzer = DiagramAnalyzer()
        self.code_detector = CodeDetector()

        # Store last processed image
        self.last_image_path: str | None = None
        self.last_image_type: ImageType | None = None

        logger.info("Vision Manager initialized")

    def capture_and_analyze(
        self, capture_type: str = "full_screen", **kwargs
    ) -> VisionContext:
        """
        Capture screen and analyze it.

        Args:
            capture_type: Type of capture (full_screen, active_monitor, active_window, selected_region)
            **kwargs: Additional settings or arguments

        Returns:
            VisionContext with analysis results
        """
        logger.info(f"Capturing and analyzing screen: {capture_type}")

        # Update screenshot settings
        if capture_type != self.screenshot_settings.capture_type:
            self.screenshot_settings.capture_type = capture_type
            self.screenshot_settings.selected_region = kwargs.get("selected_region")
            self.screenshot_settings.monitor_index = kwargs.get("monitor_index", 0)

        with self.screenshot_manager.capture_scoped(capture_type=capture_type, **kwargs) as screenshot_path:
            self.last_image_path = screenshot_path

            # Load image
            img, image_type = self.image_loader.load_image(screenshot_path)
            self.last_image_type = image_type

            # Create vision context
            context = self.coordinator.create_context(
                image_path=screenshot_path,
                image_type=image_type,
                image_width=img.shape[1] if len(img.shape) == 3 else img.shape[0],
                image_height=img.shape[0] if len(img.shape) == 3 else img.shape[1],
            )

            # Preprocess image
            try:
                img, dims = self.image_preprocessor.preprocess_image(screenshot_path)
                context.metadata["preprocessing"] = {
                    "original_dims": (img.shape[1], img.shape[0]),
                    "processed_dims": dims,
                    "deskewed": True,
                    "rotated": True,
                }
            except Exception as e:
                logger.warning(f"Preprocessing failed: {e}")

            # Run analysis pipeline
            self._run_analysis_pipeline(context, img, screenshot_path)

            # Finalize and return
            context = self.coordinator.finalize_context(context)
            return context

    def capture_active_window_and_analyze(
        self, window_title: str = None
    ) -> VisionContext:
        """
        Capture active window and analyze it.

        Args:
            window_title: Optional window title to capture

        Returns:
            VisionContext with analysis results
        """
        logger.info("Capturing and analyzing active window")

        cap_type = "window_by_title" if window_title else "active_window"
        with self.screenshot_manager.capture_scoped(capture_type=cap_type, window_title=window_title) as screenshot_path:
            self.last_image_path = screenshot_path

            # Load and preprocess
            img, image_type = self.image_loader.load_image(screenshot_path)
            context = self.coordinator.create_context(
                image_path=screenshot_path,
                image_type=image_type,
                image_width=img.shape[1] if len(img.shape) == 3 else img.shape[0],
                image_height=img.shape[0] if len(img.shape) == 3 else img.shape[1],
            )

            # Run analysis pipeline
            self._run_analysis_pipeline(context, img, screenshot_path)

            return self.coordinator.finalize_context(context)

    def analyze_image(
        self, image_path: str, image_type: ImageType = None
    ) -> VisionContext:
        """
        Analyze an existing image file.

        Args:
            image_path: Path to image file
            image_type: Type of image (optional, auto-detected if not provided)

        Returns:
            VisionContext with analysis results
        """
        logger.info(f"Analyzing image: {image_path}")

        # Load image
        img, detected_type = self.image_loader.load_image(image_path)
        if image_type is None:
            image_type = detected_type

        self.last_image_path = image_path
        self.last_image_type = image_type

        # Create vision context
        context = self.coordinator.create_context(
            image_path=image_path,
            image_type=image_type,
            image_width=img.shape[1] if len(img.shape) == 3 else img.shape[0],
            image_height=img.shape[0] if len(img.shape) == 3 else img.shape[1],
        )

        # Run analysis pipeline
        self._run_analysis_pipeline(context, img, image_path)

        return self.coordinator.finalize_context(context)

    def _run_analysis_pipeline(
        self, context: VisionContext, img: np.ndarray, image_path: str
    ):
        """
        Run the complete vision analysis pipeline.

        Args:
            context: VisionContext to update
            img: Preprocessed image
            image_path: Path to image
        """
        context.image_width = img.shape[1]
        context.image_height = img.shape[0]

        # 1. Update context with basic information
        if (
            not context.image_type or context.image_type == ImageType.UNKNOWN
        ) and image_path:
            suffix = Path(image_path).suffix
            context.image_type = self.image_loader._detect_image_type(suffix)
        elif not context.image_type:
            context.image_type = ImageType.SCREENSHOT

        # 2. Run object detection
        try:
            objects_result = self.object_detector.detect_objects(
                img, context.image_type
            )
            context.objects = objects_result.get("detected_objects", [])
            context.bounding_boxes = objects_result.get("bounding_boxes", [])
            context.buttons = objects_result.get("buttons", [])
            context.menus = objects_result.get("menus", [])
            context.dialogs = objects_result.get("dialogs", [])
            context.paragraphs = objects_result.get("paragraphs", [])
            context.table_regions = objects_result.get("table_regions", [])
            context.errors_detected = objects_result.get("errors", [])
            logger.info(f"Object detection complete: {len(context.objects)} objects")
        except Exception as e:
            logger.warning(f"Object detection failed: {e}")
            context.errors_detected.append(f"Object detection error: {str(e)}")

        # 3. Run layout analysis
        try:
            layout_result = self.layout_analyzer.analyze_layout(img, context.image_type)
            context.layout = layout_result.get("layout", {})
            context.title_bar = layout_result.get("title_bar", [])
            context.menu_bar = layout_result.get("menu_bar", [])
            context.content_area = layout_result.get("content_area", [])
            context.footer = layout_result.get("footer", [])
            context.scrollbars = layout_result.get("scrollbars", [])
            context.sidebar = layout_result.get("sidebar", [])
            context.margins = layout_result.get("margins", [])
            context.header = layout_result.get("header", [])
            context.columns = layout_result.get("columns", [])
            context.diagram_sections = layout_result.get("diagram_sections", [])
            context.elements = layout_result.get("elements", [])
            context.sections = layout_result.get("sections", [])
            logger.info(f"Layout analysis complete: {context.layout}")
        except Exception as e:
            logger.warning(f"Layout analysis failed: {e}")
            context.errors_detected.append(f"Layout analysis error: {str(e)}")

        # 4. Run UI analysis
        try:
            ui_result = self.ui_analyzer.analyze_ui(img, context.image_type)
            context.ui_analysis = ui_result
            context.buttons.extend(ui_result.get("buttons", []))
            context.menus.extend(ui_result.get("menus", []))
            context.dialogs.extend(ui_result.get("dialogs", []))
            context.forms.extend(ui_result.get("forms", []))
            context.notifications.extend(ui_result.get("notifications", []))
            context.tooltips.extend(ui_result.get("tooltips", []))
            context.input_fields.extend(ui_result.get("inputs", []))
            context.checkboxes.extend(ui_result.get("checkboxes", []))
            context.radio_buttons.extend(ui_result.get("radio_buttons", []))
            context.dropdowns.extend(ui_result.get("dropdowns", []))
            logger.info(
                f"UI analysis complete: {len(context.buttons)} buttons, "
                f"{len(context.menus)} menus, {len(context.dialogs)} dialogs"
            )
        except Exception as e:
            logger.warning(f"UI analysis failed: {e}")
            context.errors_detected.append(f"UI analysis error: {str(e)}")

        # 5. Run diagram analysis (if diagram-type image)
        try:
            if context.image_type in [
                ImageType.DIAGRAM,
                ImageType.NETWORK,
                ImageType.CIRCUIT,
            ]:
                diagram_result = self.diagram_analyzer.analyze_diagram(
                    img, context.image_type
                )
                context.diagram_analysis = diagram_result
                context.nodes.extend(diagram_result.get("nodes", []))
                context.connections.extend(diagram_result.get("connections", []))
                context.diagram_type = diagram_result.get("type", "unknown")
                context.diagram_complexity = diagram_result.get("complexity", "simple")
                context.network_devices = diagram_result.get("devices", [])
                context.ip_addresses.extend(diagram_result.get("ip_addresses", []))
                context.vlan_ids.extend(diagram_result.get("vlans", []))
                context.interface_names.extend(
                    diagram_result.get("interface_names", [])
                )
                logger.info(f"Diagram analysis complete: {len(context.nodes)} nodes")
            else:
                logger.info("Skipping diagram analysis for non-diagram image type")
        except Exception as e:
            logger.warning(f"Diagram analysis failed: {e}")
            context.errors_detected.append(f"Diagram analysis error: {str(e)}")

        # 6. Run code detection (if code-type image)
        try:
            if context.image_type == ImageType.CODE:
                code_result = self.code_detector.detect_code(img, context.image_type)
                context.code_analysis = code_result
                context.code_language = code_result.get("language", "unknown")
                context.code_lines = code_result.get("lines", [])
                context.code_snippets = code_result.get("snippets", [])
                context.syntax_highlighting = code_result.get(
                    "has_syntax_highlighting", False
                )
                context.code_complexity = code_result.get("complexity", "simple")
                logger.info(
                    f"Code detection complete: {context.code_language}, "
                    f"{code_result.get('line_count', 0)} lines"
                )
            else:
                logger.info("Skipping code detection for non-code image type")
        except Exception as e:
            logger.warning(f"Code detection failed: {e}")
            context.errors_detected.append(f"Code detection error: {str(e)}")

        # Update summary
        self.coordinator.update_with_summary(
            context,
            f"Analyzed {context.image_type.value} image with {len(context.objects)} objects",
            description="Vision analysis complete",
        )

        logger.info(f"Analysis pipeline completed for {image_path}")

    def get_context_info(self) -> dict[str, Any]:
        """
        Get information about the last analyzed context.

        Returns:
            Dictionary with context information
        """
        ctx = self.coordinator.current_context or self.coordinator.last_context
        return self.coordinator.get_context_info(ctx)

    def should_use_llm(self) -> bool:
        """
        Determine if LLM should be invoked for current context.

        Returns:
            True if LLM should be used, False otherwise
        """
        ctx = self.coordinator.current_context or self.coordinator.last_context
        if ctx:
            return self.coordinator.should_use_llm(ctx)
        return False

    def get_last_context(self) -> VisionContext | None:
        """Get the last processed vision context."""
        return self.coordinator.current_context or self.coordinator.last_context

    def get_last_image_path(self) -> str | None:
        """Get the path of the last processed image."""
        return self.last_image_path

    def configure_ocr(self, provider: VisionProvider, **kwargs):
        """
        Configure OCR settings.

        Args:
            provider: OCR provider to use
            **kwargs: OCR settings (language, confidence_threshold, etc.)
        """
        self.ocr_settings.provider = provider

        for key, value in kwargs.items():
            if hasattr(self.ocr_settings, key):
                setattr(self.ocr_settings, key, value)

        # Update preprocessor settings
        self.image_preprocessor.settings = self.ocr_settings

        logger.info(f"OCR configured: {provider.value}")

    def configure_screenshot(self, capture_type: str = None, **kwargs):
        """
        Configure screenshot settings.

        Args:
            capture_type: Screenshot capture type
            **kwargs: Screenshot settings
        """
        if capture_type is not None:
            self.screenshot_settings.capture_type = capture_type

        for key, value in kwargs.items():
            if hasattr(self.screenshot_settings, key):
                setattr(self.screenshot_settings, key, value)

        # Update screenshot manager settings
        self.screenshot_manager.settings = self.screenshot_settings

        logger.info(f"Screenshot configured: {capture_type}")

    def enable_feature(self, feature: str, enabled: bool = True):
        """
        Enable or disable specific vision features.

        Args:
            feature: Feature to enable/disable
            enabled: Whether to enable (True) or disable (False)
        """
        features = {
            "auto_rotate": self.ocr_settings.auto_rotate,
            "deskew": self.ocr_settings.deskew,
            "table_detection": self.ocr_settings.table_detection,
            "code_detection": self.ocr_settings.code_detection,
            "diagram_detection": self.ocr_settings.diagram_detection,
            "include_cursor": self.screenshot_settings.include_cursor,
            "include_timestamp": self.screenshot_settings.include_timestamp,
        }

        if feature in features:
            setattr(self.ocr_settings, feature, enabled)
            setattr(self.screenshot_settings, feature, enabled)
            logger.info(f"Feature '{feature}' {'enabled' if enabled else 'disabled'}")
        else:
            logger.warning(f"Unknown feature: {feature}")
