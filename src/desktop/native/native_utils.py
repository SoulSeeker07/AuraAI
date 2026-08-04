"""
Native Windows Layer Utilities
Common utilities for Windows operations.
"""
import win32api
import win32con
import win32gui
import win32process
import win32con as wconst
import ctypes
from typing import Optional, List, Tuple, Any
import psutil

from .native_models import WindowInfo, Rect
from .native_exceptions import WindowAccessDeniedError, ProcessAccessDeniedError


def get_window_by_title(title: str, exact_match: bool = False) -> Optional[int]:
    """
    Get window handle by title.

    Args:
        title: Window title to search for
        exact_match: If True, use exact match. If False, use partial match.

    Returns:
        Window handle (hwnd) or None
    """
    if exact_match:
        hwnd = win32gui.FindWindow(None, title)
        return hwnd if hwnd != 0 else None
    else:
        # Enumerate all windows and find matching title
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and title.lower() in title.lower():
                    windows.append(hwnd)
            return True

        windows = []
        win32gui.EnumWindows(callback, windows)
        return windows[0] if windows else None


def get_window_by_process_id(process_id: int) -> Optional[int]:
    """
    Get window handle by process ID.

    Args:
        process_id: Process ID to search for

    Returns:
        Window handle (hwnd) or None
    """
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == process_id:
                windows.append(hwnd)
        return True

    windows = []
    win32gui.EnumWindows(callback, windows)
    return windows[0] if windows else None


def get_process_by_id(process_id: int) -> Optional[psutil.Process]:
    """
    Get process object by process ID.

    Args:
        process_id: Process ID to search for

    Returns:
        Process object or None
    """
    try:
        return psutil.Process(process_id)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def get_active_window() -> Optional[WindowInfo]:
    """
    Get information about the active window.

    Returns:
        WindowInfo object or None
    """
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd or not win32gui.IsWindow(hwnd):
        return None
    return _get_window_info(hwnd)


def _get_window_info(hwnd: int) -> Optional[WindowInfo]:
    """
    Get window information for a specific handle.

    Args:
        hwnd: Window handle

    Returns:
        WindowInfo object or None
    """
    try:
        if not win32gui.IsWindow(hwnd):
            return None

        # Get window rectangle
        rect = win32gui.GetWindowRect(hwnd)
        rect_obj = Rect(left=rect[0], top=rect[1], right=rect[2], bottom=rect[3])

        # Get window styles
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style_ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

        # Check if visible
        is_visible = win32gui.IsWindowVisible(hwnd)

        # Check if minimized/maximized
        is_minimized = (style & win32con.WS_MINIMIZE) != 0
        is_maximized = (style & win32con.WS_MAXIMIZE) != 0

        # Get process information
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            process = psutil.Process(pid)
            executable = process.exe()
            title = win32gui.GetWindowText(hwnd) or executable
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            executable = "Unknown"
            title = win32gui.GetWindowText(hwnd) or "Unknown"

        # Get class name
        class_name = win32gui.GetClassName(hwnd)

        # Determine window style
        if is_minimized:
            window_style = "MINIMIZED"
        elif is_maximized:
            window_style = "MAXIMIZED"
        else:
            window_style = "NORMAL"

        return WindowInfo(
            hwnd=hwnd,
            title=title,
            process_id=pid,
            executable=executable,
            is_active=False,  # Will be set correctly
            is_visible=is_visible,
            is_minimized=is_minimized,
            is_maximized=is_maximized,
            rect=rect_obj,
            style=window_style,
            class_name=class_name,
            thread_id=win32process.GetWindowThreadProcessId(hwnd)[0],
        )
    except Exception as e:
        raise WindowAccessDeniedError(
            f"Failed to get window info: {e}",
            "get_window_info",
            win32_error=0,
            details={"hwnd": hwnd}
        )


def get_all_windows() -> List[WindowInfo]:
    """
    Get information about all visible windows.

    Returns:
        List of WindowInfo objects
    """
    windows = []

    def callback(hwnd, window_list):
        if win32gui.IsWindowVisible(hwnd):
            try:
                info = _get_window_info(hwnd)
                if info:
                    info.is_active = (hwnd == win32gui.GetForegroundWindow())
                    window_list.append(info)
            except Exception:
                pass
        return True

    win32gui.EnumWindows(callback, windows)
    return windows


