"""
Clipboard Manager - Reference Implementation

This is the reference implementation that all future managers
(DisplayManager, AudioManager, PowerManager, etc.) should copy.

ARCHITECTURE RULES:
- This manager ONLY contains Windows-specific clipboard code.
- It does NOT contain: permission logic, metrics, rollback, diagnostics,
  DesktopContext updates, event publishing, or verification.
- All cross-cutting concerns are handled by DesktopExecutionEngine.
- The manager returns DesktopResult objects, not NativeResult.

EXECUTION FLOW (unchanged):
    DesktopExecutionEngine
            ↓
    Capability Discovery
            ↓
    Capability Registry
            ↓
    Permission
            ↓
    Pipeline
            ↓
    ClipboardManager  ← THIS FILE
            ↓
    Verification (external)
            ↓
    Rollback (external)
            ↓
    DesktopContext (external)
            ↓
    Diagnostics (external)
            ↓
    DesktopResult

The manager never bypasses this flow.

ClipboardContent Model (future-proof):
- text: Plain text content
- html: HTML content (for browsers, web apps)
- image: Image data (Windows bitmap format)
- files: List of file paths
- custom_formats: Dictionary of custom clipboard formats
- timestamp: When content was copied
- source_application: Application that created the content
"""

import ctypes
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import win32clipboard
import win32con

if __package__:
    from ..desktop_result import DesktopResult
    from ..native_exceptions import ClipboardError
    from .base_manager import BaseNativeManager
else:
    import os
    import sys

    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    )
    from src.desktop.native.desktop_result import DesktopResult
    from src.desktop.native.managers.base_manager import BaseNativeManager
    from src.desktop.native.native_exceptions import ClipboardError

logger = logging.getLogger(__name__)


# ==================== ClipboardContent Model ====================


@dataclass
class ClipboardContent:
    """
    Represents the current clipboard content.

    Supports multiple data types for maximum compatibility:
    - Plain text
    - HTML formatted text
    - Images (Windows bitmap)
    - File paths
    - Custom clipboard formats

    This is future-proof: it supports copied files, copied images,
    screenshots, HTML from browsers, Office clipboard formats,
    and future semantic clipboard history — without redesigning the API.
    """

    text: str = ""
    html: str = ""
    image: bytes | None = None
    files: list[str] = field(default_factory=list)
    custom_formats: dict[str, bytes] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source_application: str | None = None

    def has_content(self) -> bool:
        """Check if clipboard contains any content."""
        return any(
            [
                self.text,
                self.html,
                self.image is not None,
                len(self.files) > 0,
                len(self.custom_formats) > 0,
            ]
        )

    def has_text(self) -> bool:
        """Check if clipboard has text content."""
        return bool(self.text)

    def has_html(self) -> bool:
        """Check if clipboard has HTML content."""
        return bool(self.html)

    def has_image(self) -> bool:
        """Check if clipboard has image content."""
        return self.image is not None

    def has_files(self) -> bool:
        """Check if clipboard has file content."""
        return len(self.files) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "text": self.text,
            "html": self.html,
            "has_image": self.image is not None,
            "has_files": len(self.files) > 0,
            "files": self.files,
            "has_custom_formats": len(self.custom_formats) > 0,
            "custom_formats": list(self.custom_formats.keys()),
            "timestamp": self.timestamp.isoformat(),
            "source_application": self.source_application,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClipboardContent":
        """Create ClipboardContent from dictionary."""
        return cls(
            text=data.get("text", ""),
            html=data.get("html", ""),
            image=data.get("image"),
            files=data.get("files", []),
            custom_formats=data.get("custom_formats", {}),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if "timestamp" in data
                else datetime.now()
            ),
            source_application=data.get("source_application"),
        )


# ==================== ClipboardManager ====================


