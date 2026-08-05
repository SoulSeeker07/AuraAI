"""
Window Manager
Manages window operations.
"""

import logging

from .native_exceptions import WindowNotFoundError
from .native_manager import NativeManager
from .native_models import WindowInfo

logger = logging.getLogger(__name__)


class WindowManager:
    """Manages window operations"""

    def __init__(self, native_manager: NativeManager):
        """
        Initialize the window manager.

        Args:
            native_manager: The NativeManager instance
        """
        self.native_manager = native_manager
        logger.debug("WindowManager initialized")

    def list_windows(self, **kwargs) -> list[WindowInfo]:
        """
        List all visible windows.

        Returns:
            List of WindowInfo objects
        """
        logger.debug("Listing all windows")
        return self.native_manager._window_manager.list_windows(**kwargs)

    def get_window(self, hwnd: int) -> WindowInfo | None:
        """
        Get information about a specific window.

        Args:
            hwnd: Window handle

        Returns:
            WindowInfo object or None
        """
        logger.debug(f"Getting window info for hwnd: {hwnd}")
        return self.native_manager._window_manager.get_window(hwnd)

    def activate_window(self, hwnd: int) -> bool:
        """
        Activate a specific window.

        Args:
            hwnd: Window handle to activate

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Activating window: {hwnd}")
        return self.native_manager._window_manager.activate_window(hwnd)

    def close_window(self, hwnd: int) -> bool:
        """
        Close a specific window.

        Args:
            hwnd: Window handle to close

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Closing window: {hwnd}")
        return self.native_manager._window_manager.close_window(hwnd)

    def minimize_window(self, hwnd: int) -> bool:
        """
        Minimize a specific window.

        Args:
            hwnd: Window handle to minimize

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Minimizing window: {hwnd}")
        return self.native_manager._window_manager.minimize_window(hwnd)

    def maximize_window(self, hwnd: int) -> bool:
        """
        Maximize a specific window.

        Args:
            hwnd: Window handle to maximize

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Maximizing window: {hwnd}")
        return self.native_manager._window_manager.maximize_window(hwnd)

    def restore_window(self, hwnd: int) -> bool:
        """
        Restore a minimized/maximized window.

        Args:
            hwnd: Window handle to restore

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Restoring window: {hwnd}")
        return self.native_manager._window_manager.restore_window(hwnd)

    def move_window(self, hwnd: int, x: int, y: int) -> bool:
        """
        Move a window to specific coordinates.

        Args:
            hwnd: Window handle
            x: X coordinate
            y: Y coordinate

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Moving window {hwnd} to ({x}, {y})")
        return self.native_manager._window_manager.set_window_position(hwnd, x, y)

    def resize_window(self, hwnd: int, width: int, height: int) -> bool:
        """
        Resize a window.

        Args:
            hwnd: Window handle
            width: Window width
            height: Window height

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Resizing window {hwnd} to {width}x{height}")
        return self.native_manager._window_manager.set_window_size(hwnd, width, height)

    def get_window_by_title(self, title: str, exact_match: bool = False) -> int | None:
        """
        Get window handle by title.

        Args:
            title: Window title to search for
            exact_match: If True, use exact match. If False, use partial match.

        Returns:
            Window handle (hwnd) or None
        """
        from .native_utils import get_window_by_title

        logger.debug(f"Finding window by title: {title}, exact_match={exact_match}")
        hwnd = get_window_by_title(title, exact_match)
        if not hwnd:
            raise WindowNotFoundError(
                f"Window not found with title: {title}",
                "get_window_by_title",
                details={"title": title, "exact_match": exact_match},
            )
        return hwnd

    def get_window_by_process_id(self, pid: int) -> int | None:
        """
        Get window handle by process ID.

        Args:
            pid: Process ID to search for

        Returns:
            Window handle (hwnd) or None
        """
        from .native_utils import get_window_by_process_id

        logger.debug(f"Finding window by process ID: {pid}")
        hwnd = get_window_by_process_id(pid)
        if not hwnd:
            raise WindowNotFoundError(
                f"No window found for process ID: {pid}",
                "get_window_by_process_id",
                details={"pid": pid},
            )
        return hwnd

    def get_active_window(self) -> WindowInfo | None:
        """
        Get information about the active window.

        Returns:
            WindowInfo object or None
        """
        from .native_utils import get_active_window

        logger.debug("Getting active window")
        return get_active_window()