def activate_window(hwnd: int) -> bool:
    """
    Activate a window.

    Args:
        hwnd: Window handle to activate

    Returns:
        True if successful, False otherwise
    """
    try:
        if not win32gui.IsWindow(hwnd):
            return False

        # Bring window to foreground
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        raise WindowAccessDeniedError(
            f"Failed to activate window: {e}",
            "activate_window",
            win32_error=0,
            details={"hwnd": hwnd}
        )


def close_window(hwnd: int, force: bool = False) -> bool:
    """
    Close a window.

    Args:
        hwnd: Window handle to close
        force: If True, force close even if dialog is open

    Returns:
        True if successful, False otherwise
    """
    try:
        if not win32gui.IsWindow(hwnd):
            return False

        # Try to close the window
        if not force:
            result = win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        else:
            # Force close using WM_SYSCOMMAND + SC_CLOSE
            result = win32gui.PostMessage(
                hwnd,
                win32con.WM_SYSCOMMAND,
                wconst.SC_CLOSE,
                0
            )

        return result != 0
    except Exception as e:
        raise WindowAccessDeniedError(
            f"Failed to close window: {e}",
            "close_window",
            win32_error=0,
            details={"hwnd": hwnd, "force": force}
        )


def minimize_window(hwnd: int) -> bool:
    """
    Minimize a window.

    Args:
        hwnd: Window handle to minimize

    Returns:
        True if successful, False otherwise
    """
    try:
        if not win32gui.IsWindow(hwnd):
            return False

        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return True
    except Exception as e:
        raise WindowAccessDeniedError(
            f"Failed to minimize window: {e}",
            "minimize_window",
            win32_error=0,
            details={"hwnd": hwnd}
        )


def maximize_window(hwnd: int) -> bool:
    """
    Maximize a window.

    Args:
        hwnd: Window handle to maximize

    Returns:
        True if successful, False otherwise
    """
    try:
        if not win32gui.IsWindow(hwnd):
            return False

        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return True
    except Exception as e:
        raise WindowAccessDeniedError(
            f"Failed to maximize window: {e}",
            "maximize_window",
            win32_error=0,
            details={"hwnd": hwnd}
        )


def restore_window(hwnd: int) -> bool:
    """
    Restore a minimized/maximized window.

    Args:
        hwnd: Window handle to restore

    Returns:
        True if successful, False otherwise
    """
    try:
        if not win32gui.IsWindow(hwnd):
            return False

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        return True
    except Exception as e:
        raise WindowAccessDeniedError(
            f"Failed to restore window: {e}",
            "restore_window",
            win32_error=0,
            details={"hwnd": hwnd}
        )


def set_window_position(hwnd: int, x: int, y: int) -> bool:
    """
    Set window position.

    Args:
        hwnd: Window handle
        x: X coordinate
        y: Y coordinate

    Returns:
        True if successful, False otherwise
    """
    try:
        if not win32gui.IsWindow(hwnd):
            return False

        win32gui.SetWindowPos(hwnd, None, x, y, 0, 0, win32con.SWP_NOSIZE | win32con.SWP_NOZORDER)
        return True
    except Exception as e:
        raise WindowAccessDeniedError(
            f"Failed to set window position: {e}",
            "set_window_position",
            win32_error=0,
            details={"hwnd": hwnd, "x": x, "y": y}
        )


def set_window_size(hwnd: int, width: int, height: int) -> bool:
    """
    Set window size.

    Args:
        hwnd: Window handle
        width: Window width
        height: Window height

    Returns:
        True if successful, False otherwise
    """
    try:
        if not win32gui.IsWindow(hwnd):
            return False

        rect = win32gui.GetWindowRect(hwnd)
        win32gui.SetWindowPos(hwnd, None, rect[0], rect[1], width, height, win32con.SWP_NOMOVE | win32con.SWP_NOZORDER)
        return True
    except Exception as e:
        raise WindowAccessDeniedError(
            f"Failed to set window size: {e}",
            "set_window_size",
            win32_error=0,
            details={"hwnd": hwnd, "width": width, "height": height}
        )


def get_process_name(pid: int) -> Optional[str]:
    """
    Get process name from process ID.

    Args:
        pid: Process ID

    Returns:
        Process name or None
    """
    try:
        process = psutil.Process(pid)
        return process.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def is_process_running(pid: int) -> bool:
    """
    Check if a process is running.

    Args:
        pid: Process ID

    Returns:
        True if running, False otherwise
    """
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False
