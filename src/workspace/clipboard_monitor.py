"""
Clipboard Monitor

Tracks clipboard content and changes.

Features:
- Monitor clipboard text content
- Detect code snippets
- Track clipboard changes
- Set clipboard manually
"""

import ctypes
import logging
import re
import threading
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

import psutil

from .models import ClipboardContext

logger = logging.getLogger(__name__)


class ClipboardMonitor:
    """
    Monitor clipboard content and changes.

    Provides:
    - Current clipboard text
    - Detection of code snippets
    - Clipboard change notifications
    - Manual clipboard setting
    """

    # Windows API constants
    CF_TEXT = 1
    CF_UNICODETEXT = 13
    CF_OEMTEXT = 4

    # Clipboard formats
    CODE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".cs",
        ".go",
        ".rs",
        ".cpp",
        ".c",
        ".h",
        ".html",
        ".css",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".bat",
        ".cmd",
    }

    # Python code patterns
    PYTHON_PATTERNS = [
        r"^import\s+[\w.]+\s*$",
        r"^from\s+[\w.]+\s+import\s+.*$",
        r"^def\s+\w+.*:$",
        r"^class\s+\w+.*:$",
        r"^if\s+__name__.*:$",
    ]

    # Code extension patterns
    CODE_PATTERNS = [
        r"^\s*(import|from)\s+.*$",
        r"^\s*(def|class|function|struct)\s+.*$",
        r"^\s*(if|while|for|switch|case)\s+.*$",
        r"^\s*(var|let|const|let\s+.*\s*=\s*{|function|return)",
    ]

    def __init__(self, poll_interval: int = 2, enable_detection: bool = True):
        """
        Initialize clipboard monitor.

        Args:
            poll_interval: Seconds between clipboard checks
            enable_detection: Enable code snippet detection
        """
        self.poll_interval = poll_interval
        self.enable_detection = enable_detection
        self._last_content: str | None = None
        self._last_hash: str | None = None
        self._clipboard_events = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._content_cache: ClipboardContext | None = None

        # Register clipboard formats
        self._code_format = self._register_format("AuraAI_Code")

        logger.info(
            f"Clipboard monitor initialized (poll_interval={poll_interval}s, code_detection={enable_detection})"
        )

    def _register_format(self, name: str) -> int:
        """
        Register a custom clipboard format.

        Args:
            name: Format name

        Returns:
            Format ID
        """
        try:
            return ctypes.windll.user32.RegisterClipboardFormatW(name)
        except Exception as e:
            logger.warning(f"Failed to register format {name}: {e}")
            return 13  # CF_UNICODETEXT

    async def get_clipboard(self) -> ClipboardContext | None:
        """
        Get current clipboard content.

        Returns:
            ClipboardContext or None if no text content
        """
        try:
            # Use cached value if available
            if self._content_cache and self._content_cache.has_content:
                # Update timestamp
                self._content_cache.timestamp = datetime.now()
                return self._content_cache

            # Get clipboard content
            text = self._get_clipboard_text()

            if not text or not text.strip():
                return None

            # Detect if it's code
            is_code = False
            code_type = None
            if self.enable_detection and text.strip():
                is_code = self._is_code_snippet(text)
                if is_code:
                    code_type = self._detect_code_type(text)

            # Create clipboard context
            clipboard = ClipboardContext(
                text=text, code=text if is_code else None, is_code=is_code, is_text=True
            )

            self._content_cache = clipboard
            self._last_content = text
            self._last_hash = self._hash_content(text)

            logger.debug(f"Clipboard updated: {len(text)} chars, code={is_code}")

            return clipboard

        except Exception as e:
            logger.error(f"Failed to get clipboard: {e}")
            return None

    def _get_clipboard_text(self) -> str | None:
        """
        Get text from clipboard.

        Returns:
            Text content or None
        """
        try:
            # Try to get Unicode text first
            if self._open_clipboard():
                try:
                    handle = ctypes.windll.user32.GetClipboardData(self.CF_UNICODETEXT)
                    if handle:
                        text = ctypes.create_unicode_buffer(1024 * 10)
                        if ctypes.windll.kernel32.GetWindowTextW(handle, text, 10240):
                            return text.value
                except Exception as e:
                    logger.debug(f"Failed to get Unicode text: {e}")
                finally:
                    self._close_clipboard()

            # Fall back to OEM text
            if self._open_clipboard():
                try:
                    handle = ctypes.windll.user32.GetClipboardData(self.CF_OEMTEXT)
                    if handle:
                        text = ctypes.create_unicode_buffer(1024 * 10)
                        if ctypes.windll.kernel32.GetWindowTextW(handle, text, 10240):
                            return text.value
                except Exception as e:
                    logger.debug(f"Failed to get OEM text: {e}")
                finally:
                    self._close_clipboard()

            return None

        except Exception as e:
            logger.error(f"Failed to get clipboard text: {e}")
            return None

    def _open_clipboard(self) -> bool:
        """
        Open clipboard for reading.

        Returns:
            True if successful
        """
        try:
            return ctypes.windll.user32.OpenClipboard(0) != 0
        except Exception as e:
            logger.error(f"Failed to open clipboard: {e}")
            return False

    def _close_clipboard(self):
        """Close clipboard"""
        try:
            ctypes.windll.user32.CloseClipboard()
        except Exception as e:
            logger.error(f"Failed to close clipboard: {e}")

    def _is_code_snippet(self, text: str) -> bool:
        """
        Detect if clipboard contains code.

        Args:
            text: Clipboard text

        Returns:
            True if it looks like code
        """
        if not self.enable_detection:
            return False

        text_lower = text.lower().strip()

        # Check file extension if available
        if self._last_content and self._is_file_open():
            ext = Path(self._last_content).suffix.lower()
            if ext in self.CODE_EXTENSIONS:
                return True

        # Check for code patterns
        lines = text.split("\n")
        code_lines = 0
        total_lines = len(lines)

        for line in lines:
            if self._is_code_line(line):
                code_lines += 1

        # At least 3 lines or 50% of content should be code
        return code_lines >= 3 or (code_lines / total_lines) >= 0.5

    def _is_code_line(self, line: str) -> bool:
        """
        Check if a line looks like code.

        Args:
            line: Line of text

        Returns:
            True if it looks like code
        """
        line_stripped = line.strip()

        # Check for Python patterns
        for pattern in self.PYTHON_PATTERNS:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                return True

        # Check for general code patterns
        for pattern in self.CODE_PATTERNS:
            if re.match(pattern, line_stripped):
                return True

        return False

    def _detect_code_type(self, text: str) -> str | None:
        """
        Detect programming language from code snippet.

        Args:
            text: Code snippet

        Returns:
            Language name or None
        """
        text_lower = text.lower()

        if re.search(r"import\s+[\w.]+$", text_lower):
            return "python"
        if re.search(r"(import|from)\s+[\w.]+.*\s+import", text_lower):
            return "python"

        if re.search(r"^import\s+[\w.]+\s*$", text_lower):
            return "javascript"

        if re.search(r"^(import|export)\s+", text_lower):
            return "typescript"

        if re.search(r"import\s+[\w.]+\s*$", text_lower):
            return "java"

        if re.search(r"^import\s+", text_lower):
            return "csharp"

        if re.search(r"^package\s+[\w.]+\s*$", text_lower):
            return "go"

        if re.search(r"^use\s+[\w.]+\s*$", text_lower):
            return "rust"

        return None

    def _is_file_open(self) -> bool:
        """
        Check if a file is currently open in an editor.

        Returns:
            True if a file is open
        """
        try:
            # Get current process
            current_process = psutil.Process()

            # Check if parent process is an editor
            parent = current_process.parent()
            while parent:
                if parent.name().lower() in [
                    "code",
                    "cursor",
                    "atom",
                    "sublime_text",
                    "pycharm",
                    "idea",
                    "visual_studio",
                ]:
                    return True
                parent = parent.parent()

            return False
        except Exception:
            return False

    def _hash_content(self, content: str) -> str:
        """
        Create hash of content to detect changes.

        Args:
            content: Content to hash

        Returns:
            Hash string
        """
        return str(hash(content))

    async def set_clipboard(self, content: str, is_code: bool = False):
        """
        Manually set clipboard content.

        Args:
            content: Content to set
            is_code: Whether content is code
        """
        try:
            self._set_clipboard_text(content, is_code)

            # Update cache
            self._content_cache = ClipboardContext(
                text=content,
                code=content if is_code else None,
                is_code=is_code,
                is_text=True,
            )

            self._last_content = content
            self._last_hash = self._hash_content(content)

            logger.debug(
                f"Clipboard set manually: {len(content)} chars, code={is_code}"
            )

        except Exception as e:
            logger.error(f"Failed to set clipboard: {e}")

    def _set_clipboard_text(self, text: str, is_code: bool = False):
        """
        Set clipboard text.

        Args:
            text: Text to set
            is_code: Whether it's code
        """
        try:
            # Set Unicode text
            if self._open_clipboard():
                try:
                    ctypes.windll.user32.EmptyClipboard()

                    # Convert to bytes
                    text_bytes = (
                        text.encode("utf-16le") if isinstance(text, str) else text
                    )

                    # Create buffer
                    buffer = ctypes.create_string_buffer(text_bytes)

                    # Set clipboard data
                    handle = ctypes.windll.kernel32.GlobalAlloc(0x0042, len(buffer))
                    pointer = ctypes.windll.kernel32.GlobalLock(handle)
                    ctypes.memmove(pointer, buffer, len(buffer))
                    ctypes.windll.kernel32.GlobalUnlock(handle)

                    ctypes.windll.user32.SetClipboardData(self.CF_UNICODETEXT, handle)

                except Exception as e:
                    logger.error(f"Failed to set Unicode text: {e}")
                finally:
                    self._close_clipboard()

        except Exception as e:
            logger.error(f"Failed to set clipboard: {e}")

    async def clear_clipboard(self):
        """Clear clipboard"""
        try:
            self._set_clipboard_text("")
            self._content_cache = None
            self._last_content = None
            self._last_hash = None
            logger.debug("Clipboard cleared")
        except Exception as e:
            logger.error(f"Failed to clear clipboard: {e}")

    def start_monitoring(self):
        """Start clipboard monitoring (polling mode)"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Clipboard monitoring started (polling mode)")

    def stop_monitoring(self):
        """Stop clipboard monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Clipboard monitoring stopped")

    def _monitor_loop(self):
        """Monitor loop for clipboard changes"""
        while self._running:
            try:
                content = self._get_clipboard_text()

                if content and content != self._last_content:
                    new_hash = self._hash_content(content)

                    if new_hash != self._last_hash:
                        self._last_content = content
                        self._last_hash = new_hash

                        # Update cache
                        is_code = (
                            self._is_code_snippet(content)
                            if self.enable_detection
                            else False
                        )
                        self._content_cache = ClipboardContext(
                            text=content,
                            code=content if is_code else None,
                            is_code=is_code,
                            is_text=True,
                        )

                        logger.info(
                            f"Clipboard changed: {len(content)} chars, code={is_code}"
                        )

            except Exception as e:
                logger.error(f"Error in clipboard monitor loop: {e}")

            time.sleep(self.poll_interval)

    def cleanup(self):
        """Clean up resources"""
        self.stop_monitoring()
        self._content_cache = None
        self._last_content = None
        self._last_hash = None
