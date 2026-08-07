"""
Screenshot Manager

Handles various types of screenshot captures for the Vision System.
"""

import ctypes
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import win32api
import win32con
import win32gui
from PIL import ImageGrab

from .models import ScreenshotSettings
from .preprocessing import ImagePreprocessor

logger = logging.getLogger(__name__)


class ScreenshotManager:
    """
    Manages various screenshot capture types.

    Supports:
    - Full screen capture
    - Active monitor capture
    - Active window capture
    - Selected region capture
    """

    def __init__(self, settings: ScreenshotSettings = None):
        """
        Initialize the screenshot manager.

        Args:
            settings: Screenshot capture settings
        """
        self.settings = settings or ScreenshotSettings()
        self.preprocessor = ImagePreprocessor()
        self.last_capture: str | None = None

    def capture_full_screen(self) -> str:
        """
        Capture the entire screen.

        Returns:
            Path to saved screenshot
        """
        logger.info("Capturing full screen")

        # Get screen dimensions
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)

        # Capture full screen
        screenshot = ImageGrab.grab(bbox=(0, 0, screen_width, screen_height))

        # Generate filename
        timestamp = int(time.time())
        filename = f"screenshot_full_{timestamp}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved full screen screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def capture_active_monitor(self, monitor_index: int = 0) -> str:
        """
        Capture the active monitor.

        Args:
            monitor_index: Index of monitor to capture (default: 0)

        Returns:
            Path to saved screenshot
        """
        logger.info(f"Capturing active monitor #{monitor_index}")

        # Get all monitors
        monitors = self._get_monitors()

        if monitor_index >= len(monitors):
            logger.warning(
                f"Monitor index {monitor_index} out of range, using first monitor"
            )
            monitor_index = 0

        monitor = monitors[monitor_index]
        bbox = monitor["rect"]

        # Capture monitor
        screenshot = ImageGrab.grab(bbox=bbox)

        # Generate filename
        timestamp = int(time.time())
        filename = f"screenshot_monitor_{monitor_index}_{timestamp}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved monitor {monitor_index} screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def capture_active_window(self) -> str:
        """
        Capture the currently active window.

        Returns:
            Path to saved screenshot
        """
        logger.info("Capturing active window")

        # Get active window handle
        hwnd = win32gui.GetForegroundWindow()

        if not hwnd:
            raise RuntimeError("No active window found")

        # Get window rectangle
        rect = win32gui.GetWindowRect(hwnd)
        x, y, right, bottom = rect

        width = right - x
        height = bottom - y

        if width <= 0 or height <= 0:
            raise RuntimeError("Invalid window dimensions")

        # Capture window
        screenshot = ImageGrab.grab(bbox=(x, y, right, bottom))

        # Get window title
        window_title = win32gui.GetWindowText(hwnd)

        # Generate filename
        timestamp = int(time.time())
        filename = f"screenshot_window_{timestamp}_{window_title[:20]}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved window screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def capture_selected_region(self, x1: int, y1: int, x2: int, y2: int) -> str:
        """
        Capture a selected region of the screen.

        Args:
            x1: Top-left x coordinate
            y1: Top-left y coordinate
            x2: Bottom-right x coordinate
            y2: Bottom-right y coordinate

        Returns:
            Path to saved screenshot
        """
        logger.info(f"Capturing selected region: ({x1}, {y1}) -> ({x2}, {y2})")

        # Validate coordinates
        if x1 >= x2 or y1 >= y2:
            raise ValueError("Invalid region coordinates")

        # Capture region
        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))

        # Generate filename
        timestamp = int(time.time())
        filename = f"screenshot_region_{x1}_{y1}_{x2}_{y2}_{timestamp}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved region screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def capture_window_by_title(self, window_title: str) -> str:
        """
        Capture a window by its title.

        Args:
            window_title: Window title to capture

        Returns:
            Path to saved screenshot
        """
        logger.info(f"Capturing window: {window_title}")

        # Find window by title
        hwnd = win32gui.FindWindow(None, window_title)

        if not hwnd:
            # Try to find window with this title (case-insensitive)
            def callback(hwnd, _):
                if win32gui.GetWindowText(hwnd) == window_title:
                    return 1
                return 0

            result = win32gui.EnumWindows(callback, 0)

            if not result:
                raise RuntimeError(f"Window not found: {window_title}")
            hwnd = result

        # Get window rectangle
        rect = win32gui.GetWindowRect(hwnd)
        x, y, right, bottom = rect

        width = right - x
        height = bottom - y

        if width <= 0 or height <= 0:
            raise RuntimeError("Invalid window dimensions")

        # Capture window
        screenshot = ImageGrab.grab(bbox=(x, y, right, bottom))

        # Generate filename
        timestamp = int(time.time())
        filename = f"screenshot_window_{timestamp}_{window_title[:20]}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved window screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def capture_menu(self, window_handle: int, menu_item: str) -> str:
        """
        Capture a menu item from a window.

        Args:
            window_handle: Handle of the window
            menu_item: Menu item to capture

        Returns:
            Path to saved screenshot
        """
        logger.info(f"Capturing menu item '{menu_item}' from window {window_handle}")

        # Get window rectangle
        rect = win32gui.GetWindowRect(window_handle)
        x, y, right, bottom = rect

        width = right - x
        height = bottom - y

        if width <= 0 or height <= 0:
            raise RuntimeError("Invalid window dimensions")

        # Capture window
        screenshot = ImageGrab.grab(bbox=(x, y, right, bottom))

        # Generate filename
        timestamp = int(time.time())
        filename = f"screenshot_menu_{timestamp}_{menu_item[:20]}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved menu screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def capture_dialog(self, window_handle: int) -> str:
        """
        Capture a dialog box.

        Args:
            window_handle: Handle of the dialog

        Returns:
            Path to saved screenshot
        """
        logger.info(f"Capturing dialog from window {window_handle}")

        # Get window rectangle
        rect = win32gui.GetWindowRect(window_handle)
        x, y, right, bottom = rect

        width = right - x
        height = bottom - y

        if width <= 0 or height <= 0:
            raise RuntimeError("Invalid dialog dimensions")

        # Capture dialog
        screenshot = ImageGrab.grab(bbox=(x, y, right, bottom))

        # Generate filename
        timestamp = int(time.time())
        filename = f"screenshot_dialog_{timestamp}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved dialog screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def _get_monitors(self) -> list[Dict]:
        """
        Get list of all connected monitors.

        Returns:
            List of monitor dictionaries with 'name', 'rect', and 'depth'
        """
        try:
            # Try using ctypes
            user32 = ctypes.windll.user32
            monitors = []

            def monitor_enum_proc(hmonitor, hdc_monitor, lpret, lparam):
                monitor_info = ctypes.create_string_buffer(40)
                if user32.GetMonitorInfoA(hmonitor, monitor_info):
                    monitors.append(
                        {
                            "name": "",
                            "rect": {
                                "left": ctypes.c_int32.from_address(
                                    ctypes.addressof(monitor_info) + 4
                                ).value,
                                "top": ctypes.c_int32.from_address(
                                    ctypes.addressof(monitor_info) + 8
                                ).value,
                                "right": ctypes.c_int32.from_address(
                                    ctypes.addressof(monitor_info) + 12
                                ).value,
                                "bottom": ctypes.c_int32.from_address(
                                    ctypes.addressof(monitor_info) + 16
                                ).value,
                            },
                            "depth": ctypes.c_int32.from_address(
                                ctypes.addressof(monitor_info) + 36
                            ).value,
                        }
                    )
                return 1

            user32.EnumDisplayMonitors(
                None,
                None,
                ctypes.WINFUNCTYPE(
                    ctypes.c_int,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                )(monitor_enum_proc),
                None,
            )

            return monitors
        except Exception as e:
            logger.warning(f"Failed to enumerate monitors using ctypes: {e}")
            # Fallback to screen info
            return self._get_monitors_fallback()

    def _get_monitors_fallback(self) -> list[Dict]:
        """
        Fallback method to get monitor information.

        Returns:
            List of monitor dictionaries
        """
        try:

            # Create a pseudo monitor list based on screen info
            monitors = []
            screen_width = win32api.GetSystemMetrics(0)
            screen_height = win32api.GetSystemMetrics(1)

            # Get all monitor handles
            monitors = []
            for monitor in range(win32api.GetSystemMetrics(80)):
                hmon = win32api.MonitorFromPoint(
                    (0, 0), win32con.MONITOR_DEFAULTTONEAREST
                )

                try:
                    # Get monitor info
                    monitor_info = ctypes.create_string_buffer(40)
                    user32 = ctypes.windll.user32
                    if user32.GetMonitorInfoA(hmon, monitor_info):
                        monitors.append(
                            {
                                "name": f"Monitor {monitor}",
                                "rect": {
                                    "left": ctypes.c_int32.from_address(
                                        ctypes.addressof(monitor_info) + 4
                                    ).value,
                                    "top": ctypes.c_int32.from_address(
                                        ctypes.addressof(monitor_info) + 8
                                    ).value,
                                    "right": ctypes.c_int32.from_address(
                                        ctypes.addressof(monitor_info) + 12
                                    ).value,
                                    "bottom": ctypes.c_int32.from_address(
                                        ctypes.addressof(monitor_info) + 16
                                    ).value,
                                },
                                "depth": ctypes.c_int32.from_address(
                                    ctypes.addressof(monitor_info) + 36
                                ).value,
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to get monitor info: {e}")

            return monitors
        except Exception as e:
            logger.error(f"Failed to get monitors: {e}")
            return []

    def _get_save_path(self, filename: str) -> str:
        """
        Get full path for saving screenshot.

        Args:
            filename: Screenshot filename

        Returns:
            Full save path
        """
        if self.settings.save_path:
            path = Path(self.settings.save_path)
            path.mkdir(parents=True, exist_ok=True)
            return str(path / filename)
        else:
            # Save to current directory
            return filename

    def capture_from_settings(self) -> str:
        """
        Capture screenshot based on settings.

        Returns:
            Path to saved screenshot
        """
        logger.info(f"Capturing using settings: {self.settings.capture_type}")

        capture_type = self.settings.capture_type

        if capture_type == "full_screen":
            return self.capture_full_screen()
        elif capture_type == "active_monitor":
            return self.capture_active_monitor(self.settings.monitor_index)
        elif capture_type == "active_window":
            return self.capture_active_window()
        elif capture_type == "selected_region":
            if not self.settings.selected_region:
                raise ValueError("Selected region not set")
            x1, y1, x2, y2 = self.settings.selected_region
            return self.capture_selected_region(x1, y1, x2, y2)
        else:
            raise ValueError(f"Unknown capture type: {capture_type}")

    def get_last_capture(self) -> str | None:
        """
        Get the path of the last captured screenshot.

        Returns:
            Path to last screenshot or None
        """
        return self.last_capture
