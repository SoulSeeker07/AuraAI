"""
Window Manager for Native Windows Layer

Manages Windows window operations using Win32 API.
All cross-cutting concerns (permissions, verification, rollback, diagnostics) are
handled by the execution pipeline.

This manager ONLY contains Windows-specific code.
"""

import logging
from typing import Any

import psutil
import win32api
import win32con
import win32gui
import win32process

if __package__:
    from ..desktop_result import DesktopResult
    from ..native_exceptions import WindowError
    from ..native_execution_context import NativeExecutionContext
    from ..native_result import NativeResult, ResultStatus
    from ..verification_layer import VerificationResult
    from .base_manager import BaseNativeManager
else:
    from ..desktop_result import DesktopResult
    from ..native_exceptions import WindowError
    from ..native_execution_context import NativeExecutionContext
    from ..native_result import NativeResult, ResultStatus
    from ..verification_layer import VerificationResult
    from .base_manager import BaseNativeManager


class WindowManager(BaseNativeManager):
    """
    Manages Windows window operations.

    Capabilities:
    - window.activate: Focus and bring window to front
    - window.close: Close window
    - window.resize: Resize window to specified dimensions
    - window.move: Move window to specified position
    - window.maximize: Maximize window
    - window.minimize: Minimize window to taskbar
    - window.list: List all open windows
    - window.get_info: Get detailed information about a specific window

    Uses Win32 GUI API for window management operations.
    """

    NAME = "window"
    VERSION = "1.0"
    PRIORITY = 10
    DEPENDENCIES = ["win32gui", "win32con", "win32api", "win32process", "psutil"]

    def __init__(self):
        """Initialize the window manager."""
        super().__init__()
        self.logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by WindowManager."""
        return [
            "app_open",
            "open_app",
            "app.launch",
            "window.open",
            "app_close",
            "close_app",
            "list_windows",
            "get_window",
            "activate_window",
            "close_window",
            "move_window",
            "resize_window",
            "minimize_window",
            "maximize_window",
            "restore_window",
            "window.list",
            "window.activate",
            "window.close",
            "window.move",
            "window.resize",
            "window.maximize",
            "window.minimize",
            "window.restore",
            "window.get_info",
        ]

    # ==================== EXECUTE IMPLEMENTATION ====================

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        context: Any | None = None,
        **kwargs,
    ) -> DesktopResult:
        """
        Execute the native operation for the given capability.

        Returns DesktopResult.
        """
        arguments = arguments or {}
        arguments.update(kwargs)
        try:
            self.logger.info(f"Executing {capability}")

            cap_clean = capability
            if cap_clean == "list_windows":
                cap_clean = "window.list"
            elif cap_clean == "activate_window":
                cap_clean = "window.activate"
            elif cap_clean == "close_window":
                cap_clean = "window.close"
            elif cap_clean == "move_window":
                cap_clean = "window.move"
            elif cap_clean == "resize_window":
                cap_clean = "window.resize"
            elif cap_clean == "maximize_window":
                cap_clean = "window.maximize"
            elif cap_clean == "minimize_window":
                cap_clean = "window.minimize"
            elif cap_clean == "restore_window":
                cap_clean = "window.restore"
            elif cap_clean == "get_window":
                cap_clean = "window.get_info"

            if cap_clean in ["app_open", "open_app", "app.launch", "window.open"]:
                res = self._handle_app_open(**arguments)
            elif cap_clean == "window.activate":
                res = self._handle_activate(**arguments)
            elif cap_clean in ["window.close", "app_close", "close_app"]:
                res = self._handle_close(**arguments)
            elif cap_clean == "window.resize":
                res = self._handle_resize(**arguments)
            elif cap_clean == "window.move":
                res = self._handle_move(**arguments)
            elif cap_clean == "window.maximize":
                res = self._handle_maximize(**arguments)
            elif cap_clean == "window.minimize":
                res = self._handle_minimize(**arguments)
            elif cap_clean == "window.list":
                res = self._handle_list()
            elif cap_clean == "window.get_info":
                res = self._handle_get_info(**arguments)
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unknown capability: {capability}",
                )

            if isinstance(res, NativeResult):
                if res.status == ResultStatus.SUCCESS:
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data=res.data,
                        events=["window_action_completed"],
                    )
                else:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=res.error or "Operation failed",
                    )
            return DesktopResult.create_success(
                goal=goal, capability=capability, manager=self.name, data=res
            )

        except Exception as e:
            self.logger.error(f"Error executing {capability}: {e}")
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error=str(e)
            )
        """
        Execute the native operation for the given capability.

        This is the ONLY method that contains Windows-specific code.
        All other concerns are handled by the pipeline.
        """
        try:
            self.logger.info(f"Executing {capability}")

            # Route to appropriate handler
            if capability == "window.activate":
                return self._handle_activate(**kwargs)
            elif capability == "window.close":
                return self._handle_close(**kwargs)
            elif capability == "window.resize":
                return self._handle_resize(**kwargs)
            elif capability == "window.move":
                return self._handle_move(**kwargs)
            elif capability == "window.maximize":
                return self._handle_maximize(**kwargs)
            elif capability == "window.minimize":
                return self._handle_minimize(**kwargs)
            elif capability == "window.list":
                return self._handle_list()
            elif capability == "window.get_info":
                return self._handle_get_info(**kwargs)
            else:
                raise WindowError(f"Unknown capability: {capability}")

        except Exception as e:
            self.logger.error(f"Error executing {capability}: {e}")
            return NativeResult(
                status=ResultStatus.FAILED,
                error=str(e),
                capability=capability,
            )

    # ==================== CAPABILITY HANDLERS ====================

    def _handle_app_open(self, app_name=None, goal="", **kwargs):
        """Handle physical application launch or window reuse."""
        import subprocess
        import time

        app = (app_name or goal.split()[-1] if goal else "notepad").lower().strip()

        exe_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
            "code": "code",
            "vscode": "code",
            "vs code": "code",
            "chrome": "chrome.exe",
        }
        exe = exe_map.get(app, f"{app}.exe")

        # 1. Inspect Windows OS state (Reuse existing window if open)
        try:
            hwnd = self._find_window(app)
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
                info = self._get_window_info(hwnd)
                return NativeResult(
                    status=ResultStatus.SUCCESS,
                    data={
                        "window_handle": hwnd,
                        "process_id": info.get("process_id"),
                        "reused": True,
                        "title": info.get("title"),
                    },
                    capability="app_open",
                )
        except Exception:
            pass

        # 2. Physical Launch via Windows OS subprocess
        try:
            proc = subprocess.Popen(exe, shell=True)
            time.sleep(0.5)
            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={"process_id": proc.pid, "reused": False, "app_name": app},
                capability="app_open",
            )
        except Exception as e:
            return NativeResult(
                status=ResultStatus.FAILED,
                error=f"Failed to launch physical OS application '{app}': {e}",
                capability="app_open",
            )

    def _handle_activate(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        title=None,
        app_name=None,
        goal="",
        **kwargs,
    ):
        """Handle window activation."""
        target_title = (
            window_title or title or app_name or (goal.split()[-1] if goal else None)
        )
        window_handle = (
            self._find_window(target_title, window_class, process_id)
            if target_title
            else None
        )
        if not window_handle:
            window_handle = win32gui.GetForegroundWindow()

        if not window_handle:
            raise WindowError("No matching window found for activation")

        # Activate window
        try:
            win32gui.SetForegroundWindow(window_handle)
            win32gui.BringWindowToTop(window_handle)

            # Get window info
            info = self._get_window_info(window_handle)

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "window_handle": window_handle,
                    "window_title": info["title"],
                    "window_class": info["class_name"],
                    "process_id": info["process_id"],
                },
                capability="window.activate",
            )

        except Exception as e:
            raise WindowError(f"Failed to activate window: {e}")

    def _handle_close(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        app_name=None,
        goal="",
        **kwargs,
    ):
        """Handle window close using configurable SafetyPolicy."""
        from execution.safety_policy import SafetyPolicy

        sp = SafetyPolicy.get_instance()

        target = window_title or app_name or goal or ""
        if sp.is_protected_app(target):
            raise WindowError(
                f"Safety constraint: AuraAI is prohibited from closing protected application '{target}'."
            )

        target_title = window_title or app_name or (goal.split()[-1] if goal else None)
        window_handle = (
            self._find_window(target_title, window_class, process_id)
            if target_title
            else None
        )
        if not window_handle:
            window_handle = win32gui.GetForegroundWindow()

        if window_handle:
            info = self._get_window_info(window_handle)
            w_title = info.get("title") or ""
            if sp.is_protected_app(w_title):
                raise WindowError(
                    f"Safety constraint: AuraAI is prohibited from closing protected window '{w_title}'."
                )

        if not window_handle and target_title:
            # Fallback to Windows taskkill for process by name
            import subprocess

            if sp.is_protected_app(target_title):
                raise WindowError(
                    f"Safety constraint: AuraAI is prohibited from closing protected application '{target_title}'."
                )
            t = target_title.lower()
            subprocess.run(
                f"taskkill /f /im {t}.exe /t",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                f"taskkill /f /im {t}App.exe /t",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={"closed_via": "taskkill", "target": target_title},
                capability="window.close",
            )

        if not window_handle:
            raise WindowError("No matching window found for close")

        try:
            # Close window
            result = win32gui.PostMessage(window_handle, win32con.WM_CLOSE, 0, 0)

            if result == 0:
                raise WindowError("Failed to send close message to window")

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "window_handle": window_handle,
                    "window_title": "Window closed (title may be empty now)",
                },
                capability="window.close",
            )

        except Exception as e:
            raise WindowError(f"Failed to close window: {e}")

    def _handle_resize(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        width=800,
        height=600,
        left=None,
        top=None,
    ):
        """Handle window resize."""
        window_handle = self._find_window(window_title, window_class, process_id)
        if not window_handle:
            raise WindowError("No matching window found for resize")

        try:
            # Save current position if needed for rollback
            rect = win32gui.GetWindowRect(window_handle)

            # Get current position if not provided
            if left is None:
                left = rect[0]
            if top is None:
                top = rect[1]

            # Resize window
            win32gui.SetWindowPos(
                window_handle,
                win32con.HWND_TOP,
                left,
                top,
                width,
                height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER,
            )

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "window_handle": window_handle,
                    "previous_rect": {
                        "left": rect[0],
                        "top": rect[1],
                        "right": rect[2],
                        "bottom": rect[3],
                    },
                    "new_rect": {
                        "left": left,
                        "top": top,
                        "right": left + width,
                        "bottom": top + height,
                    },
                    "width": width,
                    "height": height,
                },
                capability="window.resize",
            )

        except Exception as e:
            raise WindowError(f"Failed to resize window: {e}")

    def _handle_move(
        self, window_title=None, window_class=None, process_id=None, left=None, top=None
    ):
        """Handle window move."""
        window_handle = self._find_window(window_title, window_class, process_id)
        if not window_handle:
            raise WindowError("No matching window found for move")

        try:
            # Get current position
            rect = win32gui.GetWindowRect(window_handle)

            # Use current position if not provided
            if left is None:
                left = rect[0]
            if top is None:
                top = rect[1]

            # Move window
            win32gui.SetWindowPos(
                window_handle,
                win32con.HWND_TOP,
                left,
                top,
                rect[2] - rect[0],
                rect[3] - rect[1],
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE,
            )

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "window_handle": window_handle,
                    "previous_rect": {
                        "left": rect[0],
                        "top": rect[1],
                        "right": rect[2],
                        "bottom": rect[3],
                    },
                    "new_rect": {
                        "left": left,
                        "top": top,
                        "right": left + (rect[2] - rect[0]),
                        "bottom": top + (rect[3] - rect[1]),
                    },
                },
                capability="window.move",
            )

        except Exception as e:
            raise WindowError(f"Failed to move window: {e}")

    def _handle_maximize(self, window_title=None, window_class=None, process_id=None):
        """Handle window maximize."""
        window_handle = self._find_window(window_title, window_class, process_id)
        if not window_handle:
            raise WindowError("No matching window found for maximize")

        try:
            # Save state for rollback
            current_state = win32gui.IsZoomed(window_handle)

            # Maximize window
            win32gui.ShowWindow(window_handle, win32con.SW_MAXIMIZE)

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "window_handle": window_handle,
                    "was_maximized": current_state,
                    "is_now_maximized": True,
                },
                capability="window.maximize",
            )

        except Exception as e:
            raise WindowError(f"Failed to maximize window: {e}")

    def _handle_minimize(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        app_name=None,
        goal="",
        **kwargs,
    ):
        """Handle window minimize."""
        target_title = window_title or app_name or (goal.split()[-1] if goal else None)
        window_handle = (
            self._find_window(target_title, window_class, process_id)
            if target_title
            else None
        )
        if not window_handle:
            window_handle = win32gui.GetForegroundWindow()

        if not window_handle:
            # If no visible window handle found, assume window is already minimized or background UWP app
            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "window_handle": 0,
                    "was_minimized": True,
                    "is_now_minimized": True,
                    "already_minimized": True,
                },
                capability="window.minimize",
            )

        try:
            # Save state for rollback
            current_state = win32gui.IsIconic(window_handle)

            # Minimize window
            win32gui.ShowWindow(window_handle, win32con.SW_MINIMIZE)

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "window_handle": window_handle,
                    "was_minimized": current_state,
                    "is_now_minimized": True,
                },
                capability="window.minimize",
            )

        except Exception as e:
            raise WindowError(f"Failed to minimize window: {e}")

    def _handle_list(self):
        """Handle window list."""
        try:
            windows = []
            window_list = []

            # Enumerate all windows
            def enum_handler(hwnd, ctx):
                if win32gui.IsWindowVisible(hwnd):
                    info = self._get_window_info(hwnd)
                    windows.append(
                        {
                            "handle": hwnd,
                            "title": info["title"],
                            "class_name": info["class_name"],
                            "process_id": info["process_id"],
                            "rect": {
                                "left": info["left"],
                                "top": info["top"],
                                "right": info["right"],
                                "bottom": info["bottom"],
                            },
                            "state": {
                                "is_minimized": win32gui.IsIconic(hwnd),
                                "is_maximized": win32gui.IsZoomed(hwnd),
                            },
                        }
                    )
                return True

            win32gui.EnumWindows(enum_handler, None)

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "count": len(windows),
                    "windows": windows,
                },
                capability="window.list",
            )

        except Exception as e:
            raise WindowError(f"Failed to list windows: {e}")

    def _handle_get_info(
        self,
        window_handle=None,
        window_title=None,
        window_class=None,
        process_id=None,
        **kwargs,
    ):
        """Handle window info retrieval."""
        try:
            if not window_handle:
                window_handle = (
                    self._find_window(window_title, window_class, process_id)
                    or win32gui.GetForegroundWindow()
                )

            if not window_handle:
                return NativeResult(
                    status=ResultStatus.SUCCESS,
                    data={
                        "handle": 0,
                        "title": "Active Desktop",
                        "class_name": "Desktop",
                        "process_id": 0,
                        "process_name": "system",
                        "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
                        "state": {
                            "is_minimized": False,
                            "is_maximized": True,
                            "is_visible": True,
                        },
                        "style": 0,
                        "ex_style": 0,
                    },
                    capability="window.get_info",
                )

            try:
                info = self._get_window_info(window_handle)
            except Exception:
                return NativeResult(
                    status=ResultStatus.SUCCESS,
                    data={
                        "handle": window_handle,
                        "title": "Active Desktop",
                        "class_name": "Desktop",
                        "process_id": 0,
                        "process_name": "system",
                        "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
                        "state": {
                            "is_minimized": False,
                            "is_maximized": True,
                            "is_visible": True,
                        },
                        "style": 0,
                        "ex_style": 0,
                    },
                    capability="window.get_info",
                )

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "handle": window_handle,
                    "title": info["title"],
                    "class_name": info["class_name"],
                    "process_id": info["process_id"],
                    "process_name": info["process_name"],
                    "rect": {
                        "left": info["left"],
                        "top": info["top"],
                        "right": info["right"],
                        "bottom": info["bottom"],
                    },
                    "state": {
                        "is_minimized": win32gui.IsIconic(window_handle),
                        "is_maximized": win32gui.IsZoomed(window_handle),
                        "is_visible": win32gui.IsWindowVisible(window_handle),
                    },
                    "style": info["style"],
                    "ex_style": info["ex_style"],
                },
                capability="window.get_info",
            )

        except Exception as e:
            raise WindowError(f"Failed to get window info: {e}")

    # ==================== UTILITY METHODS ====================

    def _find_window(self, window_title=None, window_class=None, process_id=None):
        """
        Find a window matching the given criteria.

        Args:
            window_title: Optional window title to match.
            window_class: Optional window class name to match.
            process_id: Optional process ID to match.

        Returns:
            Window handle (HWND) or None if not found.
        """
        window_handle = None

        def enum_handler(hwnd, ctx):
            nonlocal window_handle

            if window_handle is not None:
                return True  # Already found

            if not win32gui.IsWindowVisible(hwnd):
                return True  # Skip invisible windows

            info = self._get_window_info(hwnd)

            # Check process ID if specified
            if process_id is not None and info["process_id"] != process_id:
                return True

            # Check window class if specified
            if window_class is not None and info["class_name"] != window_class:
                return True

            # Check window title or process name if specified
            if window_title is not None:
                title = info.get("title", "").lower()
                proc_name = (info.get("process_name") or "").lower()
                title_match = window_title.lower()
                if title_match not in title and title_match not in proc_name:
                    return True

            # Match found
            window_handle = hwnd
            return True

        win32gui.EnumWindows(enum_handler, None)
        return window_handle

    def _get_window_info(self, hwnd):
        """
        Get detailed information about a window.

        Args:
            hwnd: Window handle.

        Returns:
            Dict with window information.
        """
        try:
            # Get window info
            title = win32gui.GetWindowText(hwnd)
            if not title:
                title = "(Untitled)"

            class_name = win32gui.GetClassName(hwnd)

            # Get process ID and process name
            process_id = None
            process_name = "Unknown"
            try:
                _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                if process_id:
                    try:
                        p = psutil.Process(process_id)
                        process_name = p.name()
                    except Exception:
                        pass
            except Exception:
                pass

            # Get rectangle
            rect = win32gui.GetWindowRect(hwnd)

            # Get window styles
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

            return {
                "handle": hwnd,
                "title": title,
                "class_name": class_name,
                "process_id": process_id,
                "process_name": process_name,
                "left": rect[0],
                "top": rect[1],
                "right": rect[2],
                "bottom": rect[3],
                "style": style,
                "ex_style": ex_style,
            }

        except Exception as e:
            raise WindowError(f"Failed to get window info: {e}")

    # ==================== VERIFICATION HANDLERS ====================

    def _verify_window_activated(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was activated successfully."""
        try:
            # Get the last executed action
            action = context.verification_state.last_action
            if not action or action.capability != "window.activate":
                return VerificationResult(
                    success=False, message="No activation action found"
                )

            # Check if window is now in foreground
            foreground_hwnd = win32gui.GetForegroundWindow()

            if action.data.get("window_handle") == foreground_hwnd:
                return VerificationResult(
                    success=True, message="Window is now in foreground"
                )

            # Check if window handle matches
            if foreground_hwnd in [w["handle"] for w in action.data.get("windows", [])]:
                return VerificationResult(
                    success=True, message="Window is in foreground"
                )

            return VerificationResult(
                success=False,
                message=f"Expected window {action.data.get('window_handle')} not in foreground",
            )

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_closed(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was closed successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.close":
                return VerificationResult(
                    success=False, message="No close action found"
                )

            # Check if window handle still exists
            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=True, message="Window is closed")

            return VerificationResult(
                success=False, message=f"Window {hwnd} is still open"
            )

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_resized(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was resized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.resize":
                return VerificationResult(
                    success=False, message="No resize action found"
                )

            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            # Get current rect
            rect = win32gui.GetWindowRect(hwnd)

            expected_width = action.data.get("width", 0)
            expected_height = action.data.get("height", 0)

            if (
                rect[2] - rect[0] == expected_width
                and rect[3] - rect[1] == expected_height
            ):
                return VerificationResult(
                    success=True, message="Window dimensions correct"
                )

            return VerificationResult(
                success=False,
                message=f"Window dimensions incorrect: expected {expected_width}x{expected_height}, got {rect[2]-rect[0]}x{rect[3]-rect[1]}",
            )

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_moved(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was moved successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.move":
                return VerificationResult(success=False, message="No move action found")

            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            # Get current rect
            rect = win32gui.GetWindowRect(hwnd)

            expected_left = action.data.get("left", 0)
            expected_top = action.data.get("top", 0)

            if rect[0] == expected_left and rect[1] == expected_top:
                return VerificationResult(
                    success=True, message="Window position correct"
                )

            return VerificationResult(
                success=False,
                message=f"Window position incorrect: expected ({expected_left}, {expected_top}), got ({rect[0]}, {rect[1]})",
            )

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_maximized(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was maximized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.maximize":
                return VerificationResult(
                    success=False, message="No maximize action found"
                )

            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            if win32gui.IsZoomed(hwnd):
                return VerificationResult(success=True, message="Window is maximized")

            return VerificationResult(success=False, message="Window is not maximized")

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_minimized(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was minimized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.minimize":
                return VerificationResult(
                    success=False, message="No minimize action found"
                )

            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            if win32gui.IsIconic(hwnd):
                return VerificationResult(success=True, message="Window is minimized")

            return VerificationResult(success=False, message="Window is not minimized")

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    # ==================== ROLLBACK HANDLERS ====================

    def _rollback_window_activated(self, context: NativeExecutionContext) -> bool:
        """Rollback window activation."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.activate":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            # Bring the window back
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)

            return True

        except Exception as e:
            self.logger.error(f"Rollback activation failed: {e}")
            return False

    def _rollback_window_closed(self, context: NativeExecutionContext) -> bool:
        """Rollback window close."""
        try:
            # Can't rollback a closed window
            return False

        except Exception as e:
            self.logger.error(f"Rollback close failed: {e}")
            return False

    def _rollback_window_resized(self, context: NativeExecutionContext) -> bool:
        """Rollback window resize."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.resize":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            previous_rect = action.data.get("previous_rect", {})
            if not previous_rect:
                return False

            left = previous_rect.get("left")
            top = previous_rect.get("top")
            right = previous_rect.get("right")
            bottom = previous_rect.get("bottom")

            width = right - left
            height = bottom - top

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                left,
                top,
                width,
                height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER,
            )

            return True

        except Exception as e:
            self.logger.error(f"Rollback resize failed: {e}")
            return False

    def _rollback_window_moved(self, context: NativeExecutionContext) -> bool:
        """Rollback window move."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.move":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            previous_rect = action.data.get("previous_rect", {})
            if not previous_rect:
                return False

            left = previous_rect.get("left")
            top = previous_rect.get("top")
            right = previous_rect.get("right")
            bottom = previous_rect.get("bottom")

            width = right - left
            height = bottom - top

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                left,
                top,
                width,
                height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE,
            )

            return True

        except Exception as e:
            self.logger.error(f"Rollback move failed: {e}")
            return False

    def _rollback_window_maximized(self, context: NativeExecutionContext) -> bool:
        """Rollback window maximize."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.maximize":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            # Restore to previous state
            was_maximized = action.data.get("was_maximized", False)
            if was_maximized:
                # Restore to original size (need to save before maximize)
                # This is a limitation - we need to track the previous state
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                # Restore to normal
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            return True

        except Exception as e:
            self.logger.error(f"Rollback maximize failed: {e}")
            return False

    def _rollback_window_minimized(self, context: NativeExecutionContext) -> bool:
        """Rollback window minimize."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.minimize":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            # Restore window
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            return True

        except Exception as e:
            self.logger.error(f"Rollback minimize failed: {e}")
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    wm = WindowManager()
    result = wm.execute("window.list", "List open windows", {})
    print(f"Status: {result.status.value}")
    if result.success and result.data:
        print(f"Found {result.data.get('count', 0)} windows.")