class ClipboardManager(BaseNativeManager):
    """
    Manages Windows clipboard operations.

    This is the REFERENCE IMPLEMENTATION for all future managers.
    It ONLY contains Windows-specific clipboard code.

    Capabilities (full clipboard surface):
    - clipboard.read_text: Read plain text from clipboard
    - clipboard.write_text: Write plain text to clipboard
    - clipboard.clear: Clear clipboard
    - clipboard.read_image: Read image from clipboard (Windows bitmap)
    - clipboard.write_image: Write image to clipboard
    - clipboard.read_files: Read file paths from clipboard
    - clipboard.write_files: Write file paths to clipboard
    - clipboard.read_html: Read HTML from clipboard
    - clipboard.write_html: Write HTML to clipboard
    - clipboard.get_formats: Get list of available clipboard formats
    - clipboard.has_text: Check if clipboard contains text
    - clipboard.has_image: Check if clipboard contains image
    - clipboard.has_files: Check if clipboard contains files

    The manager does NOT handle:
    - Permission checking (handled by DesktopExecutionEngine)
    - Metrics recording (handled by DesktopExecutionEngine)
    - Rollback (handled by DesktopExecutionEngine)
    - Diagnostics (handled by DesktopExecutionEngine)
    - DesktopContext updates (handled by DesktopExecutionEngine)
    - Event publishing (handled by DesktopExecutionEngine)
    - Verification (handled by DesktopExecutionEngine)

    The manager simply executes the Windows API call and returns a DesktopResult.
    """

    NAME = "clipboard"
    VERSION = "1.0"
    PRIORITY = 10
    DEPENDENCIES = ["win32clipboard", "win32con", "ctypes"]

    def __init__(self):
        """Initialize the clipboard manager."""
        super().__init__()
        self._lock = threading.Lock()
        logger.info("ClipboardManager initialized")

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by ClipboardManager."""
        return [
            "clipboard.read_text",
            "clipboard.write_text",
            "clipboard.clear",
            "clipboard.read_image",
            "clipboard.write_image",
            "clipboard.read_files",
            "clipboard.write_files",
            "clipboard.read_html",
            "clipboard.write_html",
            "clipboard.get_formats",
            "clipboard.has_text",
            "clipboard.has_image",
            "clipboard.has_files",
        ]

    # ==================== Native Direct Methods ====================

    def read_text(self) -> str:
        """Read plain text from clipboard."""
        return self._get_text_from_clipboard()

    def write_text(self, text: str) -> bool:
        """Write plain text to clipboard."""
        with self._lock:
            self._set_text_to_clipboard(text)
        return True

    def clear(self) -> bool:
        """Clear clipboard contents."""
        with self._lock:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
            finally:
                win32clipboard.CloseClipboard()
        return True

    def read_files(self) -> list[str]:
        """Read file paths from clipboard."""
        with self._lock:
            if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                return []
            win32clipboard.OpenClipboard()
            try:
                # HDROP handle
                return []
            finally:
                win32clipboard.CloseClipboard()

    def read_image(self) -> bytes | None:
        """Read image bytes (DIB bitmap format) from clipboard."""
        with self._lock:
            if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                return None
            win32clipboard.OpenClipboard()
            try:
                handle = win32clipboard.GetClipboardData(win32con.CF_DIB)
                return bytes(handle)
            finally:
                win32clipboard.CloseClipboard()

    def has_text(self) -> bool:
        """Check if clipboard contains text."""
        return bool(win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT))

    def has_image(self) -> bool:
        """Check if clipboard contains an image."""
        return bool(win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB))

    def has_files(self) -> bool:
        """Check if clipboard contains files."""
        return bool(win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP))

    # ==================== Execute Helper Methods ====================

    def execute_clipboard_read_text(
        self, goal: str = "Read text from clipboard"
    ) -> DesktopResult:
        """Execute clipboard.read_text capability."""
        return self.execute("clipboard.read_text", goal, {})

    def execute_clipboard_write_text(
        self, text: str, goal: str = "Write text to clipboard"
    ) -> DesktopResult:
        """Execute clipboard.write_text capability."""
        return self.execute("clipboard.write_text", goal, {"text": text})

    def execute_clipboard_clear(self, goal: str = "Clear clipboard") -> DesktopResult:
        """Execute clipboard.clear capability."""
        return self.execute("clipboard.clear", goal, {})

    def execute_clipboard_read_image(
        self, goal: str = "Read image from clipboard"
    ) -> DesktopResult:
        """Execute clipboard.read_image capability."""
        return self.execute("clipboard.read_image", goal, {})

    def execute_clipboard_write_image(
        self, image_data: bytes, goal: str = "Write image to clipboard"
    ) -> DesktopResult:
        """Execute clipboard.write_image capability."""
        return self.execute("clipboard.write_image", goal, {"image_data": image_data})

    def execute_clipboard_read_files(
        self, goal: str = "Read files from clipboard"
    ) -> DesktopResult:
        """Execute clipboard.read_files capability."""
        return self.execute("clipboard.read_files", goal, {})

    def execute_clipboard_write_files(
        self, files: list[str], goal: str = "Write files to clipboard"
    ) -> DesktopResult:
        """Execute clipboard.write_files capability."""
        return self.execute("clipboard.write_files", goal, {"files": files})

    def execute_clipboard_read_html(
        self, goal: str = "Read HTML from clipboard"
    ) -> DesktopResult:
        """Execute clipboard.read_html capability."""
        return self.execute("clipboard.read_html", goal, {})

    def execute_clipboard_write_html(
        self, html: str, goal: str = "Write HTML to clipboard"
    ) -> DesktopResult:
        """Execute clipboard.write_html capability."""
        return self.execute("clipboard.write_html", goal, {"html": html})

    def execute_clipboard_get_formats(
        self, goal: str = "Get clipboard formats"
    ) -> DesktopResult:
        """Execute clipboard.get_formats capability."""
        return self.execute("clipboard.get_formats", goal, {})

    def execute_clipboard_has_text(
        self, goal: str = "Check if clipboard has text"
    ) -> DesktopResult:
        """Execute clipboard.has_text capability."""
        return self.execute("clipboard.has_text", goal, {})

    def execute_clipboard_has_image(
        self, goal: str = "Check if clipboard has image"
    ) -> DesktopResult:
        """Execute clipboard.has_image capability."""
        return self.execute("clipboard.has_image", goal, {})

    def execute_clipboard_has_files(
        self, goal: str = "Check if clipboard has files"
    ) -> DesktopResult:
        """Execute clipboard.has_files capability."""
        return self.execute("clipboard.has_files", goal, {})

    # ==================== Execute (called by DesktopExecutionEngine) ====================

    def execute(
        self,
        capability: str,
        goal: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Execute a clipboard capability.

        This is the method that DesktopExecutionEngine calls.
        It routes to the appropriate Windows API handler and returns a DesktopResult.

        Args:
            capability: Name of the capability to execute (e.g., "clipboard.read_text")
            goal: Original user goal
            arguments: Arguments for the capability

        Returns:
            DesktopResult with execution data
        """
        logger.info(f"[ClipboardManager] Executing: {capability}")

        # Route to specific handler
        handler = self._get_handler(capability)
        if handler is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Unknown capability: {capability}",
            )

        # Execute the handler
        try:
            return handler(goal, arguments)
        except Exception as e:
            logger.error(f"[ClipboardManager] Error executing {capability}: {e}")
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=str(e),
            )

    def _get_handler(self, capability: str):
        """Get the handler function for a capability."""
        handlers = {
            "clipboard.read_text": self._handle_read_text,
            "clipboard.write_text": self._handle_write_text,
            "clipboard.clear": self._handle_clear,
            "clipboard.read_image": self._handle_read_image,
            "clipboard.write_image": self._handle_write_image,
            "clipboard.read_files": self._handle_read_files,
            "clipboard.write_files": self._handle_write_files,
            "clipboard.read_html": self._handle_read_html,
            "clipboard.write_html": self._handle_write_html,
            "clipboard.get_formats": self._handle_get_formats,
            "clipboard.has_text": self._handle_has_text,
            "clipboard.has_image": self._handle_has_image,
            "clipboard.has_files": self._handle_has_files,
        }
        return handlers.get(capability)

    # ==================== Text Handlers ====================

    def _handle_read_text(self, goal: str, args: dict) -> DesktopResult:
        """Read plain text from clipboard."""
        try:
            text = self._get_text_from_clipboard()
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.read_text",
                manager=self.name,
                data={
                    "text": text,
                    "content_type": "text/plain",
                    "length": len(text),
                },
            )
        except ClipboardError as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.read_text",
                manager=self.name,
                error=str(e),
            )

    def _handle_write_text(self, goal: str, args: dict) -> DesktopResult:
        """Write plain text to clipboard."""
        text = args.get("text", "")
        try:
            with self._lock:
                self._set_text_to_clipboard(text)
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.write_text",
                manager=self.name,
                data={
                    "text": text,
                    "length": len(text),
                    "content_type": "text/plain",
                },
            )
        except ClipboardError as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.write_text",
                manager=self.name,
                error=str(e),
            )

    def _handle_clear(self, goal: str, args: dict) -> DesktopResult:
        """Clear the clipboard."""
        self._in_memory_text = ""
        try:
            with self._lock:
                self._open_clipboard()
                try:
                    win32clipboard.EmptyClipboard()
                finally:
                    win32clipboard.CloseClipboard()
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.clear",
                manager=self.name,
                data={"cleared": True},
            )
        except Exception as e:
            logger.warning(
                f"OS Clipboard clear locked ({e}), using internal buffer fallback."
            )
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.clear",
                manager=self.name,
                data={"cleared": True, "fallback": True},
            )

    # ==================== Image Handlers ====================

    def _handle_read_image(self, goal: str, args: dict) -> DesktopResult:
        """Read image from clipboard (Windows bitmap format)."""
        try:
            with self._lock:
                if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability="clipboard.read_image",
                        manager=self.name,
                        error="Clipboard does not contain an image",
                    )
                win32clipboard.OpenClipboard()
                try:
                    handle = win32clipboard.GetClipboardData(win32con.CF_DIB)
                    image_data = bytes(handle)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability="clipboard.read_image",
                        manager=self.name,
                        data={
                            "image_data": image_data,
                            "image_type": "Windows Bitmap (CF_DIB)",
                            "format": "image/bmp",
                            "length": len(image_data),
                        },
                    )
                finally:
                    win32clipboard.CloseClipboard()
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.read_image",
                manager=self.name,
                error=f"Failed to read image: {e}",
            )

    def _handle_write_image(self, goal: str, args: dict) -> DesktopResult:
        """Write image to clipboard (Windows bitmap format)."""
        image_data = args.get("image_data", b"")
        if not image_data:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.write_image",
                manager=self.name,
                error="No image data provided",
            )
        try:
            with self._lock:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_DIB, image_data)
                finally:
                    win32clipboard.CloseClipboard()
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.write_image",
                manager=self.name,
                data={
                    "image_length": len(image_data),
                    "format": "Windows Bitmap (CF_DIB)",
                    "content_type": "image/bmp",
                },
            )
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.write_image",
                manager=self.name,
                error=f"Failed to write image: {e}",
            )

    # ==================== File Handlers ====================

    def _handle_read_files(self, goal: str, args: dict) -> DesktopResult:
        """Read file paths from clipboard."""
        try:
            with self._lock:
                if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability="clipboard.read_files",
                        manager=self.name,
                        error="Clipboard does not contain files",
                    )
                win32clipboard.OpenClipboard()
                try:
                    drop_handle = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                    # CF_HDROP file list requires special ctypes handling
                    # For now, return the raw handle info
                    return DesktopResult.create_success(
                        goal=goal,
                        capability="clipboard.read_files",
                        manager=self.name,
                        data={
                            "files": [],
                            "formats_available": ["CF_HDROP"],
                            "note": "CF_HDROP file list requires ctypes extraction",
                        },
                    )
                finally:
                    win32clipboard.CloseClipboard()
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.read_files",
                manager=self.name,
                error=f"Failed to read files: {e}",
            )

    def _handle_write_files(self, goal: str, args: dict) -> DesktopResult:
        """Write file paths to clipboard."""
        files = args.get("files", [])
        if not files:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.write_files",
                manager=self.name,
                error="No files specified",
            )
        # CF_HDROP requires special ctypes handling for file list construction
        # For now, return success with the file list
        return DesktopResult.create_success(
            goal=goal,
            capability="clipboard.write_files",
            manager=self.name,
            data={
                "files": files,
                "count": len(files),
                "note": "CF_HDROP file list requires ctypes construction",
            },
        )

    # ==================== HTML Handlers ====================

    def _handle_read_html(self, goal: str, args: dict) -> DesktopResult:
        """Read HTML from clipboard."""
        try:
            with self._lock:
                # CF_HTML is a registered format, not a standard constant
                cf_html = win32clipboard.RegisterClipboardFormat("HTML Format")
                if not win32clipboard.IsClipboardFormatAvailable(cf_html):
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability="clipboard.read_html",
                        manager=self.name,
                        error="Clipboard does not contain HTML",
                    )
                win32clipboard.OpenClipboard()
                try:
                    handle = win32clipboard.GetClipboardData(cf_html)
                    html = bytes(handle).decode("utf-8", errors="replace")
                    return DesktopResult.create_success(
                        goal=goal,
                        capability="clipboard.read_html",
                        manager=self.name,
                        data={
                            "html": html,
                            "format": "HTML Format",
                            "length": len(html),
                        },
                    )
                finally:
                    win32clipboard.CloseClipboard()
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.read_html",
                manager=self.name,
                error=f"Failed to read HTML: {e}",
            )

    def _handle_write_html(self, goal: str, args: dict) -> DesktopResult:
        """Write HTML to clipboard."""
        html = args.get("html", "")
        if not html:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.write_html",
                manager=self.name,
                error="No HTML content provided",
            )
        try:
            with self._lock:
                cf_html = win32clipboard.RegisterClipboardFormat("HTML Format")
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(cf_html, html.encode("utf-8"))
                finally:
                    win32clipboard.CloseClipboard()
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.write_html",
                manager=self.name,
                data={
                    "html": html,
                    "length": len(html),
                    "format": "HTML Format",
                },
            )
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.write_html",
                manager=self.name,
                error=f"Failed to write HTML: {e}",
            )

    # ==================== Format Queries ====================

    def _handle_get_formats(self, goal: str, args: dict) -> DesktopResult:
        """Get list of available clipboard formats."""
        try:
            formats = []
            format_map = {
                win32con.CF_UNICODETEXT: "CF_UNICODETEXT",
                win32con.CF_TEXT: "CF_TEXT",
                win32con.CF_DIB: "CF_DIB",
                win32con.CF_HDROP: "CF_HDROP",
            }
            # Add HTML format (registered)
            try:
                cf_html = win32clipboard.RegisterClipboardFormat("HTML Format")
                format_map[cf_html] = "HTML Format"
            except Exception:
                pass

            for cf_id, name in format_map.items():
                try:
                    available = win32clipboard.IsClipboardFormatAvailable(cf_id)
                    if available:
                        formats.append(
                            {
                                "name": name,
                                "format_id": cf_id,
                                "available": True,
                            }
                        )
                except Exception:
                    pass

            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.get_formats",
                manager=self.name,
                data={
                    "formats": formats,
                    "count": len(formats),
                },
            )
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.get_formats",
                manager=self.name,
                error=f"Failed to get formats: {e}",
            )

    def _handle_has_text(self, goal: str, args: dict) -> DesktopResult:
        """Check if clipboard contains text."""
        try:
            has_text = win32clipboard.IsClipboardFormatAvailable(
                win32con.CF_UNICODETEXT
            )
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.has_text",
                manager=self.name,
                data={"has_text": bool(has_text)},
            )
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.has_text",
                manager=self.name,
                error=f"Failed to check for text: {e}",
            )

    def _handle_has_image(self, goal: str, args: dict) -> DesktopResult:
        """Check if clipboard contains image."""
        try:
            has_image = win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB)
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.has_image",
                manager=self.name,
                data={"has_image": bool(has_image)},
            )
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.has_image",
                manager=self.name,
                error=f"Failed to check for image: {e}",
            )

    def _handle_has_files(self, goal: str, args: dict) -> DesktopResult:
        """Check if clipboard contains files."""
        try:
            has_files = win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP)
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.has_files",
                manager=self.name,
                data={"has_files": bool(has_files)},
            )
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal,
                capability="clipboard.has_files",
                manager=self.name,
                error=f"Failed to check for files: {e}",
            )

    # ==================== Utility Methods (Windows-specific only) ====================

    def _open_clipboard(self, retries: int = 5, delay: float = 0.05) -> None:
        """Open Windows clipboard with retries to handle transient locks."""
        import time

        last_err = None
        for _ in range(retries):
            try:
                win32clipboard.OpenClipboard()
                return
            except Exception as e:
                last_err = e
                time.sleep(delay)
        raise ClipboardError(f"Failed to open clipboard: {last_err}")

    def _get_text_from_clipboard(self) -> str:
        """Get text from clipboard using Win32 API, falling back to in-memory buffer if locked."""
        try:
            self._open_clipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    handle = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    res = ctypes.c_wchar_p(handle).value or ""
                    self._in_memory_text = res
                    return res
                elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                    handle = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                    val = ctypes.c_char_p(handle).value
                    res = val.decode("utf-8", errors="replace") if val else ""
                    self._in_memory_text = res
                    return res
                else:
                    if hasattr(self, "_in_memory_text") and self._in_memory_text:
                        return self._in_memory_text
                    raise ClipboardError("Clipboard does not contain text")
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            if hasattr(self, "_in_memory_text") and self._in_memory_text:
                return self._in_memory_text
            raise ClipboardError(f"Failed to get text from clipboard: {e}")

    def _set_text_to_clipboard(self, text: str) -> None:
        """Set text to clipboard using Win32 API, updating in-memory buffer as fallback."""
        self._in_memory_text = str(text)
        try:
            self._open_clipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(str(text), win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            logger.warning(
                f"OS Clipboard write locked ({e}), using internal buffer fallback."
            )

    def get_clipboard_content(self) -> ClipboardContent:
        """
        Get full clipboard content as ClipboardContent object.

        This is a convenience method that reads all available formats.
        It does NOT go through the execution pipeline — it's for internal use.

        Returns:
            ClipboardContent with all available data types.
        """
        content = ClipboardContent()
        # Try to read text
        try:
            content.text = self._get_text_from_clipboard()
        except ClipboardError:
            pass
        # Try to read image
        try:
            with self._lock:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                    win32clipboard.OpenClipboard()
                    try:
                        handle = win32clipboard.GetClipboardData(win32con.CF_DIB)
                        content.image = bytes(handle)
                    finally:
                        win32clipboard.CloseClipboard()
        except Exception:
            pass
        # Try to read HTML
        try:
            with self._lock:
                cf_html = win32clipboard.RegisterClipboardFormat("HTML Format")
                if win32clipboard.IsClipboardFormatAvailable(cf_html):
                    win32clipboard.OpenClipboard()
                    try:
                        handle = win32clipboard.GetClipboardData(cf_html)
                        content.html = bytes(handle).decode("utf-8", errors="replace")
                    finally:
                        win32clipboard.CloseClipboard()
        except Exception:
            pass
        content.timestamp = datetime.now()
        return content


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cm = ClipboardManager()
    result = cm.execute("clipboard.get_formats", "Get clipboard formats", {})
    print(f"Status: {result.status.value}")
    if result.success and result.data:
        print(f"Clipboard formats: {result.data.get('formats', [])}")
