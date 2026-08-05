"""
Diagram Analyzer

Specialized analysis for diagrams and flowcharts.
"""

import logging
from typing import Any

import cv2
import numpy as np

from .models import ImageType

logger = logging.getLogger(__name__)


class DiagramAnalyzer:
    """
    Specialized diagram analysis.

    Provides detailed analysis for:
    - Flowcharts and process diagrams
    - UML diagrams
    - Network diagrams
    - Architecture diagrams
    - Circuit diagrams
    """

    def __init__(self):
        """Initialize the diagram analyzer."""
        self.node_min_size = 100
        self.connection_threshold = 30

    def analyze_diagram(
        self, image: np.ndarray, image_type: ImageType = ImageType.DIAGRAM
    ) -> dict:
        """
        Perform diagram analysis.

        Args:
            image: Image to analyze
            image_type: Type of image

        Returns:
            Diagram analysis results
        """
        logger.info(f"Analyzing diagram in {image_type.value} image")

        # Based on image type, use specialized diagram analysis
        if image_type == ImageType.DIAGRAM:
            return self._analyze_flowchart(image)
        elif image_type == ImageType.NETWORK:
            return self._analyze_network_diagram(image)
        elif image_type == ImageType.CIRCUIT:
            return self._analyze_circuit_diagram(image)
        else:
            return self._analyze_generic_diagram(image)

    def _analyze_flowchart(self, image: np.ndarray) -> dict:
        """
        Analyze flowchart.

        Args:
            image: Flowchart image

        Returns:
            Flowchart analysis results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect nodes
        nodes = self._detect_flowchart_nodes(gray, image)

        # Detect connections
        connections = self._detect_flowchart_connections(image, nodes)

        # Detect flowchart type
        flowchart_type = self._classify_flowchart(image, nodes, connections)

        result = {
            "type": flowchart_type,
            "nodes": nodes,
            "connections": connections,
            "node_count": len(nodes),
            "connection_count": len(connections),
            "complexity": self._calculate_complexity(nodes, connections),
        }

        logger.info(
            f"Flowchart analysis: {len(nodes)} nodes, "
            f"{len(connections)} connections, type: {flowchart_type}"
        )

        return result

    def _analyze_network_diagram(self, image: np.ndarray) -> dict:
        """
        Analyze network diagram.

        Args:
            image: Network diagram image

        Returns:
            Network diagram analysis results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect network nodes
        nodes = self._detect_network_nodes(gray, image)

        # Detect connections
        connections = self._detect_network_connections(image, nodes)

        # Extract network information
        network_info = self._extract_network_info(image, nodes, connections)

        result = {
            "type": "network_diagram",
            "nodes": nodes,
            "connections": connections,
            "node_count": len(nodes),
            "connection_count": len(connections),
            "devices": network_info.get("devices", []),
            "ip_addresses": network_info.get("ip_addresses", []),
            "vlans": network_info.get("vlans", []),
            "interface_names": network_info.get("interface_names", []),
            "complexity": self._calculate_complexity(nodes, connections),
        }

        logger.info(
            f"Network diagram analysis: {len(nodes)} devices, "
            f"{len(connections)} connections"
        )

        return result

    def _analyze_circuit_diagram(self, image: np.ndarray) -> dict:
        """
        Analyze circuit diagram.

        Args:
            image: Circuit diagram image

        Returns:
            Circuit diagram analysis results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect components
        components = self._detect_circuit_components(gray, image)

        # Detect connections
        connections = self._detect_circuit_connections(image, components)

        result = {
            "type": "circuit_diagram",
            "components": components,
            "connections": connections,
            "component_count": len(components),
            "connection_count": len(connections),
            "complexity": self._calculate_complexity(components, connections),
        }

        logger.info(f"Circuit diagram analysis: {len(components)} components")

        return result

    def _analyze_generic_diagram(self, image: np.ndarray) -> dict:
        """
        Analyze generic diagram.

        Args:
            image: Diagram image

        Returns:
            Generic diagram analysis results
        """
        gray = cv2.cvtColor(image, cv2_COLOR_RGB2GRAY)

        # Detect nodes
        nodes = self._detect_generic_nodes(gray, image)

        # Detect connections
        connections = self._detect_generic_connections(image, nodes)

        result = {
            "type": "generic_diagram",
            "nodes": nodes,
            "connections": connections,
            "node_count": len(nodes),
            "connection_count": len(connections),
            "complexity": self._calculate_complexity(nodes, connections),
        }

        logger.info(
            f"Generic diagram analysis: {len(nodes)} nodes, "
            f"{len(connections)} connections"
        )

        return result

    def _detect_flowchart_nodes(
        self, gray: np.ndarray, image: np.ndarray
    ) -> list[dict[str, Any]]:
        """Detect nodes in flowchart."""
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        nodes = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < self.node_min_size or area > 50000:
                continue

            # Check shape (circles, rectangles, diamonds)
            shape_type = self._classify_flowchart_node_shape(contour, image, x, y, w, h)

            nodes.append(
                {
                    "type": shape_type,
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "area": area,
                }
            )

        # Sort nodes for easier processing
        nodes.sort(key=lambda n: (n["position"]["x"], n["position"]["y"]))

        return nodes

    def _detect_network_nodes(
        self, gray: np.ndarray, image: np.ndarray
    ) -> list[dict[str, Any]]:
        """Detect nodes in network diagram."""
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        nodes = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < self.node_min_size or area > 50000:
                continue

            # Network nodes are typically circular
            shape_type = "device"
            if self._is_circular(contour, w, h):
                shape_type = "device_circle"
            elif self._is_rectangle(contour, w, h):
                shape_type = "device_box"

            nodes.append(
                {
                    "type": shape_type,
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "area": area,
                }
            )

        nodes.sort(key=lambda n: (n["position"]["x"], n["position"]["y"]))

        return nodes

    def _detect_circuit_components(
        self, gray: np.ndarray, image: np.ndarray
    ) -> list[dict[str, Any]]:
        """Detect components in circuit diagram."""
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        components = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < self.node_min_size or area > 50000:
                continue

            # Classify component
            shape_type = self._classify_circuit_component(contour, w, h)

            components.append(
                {
                    "type": shape_type,
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "area": area,
                }
            )

        components.sort(key=lambda c: (c["position"]["x"], c["position"]["y"]))

        return components

    def _detect_generic_nodes(
        self, gray: np.ndarray, image: np.ndarray
    ) -> list[dict[str, Any]]:
        """Detect nodes in generic diagram."""
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        nodes = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < self.node_min_size or area > 50000:
                continue

            nodes.append(
                {
                    "type": "node",
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "area": area,
                }
            )

        nodes.sort(key=lambda n: (n["position"]["x"], n["position"]["y"]))

        return nodes

    def _detect_flowchart_connections(
        self, image: np.ndarray, nodes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect connections between flowchart nodes."""
        if not nodes:
            return []

        connections = []
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect lines between nodes
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                x1, y1, w1, h1 = node1["position"].values()
                center1_x = x1 + w1 // 2
                center1_y = y1 + h1 // 2

                x2, y2, w2, h2 = node2["position"].values()
                center2_x = x2 + w2 // 2
                center2_y = y2 + h2 // 2

                # Check if nodes are connected
                if self._are_nodes_connected(
                    image, (center1_x, center1_y), (center2_x, center2_y)
                ):
                    connections.append(
                        {
                            "type": "connection",
                            "from": node1["position"],
                            "to": node2["position"],
                        }
                    )

        return connections

    def _detect_network_connections(
        self, image: np.ndarray, nodes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect connections in network diagram."""
        if not nodes:
            return []

        connections = []
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                x1, y1, w1, h1 = node1["position"].values()
                center1_x = x1 + w1 // 2
                center1_y = y1 + h1 // 2

                x2, y2, w2, h2 = node2["position"].values()
                center2_x = x2 + w2 // 2
                center2_y = y2 + h2 // 2

                # Check if nodes are connected (horizontal or vertical)
                horizontal_dist = abs(center1_x - center2_x)
                vertical_dist = abs(center1_y - center2_y)

                if (
                    horizontal_dist < self.connection_threshold
                    and vertical_dist > self.connection_threshold * 2
                ) or (
                    vertical_dist < self.connection_threshold
                    and horizontal_dist > self.connection_threshold * 2
                ):
                    connections.append(
                        {
                            "type": "connection",
                            "from": node1,
                            "to": node2,
                            "connection_type": (
                                "horizontal"
                                if vertical_dist > horizontal_dist
                                else "vertical"
                            ),
                        }
                    )

        return connections

    def _detect_circuit_connections(
        self, image: np.ndarray, components: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect connections in circuit diagram."""
        if not components:
            return []

        connections = []
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        for i, comp1 in enumerate(components):
            for comp2 in components[i + 1 :]:
                x1, y1, w1, h1 = comp1["position"].values()
                center1_x = x1 + w1 // 2
                center1_y = y1 + h1 // 2

                x2, y2, w2, h2 = comp2["position"].values()
                center2_x = x2 + w2 // 2
                center2_y = y2 + h2 // 2

                # Check if components are connected
                dist = abs(center1_x - center2_x) + abs(center1_y - center2_y)

                if dist < self.connection_threshold:
                    connections.append(
                        {
                            "type": "connection",
                            "from": comp1["position"],
                            "to": comp2["position"],
                        }
                    )

        return connections

    def _detect_generic_connections(
        self, image: np.ndarray, nodes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect connections in generic diagram."""
        if not nodes:
            return []

        connections = []

        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                x1, y1, w1, h1 = node1["position"].values()
                center1_x = x1 + w1 // 2
                center1_y = y1 + h1 // 2

                x2, y2, w2, h2 = node2["position"].values()
                center2_x = x2 + w2 // 2
                center2_y = y2 + h2 // 2

                # Check if nodes are connected
                dist = abs(center1_x - center2_x) + abs(center1_y - center2_y)

                if dist < self.connection_threshold:
                    connections.append(
                        {
                            "type": "connection",
                            "from": node1["position"],
                            "to": node2["position"],
                        }
                    )

        return connections

    def _classify_flowchart(
        self,
        image: np.ndarray,
        nodes: list[dict[str, Any]],
        connections: list[dict[str, Any]],
    ) -> str:
        """Classify flowchart type."""
        if not nodes:
            return "unknown"

        # Count different node types
        node_types = {}
        for node in nodes:
            ntype = node["type"]
            node_types[ntype] = node_types.get(ntype, 0) + 1

        # Check for diamond shapes (decision nodes)
        if node_types.get("diamond", 0) > 0:
            return "decision_flowchart"

        # Check for rectangle shapes (process nodes)
        if node_types.get("rectangle", 0) > 0:
            return "process_flowchart"

        # Check for circle shapes (start/end nodes)
        if node_types.get("circle", 0) > 0:
            return "start_end_flowchart"

        return "general_flowchart"

    def _classify_flowchart_node_shape(
        self, contour: np.ndarray, image: np.ndarray, x: int, y: int, w: int, h: int
    ) -> str:
        """Classify flowchart node shape."""
        # Check if circular
        if self._is_circular(contour, w, h):
            # Check if filled or outline
            roi = image[y : y + h, x : x + w]
            if len(roi.shape) == 3:
                gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
            else:
                gray = roi
            brightness = np.mean(gray)
            return "circle" if brightness > 100 else "outline_circle"

        # Check if diamond
        if self._is_diamond(contour, w, h):
            return "diamond"

        # Check if rectangle
        if self._is_rectangle(contour, w, h):
            return "rectangle"

        # Default to rectangle
        return "rectangle"

    def _classify_circuit_component(self, w: int, h: int) -> str:
        """Classify circuit component based on shape."""
        aspect_ratio = w / h if h > 0 else 0

        if 0.9 <= aspect_ratio <= 1.1:
            return "resistor"
        elif 0.5 <= aspect_ratio <= 0.7:
            return "capacitor"
        elif 1.3 <= aspect_ratio <= 1.7:
            return "inductor"
        elif 2 <= aspect_ratio <= 3:
            return "diode"
        else:
            return "component"

    def _extract_network_info(
        self,
        image: np.ndarray,
        nodes: list[dict[str, Any]],
        connections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract network information from diagram."""
        devices = []
        ip_addresses = []
        vlans = []
        interface_names = []

        for node in nodes:
            # Extract potential network device type from shape
            device_type = "device"
            if node["type"] == "device_circle":
                device_type = "router"
            elif node["type"] == "device_box":
                device_type = "switch"

            # Extract position (could be IP address or coordinates)
            x, y, w, h = node["position"].values()

            # Try to extract number as potential IP or VLAN
            if w < 50:
                try:
                    # Small rectangular shapes might be IPs
                    area = w * h
                    if area < 5000:
                        vlans.append(y)  # Use y as potential VLAN
                except:
                    pass

            devices.append({"type": device_type, "position": node["position"]})

        return {
            "devices": devices,
            "ip_addresses": ip_addresses,
            "vlans": vlans,
            "interface_names": interface_names,
        }

    def _calculate_complexity(
        self, elements: list[dict[str, Any]], connections: list[dict[str, Any]]
    ) -> str:
        """Calculate diagram complexity."""
        if not elements:
            return "simple"

        element_count = len(elements)
        connection_count = len(connections)
        density = connection_count / max(element_count, 1)

        if density < 0.5:
            return "simple"
        elif density < 1.0:
            return "medium"
        elif density < 2.0:
            return "complex"
        else:
            return "very_complex"

    def _is_circular(self, contour: np.ndarray, w: int, h: int) -> bool:
        """Check if contour is circular."""
        perimeter = cv2.arcLength(contour, True)
        area = cv2.contourArea(contour)

        if area == 0:
            return False

        circularity = (
            (4 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0
        )

        return circularity > 0.8

    def _is_rectangle(self, contour: np.ndarray, w: int, h: int) -> bool:
        """Check if contour is rectangular."""
        perimeter = cv2.arcLength(contour, True)
        area = cv2.contourArea(contour)

        if area == 0:
            return False

        rectangle_circularity = (
            (4 * area) / (perimeter * perimeter) if perimeter > 0 else 0
        )

        return rectangle_circularity > 0.85

    def _is_diamond(self, contour: np.ndarray, w: int, h: int) -> bool:
        """Check if contour is diamond-shaped."""
        # Diamond has aspect ratio close to 1
        aspect_ratio = w / h if h > 0 else 0

        return 0.7 <= aspect_ratio <= 1.3

    def _are_nodes_connected(
        self, image: np.ndarray, center1: tuple[int, int], center2: tuple[int, int]
    ) -> bool:
        """Check if two nodes are connected by a line."""
        x1, y1 = center1
        x2, y2 = center2

        # Create a line mask
        line_length = int(max(abs(x2 - x1), abs(y2 - y1)) * 1.1)
        mask = np.zeros((line_length, 1), dtype=np.uint8)

        # Draw line
        y_start = min(y1, y2)
        y_end = max(y1, y2)
        line_y = int((y2 - y1) * (line_length - 1) / (y2 - y1)) if y2 != y1 else 0

        # Check for darkness (connection line)
        roi = image[y_start:y_end, x1:x2]
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        # If line is dark, it's a connection
        brightness = np.mean(gray)
        return brightness < 100
