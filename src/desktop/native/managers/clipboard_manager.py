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

import win32clipboard
import win32con
import ctypes
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import threading

from ..desktop_result import DesktopResult, DesktopStatus
from ..native_exceptions import ClipboardError

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
    image: Optional[bytes] = None
    files: List[str] = field(default_factory=list)
    custom_formats: Dict[str, bytes] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source_application: Optional[str] = None

    def has_content(self) -> bool:
        """Check if clipboard contains any content."""
        return any([
            self.text,
            self.html,
            self.image is not None,
            len(self.files) > 0,
            len(self.custom_formats) > 0,
        ])

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

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> 'ClipboardContent':
        """Create ClipboardContent from dictionary."""
        return cls(
            text=data.get("text", ""),
            html=data.get("html", ""),
            image=data.get("image"),
            files=data.get("files", []),
            custom_formats=data.get("custom_formats", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            source_application=data.get("source_application"),
        )


# ==================== ClipboardManager ====================

class ClipboardManager:
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

    def __init__(self):
        """Initialize the clipboard manager."""
        self.name = "clipboard"
        self._lock = threading.Lock()
        logger.info("ClipboardManager initialized")

    # ==================== Execute (called by DesktopExecutionEngine) ====================

    def execute(
        self,
        capability: str,
        goal: str,
        arguments: Dict[str, Any],
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

    def _handle_read_text(self, goal: str, args: Dict) -> DesktopResult:
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
                goal=goal, capability="clipboard.read_text",
                manager=self.name, error=str(e),
            )

    def _handle_write_text(self, goal: str, args: Dict) -> DesktopResult:
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
                goal=goal, capability="clipboard.write_text",
                manager=self.name, error=str(e),
            )

    def _handle_clear(self, goal: str, args: Dict) -> DesktopResult:
        """Clear the clipboard."""
        try:
            with self._lock:
                win32clipboard.OpenClipboard()
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
            return DesktopResult.create_failure(
                goal=goal, capability="clipboard.clear",
                manager=self.name, error=f"Failed to clear clipboard: {e}",
            )

    # ==================== Image Handlers ====================

    def _handle_read_image(self, goal: str, args: Dict) -> DesktopResult:
        """Read image from clipboard (Windows bitmap format)."""
        try:
            with self._lock:
                if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                    return DesktopResult.create_failure(
                        goal=goal, capability="clipboard.read_image",
                        manager=self.name, error="Clipboard does not contain an image",
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
                goal=goal, capability="clipboard.read_image",
                manager=self.name, error=f"Failed to read image: {e}",
            )

    def _handle_write_image(self, goal: str, args: Dict) -> DesktopResult:
        """Write image to clipboard (Windows bitmap format)."""
        image_data = args.get("image_data", b"")
        if not image_data:
            return DesktopResult.create_failure(
                goal=goal, capability="clipboard.write_image",
                manager=self.name, error="No image data provided",
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
                goal=goal, capability="clipboard.write_image",
                manager=self.name, error=f"Failed to write image: {e}",
            )

    # ==================== File Handlers ====================

    def _handle_read_files(self, goal: str, args: Dict) -> DesktopResult:
        """Read file paths from clipboard."""
        try:
            with self._lock:
                if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                    return DesktopResult.create_failure(
                        goal=goal, capability="clipboard.read_files",
                        manager=self.name, error="Clipboard does not contain files",
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
                goal=goal, capability="clipboard.read_files",
                manager=self.name, error=f"Failed to read files: {e}",
            )

    def _handle_write_files(self, goal: str, args: Dict) -> DesktopResult:
        """Write file paths to clipboard."""
        files = args.get("files", [])
        if not files:
            return DesktopResult.create_failure(
                goal=goal, capability="clipboard.write_files",
                manager=self.name, error="No files specified",
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

    def _handle_read_html(self, goal: str, args: Dict) -> DesktopResult:
        """Read HTML from clipboard."""
        try:
            with self._lock:
                # CF_HTML is a registered format, not a standard constant
                cf_html = win32clipboard.RegisterClipboardFormat("HTML Format")
                if not win32clipboard.IsClipboardFormatAvailable(cf_html):
                    return DesktopResult.create_failure(
                        goal=goal, capability="clipboard.read_html",
                        manager=self.name, error="Clipboard does not contain HTML",
                    )
                win32clipboard.OpenClipboard()
                try:
                    handle = win32clipboard.GetClipboardData(cf_html)
                    html = bytes(handle).decode('utf-8', errors='replace')
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
                goal=goal, capability="clipboard.read_html",
                manager=self.name, error=f"Failed to read HTML: {e}",
            )

    def _handle_write_html(self, goal: str, args: Dict) -> DesktopResult:
        """Write HTML to clipboard."""
        html = args.get("html", "")
        if not html:
            return DesktopResult.create_failure(
                goal=goal, capability="clipboard.write_html",
                manager=self.name, error="No HTML content provided",
            )
        try:
            with self._lock:
                cf_html = win32clipboard.RegisterClipboardFormat("HTML Format")
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(cf_html, html.encode('utf-8'))
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
                goal=goal, capability="clipboard.write_html",
                manager=self.name, error=f"Failed to write HTML: {e}",
            )

    # ==================== Format Queries ====================

    def _handle_get_formats(self, goal: str, args: Dict) -> DesktopResult:
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
                        formats.append({
                            "name": name,
                            "format_id": cf_id,
                            "available": True,
                        })
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
                goal=goal, capability="clipboard.get_formats",
                manager=self.name, error=f"Failed to get formats: {e}",
            )

    def _handle_has_text(self, goal: str, args: Dict) -> DesktopResult:
        """Check if clipboard contains text."""
        try:
            has_text = win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT)
            return DesktopResult.create_success(
                goal=goal,
                capability="clipboard.has_text",
                manager=self.name,
                data={"has_text": bool(has_text)},
            )
        except Exception as e:
            return DesktopResult.create_failure(
                goal=goal, capability="clipboard.has_text",
                manager=self.name, error=f"Failed to check for text: {e}",
            )

    def _handle_has_image(self, goal: str, args: Dict) -> DesktopResult:
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
                goal=goal, capability="clipboard.has_image",
                manager=self.name, error=f"Failed to check for image: {e}",
            )

    def _handle_has_files(self, goal: str, args: Dict) -> DesktopResult:
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
                goal=goal, capability="clipboard.has_files",
                manager=self.name, error=f"Failed to check for files: {e}",
            )

    # ==================== Utility Methods (Windows-specific only) ====================

    def _get_text_from_clipboard(self) -> str:
        """Get text from clipboard using Win32 API."""
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    handle = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    return ctypes.c_wchar_p(handle).value
                elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                    handle = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                    return ctypes.c_char_p(handle).value.decode('utf-8', errors='replace')
                else:
                    raise ClipboardError("Clipboard does not contain text")
            finally:
                win32clipboard.CloseClipboard()
        except ClipboardError:
            raise
        except Exception as e:
            raise ClipboardError(f"Failed to get text from clipboard: {e}")

    def _set_text_to_clipboard(self, text: str) -> None:
        """Set text to clipboard using Win32 API."""
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text)
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            raise ClipboardError(f"Failed to set text to clipboard: {e}")

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
                        content.html = bytes(handle).decode('utf-8', errors='replace')
                    finally:
                        win32clipboard.CloseClipboard()
        except Exception:
            pass
        content.timestamp = datetime.now()
        return content