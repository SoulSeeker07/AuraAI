"""
Vision System Models

Core data models for the Vision System.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ImageType(Enum):
    """Types of images the Vision System can process."""

    SCREENSHOT = "screenshot"
    DOCUMENT = "document"
    DIAGRAM = "diagram"
    CODE = "code"
    UI = "ui"
    NETWORK = "network"
    WHITEBOARD = "whiteboard"
    PHOTO = "photo"
    UNKNOWN = "unknown"


class VisionProvider(Enum):
    """Supported vision providers."""

    LOCAL_OCR = "local_ocr"
    OPENAI = "openai"
    GEMINI = "gemini"
    FUTURE = "future"


@dataclass
class VisionContext:
    """
    Structured context from vision processing.

    This is the standard output format from vision processing that
    the Brain can use to understand what was seen.
    """

    # Core information
    image_type: ImageType
    image_path: str
    image_width: int
    image_height: int
    capture_time: datetime = field(default_factory=datetime.now)

    # OCR results
    detected_text: str = ""
    text_blocks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0

    # Object detection
    objects: list[dict[str, Any]] = field(default_factory=list)
    bounding_boxes: list[dict[str, Any]] = field(default_factory=list)

    # Layout analysis
    layout: dict[str, Any] = field(default_factory=dict)
    elements: list[dict[str, Any]] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)

    # Specialized analysis
    tables: list[list[list[str]]] = field(default_factory=list)
    code_snippets: list[dict[str, Any]] = field(default_factory=list)
    diagrams: list[dict[str, Any]] = field(default_factory=list)
    tables_found: list[str] = field(default_factory=list)
    code_found: list[str] = field(default_factory=list)
    diagrams_found: list[str] = field(default_factory=list)

    # Vision model results
    summary: str = ""
    analysis: str = ""
    description: str = ""

    # UI specific
    buttons: list[dict[str, Any]] = field(default_factory=list)
    menus: list[dict[str, Any]] = field(default_factory=list)
    dialogs: list[dict[str, Any]] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)

    # Network diagram specific
    network_devices: list[dict[str, Any]] = field(default_factory=list)
    network_connections: list[dict[str, Any]] = field(default_factory=list)
    ip_addresses: list[str] = field(default_factory=list)
    vlan_ids: list[int] = field(default_factory=list)
    interface_names: list[str] = field(default_factory=list)

    # Error detection
    errors_detected: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert vision context to dictionary."""
        return {
            "image_type": self.image_type.value,
            "image_path": self.image_path,
            "image_dimensions": {
                "width": self.image_width,
                "height": self.image_height,
            },
            "capture_time": self.capture_time.isoformat(),
            "detected_text": self.detected_text,
            "text_blocks": self.text_blocks,
            "confidence": self.confidence,
            "objects": self.objects,
            "bounding_boxes": self.bounding_boxes,
            "layout": self.layout,
            "elements": self.elements,
            "sections": self.sections,
            "tables": self.tables,
            "code_snippets": self.code_snippets,
            "diagrams": self.diagrams,
            "tables_found": self.tables_found,
            "code_found": self.code_found,
            "diagrams_found": self.diagrams_found,
            "summary": self.summary,
            "analysis": self.analysis,
            "description": self.description,
            "buttons": self.buttons,
            "menus": self.menus,
            "dialogs": self.dialogs,
            "forms": self.forms,
            "notifications": self.notifications,
            "network_devices": self.network_devices,
            "network_connections": self.network_connections,
            "ip_addresses": self.ip_addresses,
            "vlan_ids": self.vlan_ids,
            "interface_names": self.interface_names,
            "errors_detected": self.errors_detected,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }

    def from_dict(self, data: dict[str, Any]) -> "VisionContext":
        """Create VisionContext from dictionary."""
        self.image_type = ImageType(data.get("image_type", "unknown"))
        self.image_path = data.get("image_path", "")
        self.image_width = data.get("image_width", 0)
        self.image_height = data.get("image_height", 0)
        self.capture_time = datetime.fromisoformat(data["capture_time"])
        self.detected_text = data.get("detected_text", "")
        self.text_blocks = data.get("text_blocks", [])
        self.confidence = data.get("confidence", 0.0)
        self.objects = data.get("objects", [])
        self.bounding_boxes = data.get("bounding_boxes", [])
        self.layout = data.get("layout", {})
        self.elements = data.get("elements", [])
        self.sections = data.get("sections", [])
        self.tables = data.get("tables", [])
        self.code_snippets = data.get("code_snippets", [])
        self.diagrams = data.get("diagrams", [])
        self.tables_found = data.get("tables_found", [])
        self.code_found = data.get("code_found", [])
        self.diagrams_found = data.get("diagrams_found", [])
        self.summary = data.get("summary", "")
        self.analysis = data.get("analysis", "")
        self.description = data.get("description", "")
        self.buttons = data.get("buttons", [])
        self.menus = data.get("menus", [])
        self.dialogs = data.get("dialogs", [])
        self.forms = data.get("forms", [])
        self.notifications = data.get("notifications", [])
        self.network_devices = data.get("network_devices", [])
        self.network_connections = data.get("network_connections", [])
        self.ip_addresses = data.get("ip_addresses", [])
        self.vlan_ids = data.get("vlan_ids", [])
        self.interface_names = data.get("interface_names", [])
        self.errors_detected = data.get("errors_detected", [])
        self.warnings = data.get("warnings", [])
        self.metadata = data.get("metadata", {})
        return self

    def has_text(self) -> bool:
        """Check if any text was detected."""
        return len(self.detected_text) > 0

    def has_tables(self) -> bool:
        """Check if any tables were detected."""
        return len(self.tables) > 0 or len(self.tables_found) > 0

    def has_code(self) -> bool:
        """Check if any code was detected."""
        return len(self.code_snippets) > 0 or len(self.code_found) > 0

    def has_diagrams(self) -> bool:
        """Check if any diagrams were detected."""
        return len(self.diagrams) > 0 or len(self.diagrams_found) > 0

    def has_errors(self) -> bool:
        """Check if any errors were detected."""
        return len(self.errors_detected) > 0

    def has_ui_elements(self) -> bool:
        """Check if any UI elements were detected."""
        return (
            len(self.buttons) > 0
            or len(self.menus) > 0
            or len(self.dialogs) > 0
            or len(self.forms) > 0
            or len(self.notifications) > 0
        )


@dataclass
class ScreenshotSettings:
    """Settings for screenshot capture."""

    capture_type: str = (
        "full_screen"  # full_screen, active_monitor, active_window, selected_region
    )
    monitor_index: int = 0
    window_handle: int | None = None
    selected_region: tuple | None = None  # (x1, y1, x2, y2)
    format: str = "png"
    quality: int = 95
    include_cursor: bool = True
    include_timestamp: bool = True
    save_path: str | None = None


@dataclass
class OCRSettings:
    """Settings for OCR processing."""

    provider: VisionProvider = VisionProvider.LOCAL_OCR
    language: str = "en"
    table_detection: bool = True
    code_detection: bool = True
    diagram_detection: bool = True
    auto_rotate: bool = True
    deskew: bool = True
    confidence_threshold: float = 0.5


@dataclass
class UIAnalysisResult:
    """Result from UI analysis."""

    buttons: list[dict[str, Any]]
    menus: list[dict[str, Any]]
    dialogs: list[dict[str, Any]]
    forms: list[dict[str, Any]]
    notifications: list[dict[str, Any]]
    success: bool
    message: str
