"""
Window Manager for Native Windows Layer

Manages Windows window operations using Win32 API.
All cross-cutting concerns (permissions, verification, rollback, diagnostics) are
handled by the execution pipeline.

This manager ONLY contains Windows-specific code.
"""

import win32gui
import win32con
import win32api
import psutil
import time
from typing import List, Dict, Any, Optional
import logging

from .base_manager import BaseNativeManager
from ..native_execution_context import NativeExecutionContext
from ..native_result import NativeResult, ResultStatus
from ..native_exceptions import WindowError, NativeError
from ..verification_layer import VerificationLayer, VerificationResult
from ..rollback_framework import RollbackFunctions, RollbackContext, RollbackAction


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

    def __init__(self):
        """Initialize the window manager."""
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def register_capabilities(self) -> None:
        """
        Register all window management capabilities with verification and rollback handlers.
        """
        capabilities = [
            'window.activate',
            'window.close',
            'window.resize',
            'window.move',
            'window.maximize',
            'window.minimize',
            'window.list',
            'window.get_info',
        ]

        # Verification handlers
        verification_handlers = {
            'window.activate': self._verify_window_activated,
            'window.close': self._verify_window_closed,
            'window.resize': self._verify_window_resized,
            'window.move': self._verify_window_moved,
            'window.maximize': self._verify_window_maximized,
            'window.minimize': self._verify_window_minimized,
        }

        # Rollback handlers
        rollback_handlers = {
            'window.activate': self._rollback_window_activated,
            'window.close': self._rollback_window_closed,
            'window.resize': self._rollback_window_resized,
            'window.move': self._rollback_window_moved,
            'window.maximize': self._rollback_window_maximized,
            'window.minimize': self._rollback_window_minimized,
        }

        super().register_capabilities(
            capabilities=capabilities,
            verification_handlers=verification_handlers,
            rollback_handlers=rollback_handlers,
        )

    # ==================== EXPOSED CAPABILITIES ====================

    def execute_window_activate(
        self,
        window_title: Optional[str] = None,
        window_class: Optional[str] = None,
        process_id: Optional[int] = None,
    ) -> NativeResult:
        """
        Activate (focus) a window.

        Args:
            window_title: Optional window title to match.
            window_class: Optional window class name to match.
            process_id: Optional process ID to match.

        Returns:
            NativeResult with success status and window info.

        Raises:
            WindowError: If no matching window found or activation fails.
        """
        context = ExecutionContextFactory.create()
        capability = 'window.activate'
        return self.execute(capability, context, window_title=window_title,
                           window_class=window_class, process_id=process_id)

    def execute_window_close(
        self,
        window_title: Optional[str] = None,
        window_class: Optional[str] = None,
        process_id: Optional[int] = None,
    ) -> NativeResult:
        """
        Close a window.

        Args:
            window_title: Optional window title to match.
            window_class: Optional window class name to match.
            process_id: Optional process ID to match.

        Returns:
            NativeResult with success status.

        Raises:
            WindowError: If no matching window found or close fails.
        """
        context = ExecutionContextFactory.create()
        capability = 'window.close'
        return self.execute(capability, context, window_title=window_title,
                           window_class=window_class, process_id=process_id)

    def execute_window_resize(
        self,
        window_title: Optional[str] = None,
        window_class: Optional[str] = None,
        process_id: Optional[int] = None,
        width: int = 800,
        height: int = 600,
        left: Optional[int] = None,
        top: Optional[int] = None,
    ) -> NativeResult:
        """
        Resize a window to specified dimensions.

        Args:
            window_title: Optional window title to match.
            window_class: Optional window class name to match.
            process_id: Optional process ID to match.
            width: New width in pixels.
            height: New height in pixels.
            left: Optional x position (None = keep current).
            top: Optional y position (None = keep current).

        Returns:
            NativeResult with success status and new dimensions.

        Raises:
            WindowError: If no matching window found or resize fails.
        """
        context = ExecutionContextFactory.create()
        capability = 'window.resize'
        return self.execute(capability, context, window_title=window_title,
                           window_class=window_class, process_id=process_id,
                           width=width, height=height, left=left, top=top)

    def execute_window_move(
        self,
        window_title: Optional[str] = None,
        window_class: Optional[str] = None,
        process_id: Optional[int] = None,
        left: int = 0,
        top: int = 0,
    ) -> NativeResult:
        """
        Move a window to specified position.

        Args:
            window_title: Optional window title to match.
            window_class: Optional window class name to match.
            process_id: Optional process ID to match.
            left: New x position.
            top: New y position.

        Returns:
            NativeResult with success status and new position.

        Raises:
            WindowError: If no matching window found or move fails.
        """
        context = ExecutionContextFactory.create()
        capability = 'window.move'
        return self.execute(capability, context, window_title=window_title,
                           window_class=window_class, process_id=process_id,
                           left=left, top=top)

    def execute_window_maximize(
        self,
        window_title: Optional[str] = None,
        window_class: Optional[str] = None,
        process_id: Optional[int] = None,
    ) -> NativeResult:
        """
        Maximize a window.

        Args:
            window_title: Optional window title to match.
            window_class: Optional window class name to match.
            process_id: Optional process ID to match.

        Returns:
            NativeResult with success status.

        Raises:
            WindowError: If no matching window found or maximize fails.
        """
        context = ExecutionContextFactory.create()
        capability = 'window.maximize'
        return self.execute(capability, context, window_title=window_title,
                           window_class=window_class, process_id=process_id)

    def execute_window_minimize(
        self,
        window_title: Optional[str] = None,
        window_class: Optional[str] = None,
        process_id: Optional[int] = None,
    ) -> NativeResult:
        """
        Minimize a window to taskbar.

        Args:
            window_title: Optional window title to match.
            window_class: Optional window class name to match.
            process_id: Optional process ID to match.

        Returns:
            NativeResult with success status.

        Raises:
            WindowError: If no matching window found or minimize fails.
        """
        context = ExecutionContextFactory.create()
        capability = 'window.minimize'
        return self.execute(capability, context, window_title=window_title,
                           window_class=window_class, process_id=process_id)

    def execute_window_list(self) -> NativeResult:
        """
        List all open windows with basic information.

        Returns:
            NativeResult with list of window information dicts.

        Raises:
            WindowError: If listing windows fails.
        """
        context = ExecutionContextFactory.create()
        capability = 'window.list'
        return self.execute(capability, context)

    def execute_window_get_info(
        self,
        window_handle: int,
    ) -> NativeResult:
        """
        Get detailed information about a specific window.

        Args:
            window_handle: Window handle (HWND).

        Returns:
            NativeResult with detailed window info.

        Raises:
            WindowError: If window handle is invalid or info retrieval fails.
        """
        context = ExecutionContextFactory.create()
        capability = 'window.get_info'
        return self.execute(capability, context, window_handle=window_handle)

    # ==================== EXECUTE IMPLEMENTATION ====================

    def execute(
        self,
        capability: str,
        context: NativeExecutionContext,
        **kwargs,
    ) -> NativeResult:
        """
        Execute the native operation for the given capability.

        This is the ONLY method that contains Windows-specific code.
        All other concerns are handled by the pipeline.
        """
        try:
            self.logger.info(f"Executing {capability}")

            # Route to appropriate handler
            if capability == 'window.activate':
                return self._handle_activate(**kwargs)
            elif capability == 'window.close':
                return self._handle_close(**kwargs)
            elif capability == 'window.resize':
                return self._handle_resize(**kwargs)
            elif capability == 'window.move':
                return self._handle_move(**kwargs)
            elif capability == 'window.maximize':
                return self._handle_maximize(**kwargs)
            elif capability == 'window.minimize':
                return self._handle_minimize(**kwargs)
            elif capability == 'window.list':
                return self._handle_list()
            elif capability == 'window.get_info':
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

    def _handle_activate(self, window_title=None, window_class=None, process_id=None):
        """Handle window activation."""
        # Find window
        window_handle = self._find_window(window_title, window_class, process_id)
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
                capability='window.activate',
            )

        except Exception as e:
            raise WindowError(f"Failed to activate window: {e}")

    def _handle_close(self, window_title=None, window_class=None, process_id=None):
        """Handle window close."""
        window_handle = self._find_window(window_title, window_class, process_id)
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
                capability='window.close',
            )

        except Exception as e:
            raise WindowError(f"Failed to close window: {e}")

    def _handle_resize(
        self, window_title=None, window_class=None, process_id=None,
        width=800, height=600, left=None, top=None
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
                left, top, width, height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER
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
                capability='window.resize',
            )

        except Exception as e:
            raise WindowError(f"Failed to resize window: {e}")

    def _handle_move(self, window_title=None, window_class=None, process_id=None,
                     left=None, top=None):
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
                left, top,
                rect[2] - rect[0], rect[3] - rect[1],
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE
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
                capability='window.move',
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
                capability='window.maximize',
            )

        except Exception as e:
            raise WindowError(f"Failed to maximize window: {e}")

    def _handle_minimize(self, window_title=None, window_class=None, process_id=None):
        """Handle window minimize."""
        window_handle = self._find_window(window_title, window_class, process_id)
        if not window_handle:
            raise WindowError("No matching window found for minimize")

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
                capability='window.minimize',
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
                    windows.append({
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
                    })
                return True

            win32gui.EnumWindows(enum_handler, None)

            return NativeResult(
                status=ResultStatus.SUCCESS,
                data={
                    "count": len(windows),
                    "windows": windows,
                },
                capability='window.list',
            )

        except Exception as e:
            raise WindowError(f"Failed to list windows: {e}")

    def _handle_get_info(self, window_handle):
        """Handle window info retrieval."""
        try:
            info = self._get_window_info(window_handle)

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
                capability='window.get_info',
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

            # Check window title if specified
            if window_title is not None:
                title = info["title"].lower()
                title_match = window_title.lower()
                if not title_match in title:
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

            # Get process ID
            process_id = None
            try:
                handle = win32gui.DuplicateHandle(
                    win32api.GetCurrentProcess(),
                    hwnd,
                    win32api.GetCurrentProcess(),
                    0,
                    0,
                    win32con.DUPLICATE_SAME_ACCESS
                )
                process_id = win32process.GetWindowThreadProcessId(hwnd)[1]
            except:
                pass

            # Get process name
            process_name = "Unknown"
            if process_id:
                try:
                    for proc in psutil.process_iter(['pid', 'name']):
                        if proc.info['pid'] == process_id:
                            process_name = proc.info['name']
                            break
                except:
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

    def _verify_window_activated(self, context: NativeExecutionContext) -> VerificationResult:
        """Verify window was activated successfully."""
        try:
            # Get the last executed action
            action = context.verification_state.last_action
            if not action or action.capability != 'window.activate':
                return VerificationResult(success=False, message="No activation action found")

            # Check if window is now in foreground
            foreground_hwnd = win32gui.GetForegroundWindow()

            if action.data.get('window_handle') == foreground_hwnd:
                return VerificationResult(success=True, message="Window is now in foreground")

            # Check if window handle matches
            if foreground_hwnd in [w['handle'] for w in action.data.get('windows', [])]:
                return VerificationResult(success=True, message="Window is in foreground")

            return VerificationResult(
                success=False,
                message=f"Expected window {action.data.get('window_handle')} not in foreground"
            )

        except Exception as e:
            return VerificationResult(success=False, message=f"Verification failed: {e}")

    def _verify_window_closed(self, context: NativeExecutionContext) -> VerificationResult:
        """Verify window was closed successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != 'window.close':
                return VerificationResult(success=False, message="No close action found")

            # Check if window handle still exists
            hwnd = action.data.get('window_handle')
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=True, message="Window is closed")

            return VerificationResult(
                success=False,
                message=f"Window {hwnd} is still open"
            )

        except Exception as e:
            return VerificationResult(success=False, message=f"Verification failed: {e}")

    def _verify_window_resized(self, context: NativeExecutionContext) -> VerificationResult:
        """Verify window was resized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != 'window.resize':
                return VerificationResult(success=False, message="No resize action found")

            hwnd = action.data.get('window_handle')
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            # Get current rect
            rect = win32gui.GetWindowRect(hwnd)

            expected_width = action.data.get('width', 0)
            expected_height = action.data.get('height', 0)

            if rect[2] - rect[0] == expected_width and rect[3] - rect[1] == expected_height:
                return VerificationResult(success=True, message="Window dimensions correct")

            return VerificationResult(
                success=False,
                message=f"Window dimensions incorrect: expected {expected_width}x{expected_height}, got {rect[2]-rect[0]}x{rect[3]-rect[1]}"
            )

        except Exception as e:
            return VerificationResult(success=False, message=f"Verification failed: {e}")

    def _verify_window_moved(self, context: NativeExecutionContext) -> VerificationResult:
        """Verify window was moved successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != 'window.move':
                return VerificationResult(success=False, message="No move action found")

            hwnd = action.data.get('window_handle')
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            # Get current rect
            rect = win32gui.GetWindowRect(hwnd)

            expected_left = action.data.get('left', 0)
            expected_top = action.data.get('top', 0)

            if rect[0] == expected_left and rect[1] == expected_top:
                return VerificationResult(success=True, message="Window position correct")

            return VerificationResult(
                success=False,
                message=f"Window position incorrect: expected ({expected_left}, {expected_top}), got ({rect[0]}, {rect[1]})"
            )

        except Exception as e:
            return VerificationResult(success=False, message=f"Verification failed: {e}")

    def _verify_window_maximized(self, context: NativeExecutionContext) -> VerificationResult:
        """Verify window was maximized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != 'window.maximize':
                return VerificationResult(success=False, message="No maximize action found")

            hwnd = action.data.get('window_handle')
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            if win32gui.IsZoomed(hwnd):
                return VerificationResult(success=True, message="Window is maximized")

            return VerificationResult(success=False, message="Window is not maximized")

        except Exception as e:
            return VerificationResult(success=False, message=f"Verification failed: {e}")

    def _verify_window_minimized(self, context: NativeExecutionContext) -> VerificationResult:
        """Verify window was minimized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != 'window.minimize':
                return VerificationResult(success=False, message="No minimize action found")

            hwnd = action.data.get('window_handle')
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            if win32gui.IsIconic(hwnd):
                return VerificationResult(success=True, message="Window is minimized")

            return VerificationResult(success=False, message="Window is not minimized")

        except Exception as e:
            return VerificationResult(success=False, message=f"Verification failed: {e}")

    # ==================== ROLLBACK HANDLERS ====================

    def _rollback_window_activated(self, context: NativeExecutionContext) -> bool:
        """Rollback window activation."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != 'window.activate':
                return False

            hwnd = action.data.get('window_handle')
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
            if not action or action.capability != 'window.resize':
                return False

            hwnd = action.data.get('window_handle')
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            previous_rect = action.data.get('previous_rect', {})
            if not previous_rect:
                return False

            left = previous_rect.get('left')
            top = previous_rect.get('top')
            right = previous_rect.get('right')
            bottom = previous_rect.get('bottom')

            width = right - left
            height = bottom - top

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                left, top, width, height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER
            )

            return True

        except Exception as e:
            self.logger.error(f"Rollback resize failed: {e}")
            return False

    def _rollback_window_moved(self, context: NativeExecutionContext) -> bool:
        """Rollback window move."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != 'window.move':
                return False

            hwnd = action.data.get('window_handle')
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            previous_rect = action.data.get('previous_rect', {})
            if not previous_rect:
                return False

            left = previous_rect.get('left')
            top = previous_rect.get('top')
            right = previous_rect.get('right')
            bottom = previous_rect.get('bottom')

            width = right - left
            height = bottom - top

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                left, top, width, height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE
            )

            return True

        except Exception as e:
            self.logger.error(f"Rollback move failed: {e}")
            return False

    def _rollback_window_maximized(self, context: NativeExecutionContext) -> bool:
        """Rollback window maximize."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != 'window.maximize':
                return False

            hwnd = action.data.get('window_handle')
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            # Restore to previous state
            was_maximized = action.data.get('was_maximized', False)
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
            if not action or action.capability != 'window.minimize':
                return False

            hwnd = action.data.get('window_handle')
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            # Restore window
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            return True

        except Exception as e:
            self.logger.error(f"Rollback minimize failed: {e}")
            return False
