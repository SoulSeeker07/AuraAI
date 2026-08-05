"""
Active Window Monitor

Monitors the currently active window and provides information about it.
Uses Windows API to get window information.
"""

import ctypes
import logging
from ctypes import wintypes
from pathlib import Path

import psutil

from .models import ActiveWindow

logger = logging.getLogger(__name__)


class ActiveWindowMonitor:
    """
    Monitor for the currently active window.

    Tracks:
    - Window title
    - Application name
    - Process name
    - Window dimensions
    """

    # Windows API constants
    GW_HWNDPREV = -3
    GW_OWNER = 4

    # GetForegroundWindow function
    GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow
    GetForegroundWindow.argtypes = []
    GetForegroundWindow.restype = wintypes.HWND

    # GetWindowText function
    GetWindowTextW = ctypes.windll.user32.GetWindowTextW
    GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    GetWindowTextW.restype = ctypes.c_int

    # GetWindowThreadProcessId function
    GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
    GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(ctypes.c_uint)]
    GetWindowThreadProcessId.restype = ctypes.c_ulong

    # GetModuleFileNameEx function
    GetModuleFileNameEx = ctypes.windll.psapi.GetModuleFileNameExW
    GetModuleFileNameEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    GetModuleFileNameEx.restype = ctypes.c_int

    # GetWindowRect function
    GetWindowRect = ctypes.windll.user32.GetWindowRect
    GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(ctypes.c_int)]
    GetWindowRect.restype = ctypes.c_int

    # OpenProcess function
    OpenProcess = ctypes.windll.kernel32.OpenProcess
    OpenProcess.argtypes = [
        ctypes.c_ulong,  # dwDesiredAccess
        ctypes.c_int,  # bInheritHandle
        ctypes.c_uint,  # dwProcessId
    ]
    OpenProcess.restype = wintypes.HANDLE

    # CloseHandle function
    CloseHandle = ctypes.windll.kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = ctypes.c_int

    # PROCESS_QUERY_INFORMATION constant
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010

    # Default max length for window title
    MAX_WINDOW_TITLE_LENGTH = 2048

    def __init__(self):
        """Initialize active window monitor"""
        self._last_window: ActiveWindow | None = None

    async def get_active_window(self) -> ActiveWindow | None:
        """
        Get the currently active window.

        Returns:
            ActiveWindow object or None if no window found
        """
        try:
            hwnd = self.GetForegroundWindow()
            if not hwnd:
                return None

            # Get window title
            title_buf = ctypes.create_unicode_buffer(self.MAX_WINDOW_TITLE_LENGTH)
            title_length = self.GetWindowTextW(
                hwnd, title_buf, self.MAX_WINDOW_TITLE_LENGTH
            )

            if title_length == 0:
                # No title, might be a minimized or hidden window
                return None

            window_title = title_buf.value if title_length > 0 else ""

            # Get window rectangle (dimensions)
            rect = ctypes.c_int(4)
            self.GetWindowRect(hwnd, ctypes.byref(rect))
            x, y, width, height = (
                rect.value,
                rect.value + 1,
                rect.value + 2,
                rect.value + 3,
            )

            # Get process ID
            process_id = ctypes.c_uint(0)
            self.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            pid = process_id.value

            # Get process name
            process_name = self._get_process_name(pid)

            # Extract app name from process name
            app_name = self._extract_app_name(process_name)

            # Create active window object
            active_window = ActiveWindow(
                title=window_title,
                app_name=app_name,
                process_name=process_name,
                window_id=int(hwnd),
                rect={"x": x, "y": y, "width": width, "height": height},
            )

            self._last_window = active_window
            logger.debug(f"Active window: {app_name} - {window_title}")
            return active_window

        except Exception as e:
            logger.error(f"Failed to get active window: {e}")
            return self._last_window

    def _get_process_name(self, pid: int) -> str:
        """
        Get the process name by PID.

        Args:
            pid: Process ID

        Returns:
            Process name
        """
        try:
            process = psutil.Process(pid)
            exe = process.exe()
            if exe:
                return Path(exe).name
            return process.name()
        except Exception as e:
            logger.warning(f"Failed to get process name for PID {pid}: {e}")
            return "unknown"

    def _extract_app_name(self, process_name: str) -> str:
        """
        Extract application name from process name.

        Args:
            process_name: Full process name/path

        Returns:
            Cleaned application name
        """
        # Remove extension if present
        name = Path(process_name).stem

        # Common name mappings
        name_mappings = {
            "code": "VS Code",
            "cursor": "Cursor",
            "atom": "Atom",
            "sublime_text": "Sublime Text",
            "pycharm": "PyCharm",
            "idea": "IntelliJ IDEA",
            "visual_studio": "Visual Studio",
            "powershell": "Windows Terminal",
            "cmd": "Command Prompt",
            "powershell_ise": "Windows PowerShell ISE",
            "node": "Node.js",
            "python": "Python",
            "google_chrome": "Chrome",
            "msedge": "Edge",
            "firefox": "Firefox",
            "brave": "Brave",
            "safari": "Safari",
            "discord": "Discord",
            "slack": "Slack",
            "microsoft_teams": "Teams",
            "outlook": "Outlook",
            "packettracer": "Packet Tracer",
            "wireshark": "Wireshark",
        }

        # Check if we have a mapping
        for key, value in name_mappings.items():
            if key.lower() in name.lower():
                return value

        # Clean up the name
        name = name.replace("_", " ").title()
        return name

    async def get_last_window(self) -> ActiveWindow | None:
        """
        Get the last known active window.

        Returns:
            Last known ActiveWindow or None
        """
        return self._last_window

    async def is_window_in_workspace(self) -> bool:
        """
        Check if the active window is within workspace bounds.

        Returns:
            True if window is in workspace, False otherwise
        """
        window = await self.get_active_window()
        if window and window.rect:
            return window.is_in_workspace
        return True

    def cleanup(self):
        """Clean up resources"""
        # No resources to clean up for this simple monitor
        pass
