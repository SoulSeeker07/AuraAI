"""
Screenshot Manager

Handles various types of screenshot captures for the Vision System.
"""

import ctypes
import logging
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

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

    def _grab_safe(self, bbox=None):
        """Safely grab genuine screen pixels using mss or Pillow with DPI awareness."""
        try:
            import ctypes

            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
        except Exception:
            pass

        # Attempt 1: mss (high performance native Windows screen grab)
        try:
            from mss import mss
            from PIL import Image

            with mss() as sct:
                if bbox:
                    mon = {"left": bbox[0], "top": bbox[1], "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
                else:
                    mon = sct.monitors[0]
                sct_img = sct.grab(mon)
                return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        except Exception:
            pass

        # Attempt 2: Pillow ImageGrab with bbox
        if bbox:
            try:
                return ImageGrab.grab(bbox=bbox)
            except Exception:
                pass

        # Attempt 3: Pillow ImageGrab with all_screens
        try:
            return ImageGrab.grab(all_screens=True)
        except Exception:
            pass

        # Attempt 4: Plain Pillow ImageGrab
        try:
            return ImageGrab.grab()
        except Exception:
            pass

        # Do NOT return a fake blank image - return None so caller knows screen is unavailable
        return None

    def capture_full_screen(self) -> str | None:
        """
        Capture the entire screen.

        Returns:
            Absolute path to saved screenshot, or None if screen capture is unavailable
        """
        logger.info("Capturing full screen")

        screenshot = self._grab_safe()
        if screenshot is None:
            logger.warning("Screen capture unavailable on current display session")
            return None

        # Generate collision-proof filename
        timestamp = int(time.time())
        uid = uuid.uuid4().hex[:6]
        filename = f"screenshot_full_{timestamp}_{uid}.png"
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
        if not monitors:
            logger.warning("No monitors detected via Win32 enum, falling back to full screen capture")
            res = self.capture_full_screen()
            if res is None:
                raise RuntimeError("Screen capture unavailable for active monitor")
            return res

        if monitor_index >= len(monitors):
            logger.warning(
                f"Monitor index {monitor_index} out of range, using first monitor"
            )
            monitor_index = 0

        monitor = monitors[monitor_index]
        bbox = monitor["rect"]

        # Capture monitor
        screenshot = self._grab_safe(bbox=bbox)
        if screenshot is None:
            raise RuntimeError("Screen capture unavailable for active monitor")

        # Generate collision-proof filename
        timestamp = int(time.time())
        uid = uuid.uuid4().hex[:6]
        filename = f"screenshot_monitor_{monitor_index}_{timestamp}_{uid}.png"
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
            # Fallback to full screen if no foreground window handle
            return self.capture_full_screen()

        # Get window rectangle
        rect = win32gui.GetWindowRect(hwnd)
        x, y, right, bottom = rect

        width = right - x
        height = bottom - y

        if width <= 0 or height <= 0:
            return self.capture_full_screen()

        # Capture window
        screenshot = self._grab_safe(bbox=(x, y, right, bottom))
        if screenshot is None:
            raise RuntimeError("Screen capture unavailable for active window")

        # Get window title sanitized
        window_title = "".join(c for c in win32gui.GetWindowText(hwnd) if c.isalnum() or c in (" ", "_", "-")).strip()

        # Generate collision-proof filename
        timestamp = int(time.time())
        uid = uuid.uuid4().hex[:6]
        filename = f"screenshot_window_{timestamp}_{uid}_{window_title[:15]}.png"
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
        screenshot = self._grab_safe(bbox=(x1, y1, x2, y2))
        if screenshot is None:
            raise RuntimeError("Screen capture unavailable for selected region")

        # Generate collision-proof filename
        timestamp = int(time.time())
        uid = uuid.uuid4().hex[:6]
        filename = f"screenshot_region_{x1}_{y1}_{x2}_{y2}_{timestamp}_{uid}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved region screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def capture_region(self, x1: int, y1: int, x2: int, y2: int) -> str:
        """Alias for capture_selected_region."""
        return self.capture_selected_region(x1, y1, x2, y2)

    def capture_window(self, window_title: str) -> str:
        """Alias for capture_window_by_title."""
        return self.capture_window_by_title(window_title)

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
        screenshot = self._grab_safe(bbox=(x, y, right, bottom))
        if screenshot is None:
            raise RuntimeError("Screen capture unavailable for window")

        # Generate collision-proof filename
        timestamp = int(time.time())
        uid = uuid.uuid4().hex[:6]
        safe_title = "".join(c for c in window_title if c.isalnum() or c in (" ", "_", "-")).strip()
        filename = f"screenshot_window_{timestamp}_{uid}_{safe_title[:15]}.png"
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
        screenshot = self._grab_safe(bbox=(x, y, right, bottom))
        if screenshot is None:
            raise RuntimeError("Screen capture unavailable for menu")

        # Generate collision-proof filename
        timestamp = int(time.time())
        uid = uuid.uuid4().hex[:6]
        safe_menu = "".join(c for c in menu_item if c.isalnum() or c in (" ", "_", "-")).strip()
        filename = f"screenshot_menu_{timestamp}_{uid}_{safe_menu[:15]}.png"
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
        screenshot = self._grab_safe(bbox=(x, y, right, bottom))
        if screenshot is None:
            raise RuntimeError("Screen capture unavailable for dialog")

        # Generate collision-proof filename
        timestamp = int(time.time())
        uid = uuid.uuid4().hex[:6]
        filename = f"screenshot_dialog_{timestamp}_{uid}_{window_handle}.png"
        filepath = self._get_save_path(filename)

        # Save screenshot
        screenshot.save(filepath)
        logger.info(f"Saved dialog screenshot: {filepath}")

        self.last_capture = filepath
        return filepath

    def _get_monitors(self) -> list[dict]:
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

    def _get_monitors_fallback(self) -> list[dict]:
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
        Get absolute path for saving screenshot.
        Defaults to project Data/runtime/screenshots/ with automatic directory creation.
        """
        if self.settings and self.settings.save_path and self.settings.save_path.strip():
            path = Path(self.settings.save_path)
            if not path.is_absolute():
                path = (Path(__file__).resolve().parents[2] / path).resolve()
        else:
            path = (Path(__file__).resolve().parents[2] / "Data" / "runtime" / "screenshots").resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str((path / filename).resolve())

    def capture_internal(self, capture_type: str = "full_screen", **kwargs) -> str:
        """
        Dispatch capture based on capture_type and kwargs.
        Handles 'full_screen', 'active_monitor', 'active_window', 'window_by_title', and 'selected_region'.
        """
        ct = capture_type.lower().strip()
        if ct in ("full_screen", "fullscreen", "screen", "full"):
            res = self.capture_full_screen()
            if res is None:
                raise RuntimeError("Screen capture unavailable on current display session")
            return res
        elif ct in ("active_monitor", "monitor"):
            idx = kwargs.get("monitor_index", kwargs.get("monitor", self.settings.monitor_index if self.settings else 0))
            return self.capture_active_monitor(monitor_index=idx)
        elif ct in ("active_window", "window_active"):
            return self.capture_active_window()
        elif ct in ("window", "window_by_title", "title"):
            title = kwargs.get("window_title", kwargs.get("title", ""))
            if not title:
                return self.capture_active_window()
            return self.capture_window_by_title(title)
        elif ct in ("selected_region", "region"):
            region = kwargs.get("region")
            if region and len(region) >= 4:
                return self.capture_selected_region(region[0], region[1], region[2], region[3])
            elif all(k in kwargs for k in ("x1", "y1", "x2", "y2")):
                return self.capture_selected_region(kwargs["x1"], kwargs["y1"], kwargs["x2"], kwargs["y2"])
            elif self.settings and self.settings.selected_region:
                x1, y1, x2, y2 = self.settings.selected_region
                return self.capture_selected_region(x1, y1, x2, y2)
            raise ValueError("Region coordinates (x1, y1, x2, y2) required for region capture")
        else:
            # Fallback to settings or full screen
            try:
                return self.capture_from_settings()
            except Exception:
                res = self.capture_full_screen()
                if res is None:
                    raise RuntimeError(f"Unknown capture type '{capture_type}' and full screen fallback unavailable")
                return res

    @contextmanager
    def capture_scoped(self, capture_type: str = "full_screen", **kwargs) -> Generator[str, None, None]:
        """
        Context manager for ephemeral screenshot capture with fail-open lifecycle.
        - Captures screenshot into Data/runtime/screenshots/
        - Yields the absolute file path to the consumer
        - On clean exit: safely unlinks the temporary file
        - On exception: preserves the file on disk for post-mortem analysis and re-raises
        - Runs bounded retention pruning on exit
        """
        filepath = self.capture_internal(capture_type=capture_type, **kwargs)
        try:
            yield filepath
            self._safe_unlink(filepath)
        except Exception:
            logger.warning(f"Consumer failed; preserving failure screenshot at {filepath}")
            raise
        finally:
            self._prune_failure_captures(max_count=20, max_age_hours=24)

    def _safe_unlink(self, filepath: str | Path | None) -> bool:
        """Safely delete screenshot file with Windows file-lock and permission guardrails."""
        if not filepath:
            return False
        try:
            p = Path(filepath)
            if p.exists() and p.is_file():
                p.unlink()
                logger.debug(f"Ephemeral screenshot safely unlinked: {filepath}")
                return True
        except OSError as e:
            logger.warning(f"Could not unlink ephemeral screenshot {filepath}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error unlinking screenshot {filepath}: {e}")
        return False

    def _prune_failure_captures(self, max_count: int = 20, max_age_hours: int = 24) -> int:
        """
        Prune failure/preserved screenshots to prevent unbounded disk accumulation.
        Enforces max_count ceiling and max_age_hours retention limit.
        Returns number of deleted files.
        """
        try:
            if self.settings and self.settings.save_path and self.settings.save_path.strip():
                dir_path = Path(self.settings.save_path)
                if not dir_path.is_absolute():
                    dir_path = (Path(__file__).resolve().parents[2] / dir_path).resolve()
            else:
                dir_path = (Path(__file__).resolve().parents[2] / "Data" / "runtime" / "screenshots").resolve()

            if not dir_path.exists() or not dir_path.is_dir():
                return 0

            now = time.time()
            max_age_seconds = max_age_hours * 3600
            files = [f for f in dir_path.glob("*.png") if f.is_file()]
            deleted = 0

            # 1. Prune by age
            remaining = []
            for f in files:
                try:
                    mtime = f.stat().st_mtime
                    if now - mtime > max_age_seconds:
                        f.unlink(missing_ok=True)
                        deleted += 1
                    else:
                        remaining.append((f, mtime))
                except OSError:
                    pass

            # 2. Prune by count (keep most recent max_count)
            if len(remaining) > max_count:
                remaining.sort(key=lambda x: x[1])  # oldest first
                overflow = len(remaining) - max_count
                for f, _ in remaining[:overflow]:
                    try:
                        f.unlink(missing_ok=True)
                        deleted += 1
                    except OSError:
                        pass

            if deleted > 0:
                logger.info(f"Pruned {deleted} expired/overflow failure screenshot(s) from {dir_path}")
            return deleted
        except Exception as e:
            logger.warning(f"Error during failure screenshot pruning: {e}")
            return 0

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
