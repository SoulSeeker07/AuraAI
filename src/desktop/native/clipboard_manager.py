"""
Clipboard Manager
Manages clipboard operations.
"""

import logging

from .native_manager import NativeManager
from .native_models import ClipboardData

logger = logging.getLogger(__name__)


class ClipboardManager:
    """Manages clipboard operations"""

    def __init__(self, native_manager: NativeManager):
        """
        Initialize the clipboard manager.

        Args:
            native_manager: The NativeManager instance
        """
        self.native_manager = native_manager
        logger.debug("ClipboardManager initialized")

    def read(self) -> ClipboardData:
        """
        Read clipboard data.

        Returns:
            ClipboardData object
        """
        logger.debug("Reading clipboard")
        return self.native_manager._clipboard_manager.read()

    def write(self, text: str, html: str | None = None) -> bool:
        """
        Write to clipboard.

        Args:
            text: Text to write
            html: HTML content (optional)

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Writing to clipboard: {text[:100]}...")
        return self.native_manager._clipboard_manager.write(text, html)

    def clear(self) -> bool:
        """
        Clear clipboard.

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Clearing clipboard")
        return self.native_manager._clipboard_manager.clear()

    def has_text(self) -> bool:
        """
        Check if clipboard has text.

        Returns:
            True if clipboard has text, False otherwise
        """
        logger.debug("Checking if clipboard has text")
        return self.native_manager._clipboard_manager.has_text()
