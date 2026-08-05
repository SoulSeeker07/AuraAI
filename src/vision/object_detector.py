"""
Object Detector

Detects objects in images using various techniques.
"""

import logging
from typing import Any

import cv2
import numpy as np

from .models import ImageType

logger = logging.getLogger(__name__)


class ObjectDetector:
    """
    Detects objects in images.

    Provides detection for:
    - UI elements (buttons, menus, dialogs, etc.)
    - Text blocks and regions
    - Code snippets
    - General objects using pre-trained models
    """

    def __init__(self):
        """Initialize the object detector."""
        # In production, load pre-trained models here
        self.model = None
        self.confidence_threshold = 0.5

    def detect_objects(
        self, image: np.ndarray, image_type: ImageType = ImageType.SCREENSHOT
    ) -> tuple:
        """
        Detect objects in an image.

        Args:
            image: Image to analyze
            image_type: Type of image

        Returns:
            Tuple of (detected_objects, bounding_boxes)
        """
        logger.info(f"Detecting objects in {image_type.value} image")

        # Based on image type, use specialized detection
        if image_type == ImageType.SCREENSHOT:
            return self._detect_ui_elements(image)
        elif image_type == ImageType.DOCUMENT:
            return self._detect_document_elements(image)
        elif image_type == ImageType.CODE:
            return self._detect_code_elements(image)
        else:
            return self._detect_generic_objects(image)

    def _detect_ui_elements(self, image: np.ndarray) -> tuple:
        """
        Detect UI elements in a screenshot.

        Args:
            image: Screenshot image

        Returns:
            Tuple of (detected_objects, bounding_boxes)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Find text regions
        text_regions = self._find_text_regions(gray, image)

        # Detect buttons (rectangle-like regions with text)
        buttons = self._detect_buttons(image, text_regions)

        # Detect menus
        menus = self._detect_menus(image, text_regions)

        # Detect dialogs
        dialogs = self._detect_dialogs(image, text_regions)

        # Combine all detections
        all_objects = text_regions + buttons + menus + dialogs

        # Extract bounding boxes
        bounding_boxes = self._extract_bounding_boxes(all_objects)

        logger.info(
            f"Detected {len(all_objects)} UI elements: "
            f"{len(text_regions)} text regions, "
            f"{len(buttons)} buttons, "
            f"{len(menus)} menus, "
            f"{len(dialogs)} dialogs"
        )

        return all_objects, bounding_boxes

    def _find_text_regions(
        self, gray: np.ndarray, original: np.ndarray
    ) -> list[dict[str, Any]]:
        """Find text regions in an image."""
        # Use morphological operations to find text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
        morphed = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)

        # Find contours
        contours, _ = cv2.findContours(morphed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        text_regions = []
        min_area = 100

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)

            # Skip too small or too large regions
            if w < 10 or h < 5 or w > 1000 or h > 500:
                continue

            # Get the ROI
            roi = original[y : y + h, x : x + w]

            text_regions.append(
                {
                    "type": "text_region",
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "area": area,
                    "roi": roi,
                }
            )

        return text_regions

    def _detect_buttons(
        self, image: np.ndarray, text_regions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect button-like elements."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        buttons = []

        # Find all rectangular regions
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            # Skip if too small or too large
            if area < 100 or area > 50000:
                continue

            # Check aspect ratio (buttons are typically not too tall or too wide)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.1 or aspect_ratio > 5:
                continue

            # Check if region contains text
            roi = image[y : y + h, x : x + w]
            if self._has_text_content(roi):
                buttons.append(
                    {
                        "type": "button",
                        "text": "",
                        "position": {"x": x, "y": y, "width": w, "height": h},
                        "area": area,
                    }
                )

        return buttons

    def _detect_menus(
        self, image: np.ndarray, text_regions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect menu items."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        menus = []
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < 100 or area > 20000:
                continue

            # Check if menu-like (tall and narrow or short and wide)
            aspect_ratio = w / h if h > 0 else 0

            # Typical menu aspect ratios
            if 0.5 < aspect_ratio < 3:
                roi = image[y : y + h, x : x + w]
                if self._has_text_content(roi):
                    menus.append(
                        {
                            "type": "menu_item",
                            "text": "",
                            "position": {"x": x, "y": y, "width": w, "height": h},
                            "area": area,
                        }
                    )

        return menus

    def _detect_dialogs(
        self, image: np.ndarray, text_regions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect dialog boxes."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        dialogs = []
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < 500 or area > 500000:
                continue

            # Check aspect ratio (dialogs are typically square-ish)
            aspect_ratio = w / h if h > 0 else 0
            if 0.7 < aspect_ratio < 1.3:
                roi = image[y : y + h, x : x + w]
                if self._has_text_content(roi):
                    dialogs.append(
                        {
                            "type": "dialog",
                            "text": "",
                            "position": {"x": x, "y": y, "width": w, "height": h},
                            "area": area,
                        }
                    )

        return dialogs

    def _detect_generic_objects(self, image: np.ndarray) -> tuple:
        """
        Detect generic objects using simple heuristics.

        Args:
            image: Image to analyze

        Returns:
            Tuple of (detected_objects, bounding_boxes)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        objects = []
        min_area = 200
        max_area = 500000

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            # Approximate contour
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

            # Simple shape classification
            num_vertices = len(approx)

            if num_vertices == 3:
                shape = "triangle"
            elif num_vertices == 4:
                shape = "rectangle"
            elif num_vertices == 5:
                shape = "pentagon"
            elif num_vertices >= 6:
                shape = "circle"
            else:
                shape = "unknown"

            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)

            objects.append(
                {
                    "type": shape,
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "area": area,
                }
            )

        bounding_boxes = self._extract_bounding_boxes(objects)

        logger.info(f"Detected {len(objects)} generic objects")

        return objects, bounding_boxes

    def _detect_document_elements(self, image: np.ndarray) -> tuple:
        """Detect document-specific elements (tables, paragraphs, etc.)."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Find text regions
        text_regions = self._find_text_regions(gray, image)

        # Detect paragraph-like regions
        paragraphs = self._detect_paragraphs(image, text_regions)

        # Detect table-like regions
        tables = self._detect_table_regions(image, text_regions)

        all_objects = text_regions + paragraphs + tables

        bounding_boxes = self._extract_bounding_boxes(all_objects)

        logger.info(f"Detected {len(all_objects)} document elements")

        return all_objects, bounding_boxes

    def _detect_code_elements(self, image: np.ndarray) -> tuple:
        """Detect code elements (lines of code, functions, etc.)."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect horizontal lines (code lines)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 10))
        horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)

        _, binary = cv2.threshold(
            horizontal_lines, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        code_elements = []
        min_length = 10

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            if w < min_length or h < 2:
                continue

            code_elements.append(
                {
                    "type": "code_line",
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "area": w * h,
                }
            )

        bounding_boxes = self._extract_bounding_boxes(code_elements)

        logger.info(f"Detected {len(code_elements)} code elements")

        return code_elements, bounding_boxes

    def _detect_paragraphs(
        self, image: np.ndarray, text_regions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect paragraph regions."""
        paragraphs = []
        min_area = 1000
        max_area = 50000

        for region in text_regions:
            area = region.get("area", 0)
            if area < min_area or area > max_area:
                continue

            # Check if region is wide enough for a paragraph
            x, y, w, h = region["position"].values()
            aspect_ratio = w / h if h > 0 else 0

            if aspect_ratio > 2:  # Wide regions are likely paragraphs
                paragraphs.append(
                    {"type": "paragraph", "position": region["position"], "area": area}
                )

        return paragraphs

    def _detect_table_regions(
        self, image: np.ndarray, text_regions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect table-like regions."""
        tables = []

        # Group text regions by proximity
        # This is a simplified approach
        grouped = []

        for region in text_regions:
            x, y, w, h = region["position"].values()
            area = w * h

            # Find nearby regions
            neighbors = []
            for other in text_regions:
                ox, oy, ow, oh = other["position"].values()
                dist = abs(x - ox) + abs(y - oy)

                if dist < 30 and area > 500:  # Close and substantial
                    neighbors.append(other)

            if len(neighbors) >= 2:
                # This looks like a table cell
                tables.append(
                    {
                        "type": "table_cell",
                        "position": region["position"],
                        "area": area,
                        "neighbors": len(neighbors),
                    }
                )

        return tables

    def _has_text_content(self, roi: np.ndarray) -> bool:
        """Check if a region contains text content."""
        # Convert to grayscale
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        # Calculate brightness
        brightness = np.mean(gray)

        # If region is too dark, it might be empty
        return brightness > 30

    def _extract_bounding_boxes(
        self, objects: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Extract bounding boxes from detected objects.

        Args:
            objects: Detected objects

        Returns:
            List of bounding boxes
        """
        boxes = []
        for obj in objects:
            pos = obj["position"]
            boxes.append(
                {
                    "x": pos["x"],
                    "y": pos["y"],
                    "width": pos["width"],
                    "height": pos["height"],
                }
            )
        return boxes
