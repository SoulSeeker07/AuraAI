"""
Vision Context Coordinator

Coordinates vision processing across all components.
"""

import logging
from typing import Any

from .models import ImageType, VisionContext

logger = logging.getLogger(__name__)


class VisionContextCoordinator:
    """
    Orchestrates vision processing and context creation.

    The coordinator manages the vision processing pipeline and
    ensures all components work together seamlessly.
    """

    def __init__(self):
        """Initialize the vision context coordinator."""
        self.current_context: VisionContext | None = None
        self.last_context: VisionContext | None = None

    def create_context(
        self, image_path: str, image_type: ImageType = ImageType.SCREENSHOT, **kwargs
    ) -> VisionContext:
        """
        Create a new VisionContext.

        Args:
            image_path: Path to the image
            image_type: Type of image being processed
            **kwargs: Additional context data

        Returns:
            New VisionContext instance
        """
        context = VisionContext(image_type=image_type, image_path=image_path, **kwargs)

        logger.info(f"Created VisionContext for {image_type.value}: {image_path}")
        return context

    def update_with_ocr(
        self,
        context: VisionContext,
        text: str,
        blocks: list = None,
        confidence: float = 1.0,
    ) -> VisionContext:
        """
        Update context with OCR results.

        Args:
            context: VisionContext to update
            text: Detected text
            blocks: Text blocks with metadata
            confidence: OCR confidence score

        Returns:
            Updated VisionContext
        """
        context.detected_text = text
        context.text_blocks = blocks or []
        context.confidence = confidence

        # Add to metadata
        context.metadata["ocr_processed"] = True

        logger.debug(f"Updated context with OCR: {len(text)} characters")
        return context

    def update_with_objects(
        self, context: VisionContext, objects: list, bounding_boxes: list = None
    ) -> VisionContext:
        """
        Update context with object detection results.

        Args:
            context: VisionContext to update
            objects: Detected objects
            bounding_boxes: Bounding boxes for each object

        Returns:
            Updated VisionContext
        """
        context.objects = objects
        context.bounding_boxes = bounding_boxes or []

        context.metadata["object_detection_processed"] = True

        logger.debug(f"Updated context with {len(objects)} objects")
        return context

    def update_with_layout(
        self,
        context: VisionContext,
        layout: dict[str, Any],
        elements: list = None,
        sections: list = None,
    ) -> VisionContext:
        """
        Update context with layout analysis.

        Args:
            context: VisionContext to update
            layout: Layout information
            elements: Detected layout elements
            sections: Detected sections

        Returns:
            Updated VisionContext
        """
        context.layout = layout
        context.elements = elements or []
        context.sections = sections or []

        context.metadata["layout_analysis_processed"] = True

        logger.debug("Updated context with layout analysis")
        return context

    def update_with_tables(
        self, context: VisionContext, tables: list, found_tables: list = None
    ) -> VisionContext:
        """
        Update context with table detection results.

        Args:
            context: VisionContext to update
            tables: Detected tables
            found_tables: List of table locations

        Returns:
            Updated VisionContext
        """
        context.tables = tables
        context.tables_found = found_tables or []

        context.metadata["table_detection_processed"] = True

        logger.debug(f"Updated context with {len(tables)} tables")
        return context

    def update_with_code(
        self, context: VisionContext, code_snippets: list, found_code: list = None
    ) -> VisionContext:
        """
        Update context with code detection results.

        Args:
            context: VisionContext to update
            code_snippets: Detected code snippets
            found_code: List of code locations

        Returns:
            Updated VisionContext
        """
        context.code_snippets = code_snippets
        context.code_found = found_code or []

        context.metadata["code_detection_processed"] = True

        logger.debug(f"Updated context with {len(code_snippets)} code snippets")
        return context

    def update_with_ui_analysis(
        self,
        context: VisionContext,
        buttons: list,
        menus: list,
        dialogs: list,
        forms: list,
        notifications: list,
    ) -> VisionContext:
        """
        Update context with UI analysis results.

        Args:
            context: VisionContext to update
            buttons: Detected buttons
            menus: Detected menus
            dialogs: Detected dialogs
            forms: Detected forms
            notifications: Detected notifications

        Returns:
            Updated VisionContext
        """
        context.buttons = buttons
        context.menus = menus
        context.dialogs = dialogs
        context.forms = forms
        context.notifications = notifications

        context.metadata["ui_analysis_processed"] = True

        logger.debug(
            f"Updated context with UI analysis: "
            f"{len(buttons)} buttons, {len(menus)} menus, "
            f"{len(dialogs)} dialogs, {len(forms)} forms, "
            f"{len(notifications)} notifications"
        )
        return context

    def update_with_network_analysis(
        self,
        context: VisionContext,
        devices: list,
        connections: list,
        ip_addresses: list,
        vlan_ids: list,
        interface_names: list,
    ) -> VisionContext:
        """
        Update context with network diagram analysis.

        Args:
            context: VisionContext to update
            devices: Detected network devices
            connections: Network connections
            ip_addresses: IP addresses found
            vlan_ids: VLAN IDs found
            interface_names: Interface names found

        Returns:
            Updated VisionContext
        """
        context.network_devices = devices
        context.network_connections = connections
        context.ip_addresses = ip_addresses
        context.vlan_ids = vlan_ids
        context.interface_names = interface_names

        context.metadata["network_analysis_processed"] = True

        logger.debug(
            f"Updated context with network analysis: "
            f"{len(devices)} devices, {len(connections)} connections, "
            f"{len(ip_addresses)} IPs"
        )
        return context

    def update_with_summary(
        self,
        context: VisionContext,
        summary: str,
        analysis: str = "",
        description: str = "",
    ) -> VisionContext:
        """
        Update context with vision model analysis.

        Args:
            context: VisionContext to update
            summary: High-level summary
            analysis: Detailed analysis
            description: Descriptive text

        Returns:
            Updated VisionContext
        """
        context.summary = summary
        context.analysis = analysis
        context.description = description

        context.metadata["vision_model_processed"] = True

        logger.debug("Updated context with vision model analysis")
        return context

    def update_with_errors(
        self, context: VisionContext, errors: list, warnings: list = None
    ) -> VisionContext:
        """
        Update context with error detection.

        Args:
            context: VisionContext to update
            errors: Detected errors
            warnings: Detected warnings

        Returns:
            Updated VisionContext
        """
        context.errors_detected = errors
        context.warnings = warnings or []

        context.metadata["error_detection_processed"] = True

        logger.debug(f"Updated context with {len(errors)} errors")
        return context

    def finalize_context(self, context: VisionContext) -> VisionContext:
        """
        Mark context as complete and save it.

        Args:
            context: VisionContext to finalize

        Returns:
            Finalized VisionContext
        """
        context.metadata["finalized"] = True
        context.metadata["finalized_at"] = datetime.now().isoformat()

        logger.info(f"Finalized VisionContext: {context.image_path}")
        logger.info(f"  - Image type: {context.image_type.value}")
        logger.info(f"  - Text detected: {len(context.detected_text)} chars")
        logger.info(f"  - Objects: {len(context.objects)}")
        logger.info(f"  - Tables: {len(context.tables)}")
        logger.info(f"  - Code: {len(context.code_snippets)}")

        self.last_context = context
        return context

    def get_context_info(self, context: VisionContext) -> dict[str, Any]:
        """
        Get information about the vision context.

        Args:
            context: VisionContext to analyze

        Returns:
            Dictionary with context information
        """
        return {
            "image_path": context.image_path,
            "image_type": context.image_type.value,
            "dimensions": {
                "width": context.image_width,
                "height": context.image_height,
            },
            "ocr": {
                "has_text": context.has_text(),
                "text_length": len(context.detected_text),
                "confidence": context.confidence,
            },
            "detection": {
                "objects": len(context.objects),
                "tables": len(context.tables),
                "code": len(context.code_snippets),
                "diagrams": len(context.diagrams),
            },
            "ui_elements": {
                "buttons": len(context.buttons),
                "menus": len(context.menus),
                "dialogs": len(context.dialogs),
            },
            "network": {
                "devices": len(context.network_devices),
                "connections": len(context.network_connections),
                "ip_addresses": len(context.ip_addresses),
            },
            "errors_detected": len(context.errors_detected),
            "warnings": len(context.warnings),
            "has_tables": context.has_tables(),
            "has_code": context.has_code(),
            "has_diagrams": context.has_diagrams(),
            "has_errors": context.has_errors(),
            "has_ui_elements": context.has_ui_elements(),
        }

    def should_use_llm(self, context: VisionContext) -> bool:
        """
        Determine if LLM should be invoked for this context.

        Uses text-based heuristics:
        - If there's significant text, UI elements, or network data, consider using LLM
        - If only minimal text and no structured data, OCR-only might be enough

        Args:
            context: VisionContext to analyze

        Returns:
            True if LLM should be used, False otherwise
        """
        # Heuristic: Use LLM if there's substantial content to analyze
        text_score = len(context.detected_text) / (
            context.image_width * context.image_height * 0.01
        )
        object_score = len(context.objects)
        ui_score = (
            len(context.buttons)
            + len(context.menus)
            + len(context.dialogs)
            + len(context.forms)
            + len(context.notifications)
        )
        network_score = len(context.network_devices) + len(context.network_connections)
        table_score = len(context.tables)
        code_score = len(context.code_snippets)

        total_score = (
            text_score
            + object_score
            + ui_score
            + network_score
            + table_score
            + code_score
        )

        # Use LLM if total score is above threshold
        return total_score > 5.0

    def merge_contexts(self, *contexts: VisionContext) -> VisionContext:
        """
        Merge multiple vision contexts into one.

        Args:
            *contexts: VisionContext instances to merge

        Returns:
            Merged VisionContext
        """
        if not contexts:
            raise ValueError("At least one context is required")

        # Start with the first context
        merged = contexts[0].__class__(
            image_type=contexts[0].image_type,
            image_path=contexts[0].image_path,
            image_width=contexts[0].image_width,
            image_height=contexts[0].image_height,
            capture_time=contexts[0].capture_time,
        )

        # Merge all fields
        for context in contexts[1:]:
            merged.detected_text += "\n" + context.detected_text
            merged.objects.extend(context.objects)
            merged.bounding_boxes.extend(context.bounding_boxes)
            merged.layout = {**merged.layout, **context.layout}
            merged.elements.extend(context.elements)
            merged.sections.extend(context.sections)
            merged.tables.extend(context.tables)
            merged.code_snippets.extend(context.code_snippets)
            merged.diagrams.extend(context.diagrams)
            merged.buttons.extend(context.buttons)
            merged.menus.extend(context.menus)
            merged.dialogs.extend(context.dialogs)
            merged.forms.extend(context.forms)
            merged.notifications.extend(context.notifications)
            merged.network_devices.extend(context.network_devices)
            merged.network_connections.extend(context.network_connections)
            merged.ip_addresses.extend(context.ip_addresses)
            merged.vlan_ids.extend(context.vlan_ids)
            merged.interface_names.extend(context.interface_names)
            merged.errors_detected.extend(context.errors_detected)
            merged.warnings.extend(context.warnings)

        logger.info(f"Merged {len(contexts)} vision contexts")
        return merged
