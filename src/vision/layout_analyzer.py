"""
Layout Analyzer

Analyzes and detects layout structures in images.
"""

import logging
from typing import Any

import cv2
import numpy as np

from .models import ImageType

logger = logging.getLogger(__name__)


class LayoutAnalyzer:
    """
    Analyzes layout structures in images.

    Provides layout detection for:
    - Page structure (headers, footers, body, margins)
    - Sections and subsections
    - Columns and rows
    - Block layouts
    """

    def __init__(self):
        """Initialize the layout analyzer."""
        self.min_block_size = 500
        self.min_section_size = 2000

    def analyze_layout(
        self, image: np.ndarray, image_type: ImageType = ImageType.SCREENSHOT
    ) -> tuple:
        """
        Analyze layout of an image.

        Args:
            image: Image to analyze
            image_type: Type of image

        Returns:
            Tuple of (layout_info, elements, sections)
        """
        logger.info(f"Analyzing layout in {image_type.value} image")

        # Based on image type, use specialized layout analysis
        if image_type == ImageType.SCREENSHOT:
            res = self._analyze_screenshot_layout(image)
        elif image_type == ImageType.DOCUMENT:
            res = self._analyze_document_layout(image)
        elif image_type == ImageType.DIAGRAM:
            res = self._analyze_diagram_layout(image)
        else:
            res = self._analyze_generic_layout(image)

        if isinstance(res, tuple) and len(res) == 3:
            layout_info, elements, sections = res
            return {
                "layout": layout_info,
                "elements": elements,
                "sections": sections,
                "header": (
                    layout_info.get("header") if isinstance(layout_info, dict) else None
                ),
                "footer": (
                    layout_info.get("footer") if isinstance(layout_info, dict) else None
                ),
            }
        return res

    def _analyze_screenshot_layout(self, image: np.ndarray) -> tuple:
        """
        Analyze screenshot layout (UI window layout).

        Args:
            image: Screenshot image

        Returns:
            Tuple of (layout_info, elements, sections)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect title bar (top, narrow region)
        title_bar = self._detect_title_bar(gray, image)

        # Detect menu bar (second from top)
        menu_bar = self._detect_menu_bar(gray, image, title_bar)

        # Detect main content area
        content_area = self._detect_content_area(image, title_bar, menu_bar)

        # Detect footer or status bar
        footer = self._detect_footer(gray, image, content_area)

        # Detect scroll areas
        scroll_areas = self._detect_scroll_areas(image, content_area)

        # Detect sidebar
        sidebar = self._detect_sidebar(image, content_area)

        # Compose layout info
        layout_info = {
            "title_bar": title_bar,
            "menu_bar": menu_bar,
            "content_area": content_area,
            "footer": footer,
            "sidebar": sidebar,
            "scroll_areas": scroll_areas,
            "orientation": "horizontal" if sidebar else "vertical",
        }

        # Extract layout elements
        elements = self._extract_layout_elements(layout_info)

        # Identify main sections
        sections = self._identify_sections(layout_info, elements)

        logger.info(
            f"Screenshot layout analyzed: {len(elements)} elements, "
            f"{len(sections)} sections"
        )

        return layout_info, elements, sections

    def _analyze_document_layout(self, image: np.ndarray) -> tuple:
        """
        Analyze document layout.

        Args:
            image: Document image

        Returns:
            Tuple of (layout_info, elements, sections)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect page margins
        margins = self._detect_page_margins(gray, image)

        # Detect header
        header = self._detect_header(gray, image, margins)

        # Detect footer
        footer = self._detect_document_footer(gray, image, margins)

        # Detect body
        body = self._detect_body(image, margins, header, footer)

        # Detect columns
        columns = self._detect_columns(gray, body)

        # Compose layout info
        layout_info = {
            "margins": margins,
            "header": header,
            "footer": footer,
            "body": body,
            "columns": columns,
            "orientation": "vertical" if columns else "horizontal",
        }

        # Extract layout elements
        elements = self._extract_layout_elements(layout_info)

        # Identify sections
        sections = self._identify_sections(layout_info, elements)

        logger.info(
            f"Document layout analyzed: {len(columns)} columns, "
            f"{len(elements)} elements"
        )

        return layout_info, elements, sections

    def _analyze_diagram_layout(self, image: np.ndarray) -> tuple:
        """
        Analyze diagram layout.

        Args:
            image: Diagram image

        Returns:
            Tuple of (layout_info, elements, sections)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect grid or nodes
        nodes = self._detect_nodes(gray, image)

        # Detect connections
        connections = self._detect_connections(image, nodes)

        # Compose layout info
        layout_info = {
            "nodes": nodes,
            "connections": connections,
            "node_count": len(nodes),
            "connection_count": len(connections),
        }

        # Extract layout elements
        elements = [{"type": "node", "position": node} for node in nodes]

        # Identify sections (groups of nodes)
        sections = self._identify_diagram_sections(nodes)

        logger.info(
            f"Diagram layout analyzed: {len(nodes)} nodes, "
            f"{len(connections)} connections"
        )

        return layout_info, elements, sections

    def _analyze_generic_layout(self, image: np.ndarray) -> tuple:
        """
        Analyze generic layout using edge detection.

        Args:
            image: Image to analyze

        Returns:
            Tuple of (layout_info, elements, sections)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect edges
        edges = cv2.Canny(gray, 50, 150)

        # Detect regions
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        regions = []
        min_area = 1000
        max_area = 500000

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            regions.append(
                {
                    "type": "region",
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "area": area,
                }
            )

        # Sort by y-coordinate to get vertical ordering
        regions.sort(key=lambda r: r["position"]["y"])

        layout_info = {"regions": regions, "region_count": len(regions)}

        elements = regions
        sections = self._identify_sections(layout_info, elements)

        logger.info(f"Generic layout analyzed: {len(regions)} regions")

        return layout_info, elements, sections

    def _detect_title_bar(self, gray: np.ndarray, image: np.ndarray) -> dict[str, Any]:
        """Detect window title bar."""
        height, width = gray.shape

        # Top narrow region
        top_height = int(height * 0.05)
        title_bar_roi = gray[0:top_height, :]

        # Calculate brightness
        brightness = np.mean(title_bar_roi)

        # If bright, likely a title bar
        if brightness > 50:
            x, y, w, h = 0, 0, width, top_height
            return {
                "type": "title_bar",
                "position": {"x": x, "y": y, "width": w, "height": h},
                "height": h,
                "brightness": brightness,
            }

        return None

    def _detect_menu_bar(
        self, gray: np.ndarray, image: np.ndarray, title_bar: dict
    ) -> dict[str, Any]:
        """Detect menu bar."""
        if not title_bar:
            return None

        height, width = gray.shape
        menu_y = title_bar["position"]["y"] + title_bar["position"]["height"]

        # Second narrow region
        menu_height = int(height * 0.03)
        menu_bar_roi = gray[menu_y : menu_y + menu_height, :]

        # Calculate brightness
        brightness = np.mean(menu_bar_roi)

        # If bright, likely a menu bar
        if brightness > 50:
            x, y, w, h = 0, menu_y, width, menu_height
            return {
                "type": "menu_bar",
                "position": {"x": x, "y": y, "width": w, "height": h},
                "height": h,
                "brightness": brightness,
            }

        return None

    def _detect_content_area(
        self, image: np.ndarray, title_bar: dict, menu_bar: dict
    ) -> dict[str, Any]:
        """Detect main content area."""
        if not title_bar or not menu_bar:
            height, width = image.shape[:2]
            x, y, w, h = 0, 0, width, height
            return {
                "type": "content_area",
                "position": {"x": x, "y": y, "width": w, "height": h},
            }

        # Content is everything below menu bar
        x = 0
        y = menu_bar["position"]["y"] + menu_bar["position"]["height"]
        height = image.shape[0] - y
        width = image.shape[1]

        return {
            "type": "content_area",
            "position": {"x": x, "y": y, "width": width, "height": height},
        }

    def _detect_footer(
        self, gray: np.ndarray, image: np.ndarray, content_area: dict
    ) -> dict[str, Any]:
        """Detect footer or status bar."""
        if not content_area:
            return None

        x, y, w, h = content_area["position"].values()

        # Bottom narrow region
        bottom_height = int(h * 0.05)
        footer_roi = gray[y + h - bottom_height : y + h, :]

        # Calculate brightness
        brightness = np.mean(footer_roi)

        # If bright, likely a footer
        if brightness > 50:
            return {
                "type": "footer",
                "position": {
                    "x": x,
                    "y": y + h - bottom_height,
                    "width": w,
                    "height": bottom_height,
                },
                "height": bottom_height,
                "brightness": brightness,
            }

        return None

    def _detect_scroll_areas(
        self, image: np.ndarray, content_area: dict
    ) -> list[dict[str, Any]]:
        """Detect scrollable areas."""
        if not content_area:
            return []

        x, y, w, h = content_area["position"].values()
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Check left and right sides for scrollbars
        scrollbar_width = int(w * 0.02)
        scroll_areas = []

        # Left scrollbar
        left_roi = gray[y : y + h, x : x + scrollbar_width]
        left_brightness = np.mean(left_roi)

        if left_brightness > 50:
            scroll_areas.append(
                {
                    "type": "left_scrollbar",
                    "position": {"x": x, "y": y, "width": scrollbar_width, "height": h},
                    "brightness": left_brightness,
                }
            )

        # Right scrollbar
        right_roi = gray[y : y + h, x + w - scrollbar_width : x + w]
        right_brightness = np.mean(right_roi)

        if right_brightness > 50:
            scroll_areas.append(
                {
                    "type": "right_scrollbar",
                    "position": {
                        "x": x + w - scrollbar_width,
                        "y": y,
                        "width": scrollbar_width,
                        "height": h,
                    },
                    "brightness": right_brightness,
                }
            )

        return scroll_areas

    def _detect_sidebar(self, image: np.ndarray, content_area: dict) -> dict[str, Any]:
        """Detect sidebar."""
        if not content_area:
            return None

        x, y, w, h = content_area["position"].values()
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Check if left or right third is consistently different
        third_width = int(w * 0.33)

        left_roi = gray[y : y + h, x : x + third_width]
        right_roi = gray[y : y + h, x + w - third_width : x + w]

        left_brightness = np.mean(left_roi)
        right_brightness = np.mean(right_roi)

        # If one side is much brighter/darker, it might be a sidebar
        diff = abs(left_brightness - right_brightness)

        if diff > 50:
            if left_brightness < right_brightness - 50:
                return {
                    "type": "left_sidebar",
                    "position": {"x": x, "y": y, "width": third_width, "height": h},
                }
            elif right_brightness < left_brightness - 50:
                return {
                    "type": "right_sidebar",
                    "position": {
                        "x": x + w - third_width,
                        "y": y,
                        "width": third_width,
                        "height": h,
                    },
                }

        return None

    def _detect_page_margins(
        self, gray: np.ndarray, image: np.ndarray
    ) -> dict[str, Any]:
        """Detect page margins."""
        height, width = gray.shape

        # Check left and right margins
        margin_width = int(width * 0.02)
        left_margin_roi = gray[0:height, 0:margin_width]
        right_margin_roi = gray[0:height, width - margin_width : width]

        left_brightness = np.mean(left_margin_roi)
        right_brightness = np.mean(right_margin_roi)

        # If margins are different from content, return them
        diff = abs(left_brightness - right_brightness)

        if diff > 20:
            return {
                "left_margin": margin_width,
                "right_margin": margin_width,
                "orientation": "vertical",
            }

        return None

    def _detect_header(
        self, gray: np.ndarray, image: np.ndarray, margins: dict
    ) -> dict[str, Any]:
        """Detect document header."""
        if not margins:
            return None

        height, width = gray.shape
        left_margin = margins.get("left_margin", 0)
        right_margin = margins.get("right_margin", 0)
        content_width = max(1, width - left_margin - right_margin)

        # Top 10% of page
        header_height = int(height * 0.10)

        if header_height < 50:
            return None

        header_roi = gray[
            0:header_height,
            left_margin : left_margin + content_width,
        ]
        brightness = float(np.mean(header_roi)) if header_roi.size > 0 else 0.0

        if brightness > 50:
            x = left_margin
            y = 0
            w = content_width
            h = header_height

            return {
                "type": "header",
                "position": {"x": x, "y": y, "width": w, "height": h},
                "height": h,
                "brightness": brightness,
            }

        return None

    def _detect_document_footer(
        self, gray: np.ndarray, image: np.ndarray, margins: dict
    ) -> dict[str, Any]:
        """Detect document footer."""
        if not margins:
            return None

        height, width = gray.shape
        left_margin = margins.get("left_margin", 0)
        right_margin = margins.get("right_margin", 0)
        content_width = max(1, width - left_margin - right_margin)

        # Bottom 10% of page
        footer_height = int(height * 0.10)

        if footer_height < 50:
            return None

        footer_roi = gray[
            height - footer_height : height,
            left_margin : left_margin + content_width,
        ]
        brightness = float(np.mean(footer_roi)) if footer_roi.size > 0 else 0.0

        if brightness > 50:
            x = left_margin
            y = height - footer_height
            w = content_width
            h = footer_height

            return {
                "type": "footer",
                "position": {"x": x, "y": y, "width": w, "height": h},
                "height": h,
                "brightness": brightness,
            }

        return None

    def _detect_body(
        self, image: np.ndarray, margins: dict, header: dict, footer: dict
    ) -> dict[str, Any]:
        """Detect document body."""
        if not margins:
            height, width = image.shape[:2]
            x, y, w, h = 0, 0, width, height
            return {
                "type": "body",
                "position": {"x": x, "y": y, "width": w, "height": h},
            }

        height, width = image.shape[:2]
        x = margins["left_margin"]
        y = header["position"]["y"] + header["position"]["height"] if header else 0
        w = width - margins["left_margin"] - margins["right_margin"]
        h = (
            height
            - y
            - (footer["position"]["y"] + footer["position"]["height"] if footer else 0)
        )

        return {"type": "body", "position": {"x": x, "y": y, "width": w, "height": h}}

    def _detect_columns(self, gray: np.ndarray, body: dict) -> list[dict[str, Any]]:
        """Detect columns in document body."""
        if not body:
            return []

        x, y, w, h = body["position"].values()

        # Check for column separators
        column_width = int(w / 3)
        vertical_line_count = 0

        for col_x in range(x + column_width, x + 2 * column_width, column_width):
            # Check if there's a vertical line
            column_roi = gray[y : y + h, col_x : col_x + 5]
            brightness = np.mean(column_roi)

            if brightness < 100:  # Dark line indicates column separator
                vertical_line_count += 1

        if vertical_line_count >= 2:
            return [
                {
                    "type": "column",
                    "position": {"x": x, "y": y, "width": column_width, "height": h},
                },
                {
                    "type": "column",
                    "position": {
                        "x": x + column_width,
                        "y": y,
                        "width": column_width,
                        "height": h,
                    },
                },
            ]

        return []

    def _detect_nodes(
        self, gray: np.ndarray, image: np.ndarray
    ) -> list[dict[str, Any]]:
        """Detect nodes in diagram."""
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        nodes = []
        min_area = 100
        max_area = 10000

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            nodes.append({"x": x, "y": y, "width": w, "height": h, "area": area})

        # Sort by x then y for grid-like diagrams
        nodes.sort(key=lambda n: (n["x"], n["y"]))

        return nodes

    def _detect_connections(
        self, image: np.ndarray, nodes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect connections between nodes."""
        if not nodes:
            return []

        connections = []
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Check for horizontal and vertical lines connecting nodes
        min_distance = 30

        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                # Calculate center points
                center1_x = node1["x"] + node1["width"] // 2
                center1_y = node1["y"] + node1["height"] // 2
                center2_x = node2["x"] + node2["width"] // 2
                center2_y = node2["y"] + node2["height"] // 2

                # Check if nodes are aligned horizontally
                horizontal_dist = abs(center1_x - center2_x)
                vertical_dist = abs(center1_y - center2_y)

                if horizontal_dist < min_distance and vertical_dist > min_distance * 2:
                    connections.append(
                        {"type": "horizontal", "from": node1, "to": node2}
                    )

                # Check if nodes are aligned vertically
                if vertical_dist < min_distance and horizontal_dist > min_distance * 2:
                    connections.append({"type": "vertical", "from": node1, "to": node2})

        return connections

    def _identify_diagram_sections(
        self, nodes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Identify sections in diagram (grouped nodes)."""
        if not nodes:
            return []

        # Simple clustering by x-coordinate
        sections = []
        min_gap = 100

        current_section = [nodes[0]]

        for node in nodes[1:]:
            if node["x"] - current_section[-1]["x"] < min_gap:
                current_section.append(node)
            else:
                if len(current_section) > 1:
                    sections.append({"type": "section", "nodes": current_section})
                current_section = [node]

        if len(current_section) > 1:
            sections.append({"type": "section", "nodes": current_section})

        return sections

    def _extract_layout_elements(
        self, layout_info: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract all layout elements."""
        elements = []

        def add_element(type_name, pos):
            elements.append({"type": type_name, "position": pos})

        if layout_info.get("title_bar"):
            add_element("title_bar", layout_info["title_bar"]["position"])

        if layout_info.get("menu_bar"):
            add_element("menu_bar", layout_info["menu_bar"]["position"])

        if layout_info.get("content_area"):
            add_element("content_area", layout_info["content_area"]["position"])

        if layout_info.get("footer"):
            add_element("footer", layout_info["footer"]["position"])

        if layout_info.get("sidebar"):
            add_element("sidebar", layout_info["sidebar"]["position"])

        if layout_info.get("margins"):
            margins = layout_info["margins"]
            if margins.get("left_margin"):
                add_element(
                    "left_margin",
                    {"x": 0, "y": 0, "width": margins["left_margin"], "height": 10000},
                )
            if margins.get("right_margin"):
                add_element(
                    "right_margin",
                    {
                        "x": 10000 - margins["right_margin"],
                        "y": 0,
                        "width": margins["right_margin"],
                        "height": 10000,
                    },
                )

        if layout_info.get("columns"):
            for col in layout_info["columns"]:
                add_element("column", col["position"])

        return elements

    def _identify_sections(
        self, layout_info: dict[str, Any], elements: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Identify main sections in layout."""
        sections = []

        def get_y_range(elements_list):
            if not elements_list:
                return (0, 10000)

            y_coords = [el["position"]["y"] for el in elements_list]
            return (min(y_coords), max(y_coords))

        if layout_info.get("content_area"):
            y_min, y_max = get_y_range(elements)
            sections.append(
                {
                    "type": "main_content",
                    "position": {
                        "y_start": y_min,
                        "y_end": y_max,
                        "height": y_max - y_min,
                    },
                }
            )

        return sections
