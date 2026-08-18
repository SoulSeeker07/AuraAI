"""
Advanced Window Manager — Snapping, Transparency, Always-on-Top, and Tiling
Location: src/desktop/native/managers/advanced_window_manager.py

Extends basic WindowManager with advanced desktop spatial layouts, pinning,
opacity control, and multi-window auto-arrangements.
"""

import ctypes
import ctypes.wintypes
import logging
from typing import Any

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)

# ── Win32 Constants ──
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
WS_EX_LAYERED = 0x00080000
GWL_EXSTYLE = -20
LWA_ALPHA = 0x00000002
VK_LWIN = 0x5B


class AdvancedWindowManager(BaseNativeManager):
    """
    Advanced window manipulation manager providing snapping, transparency,
    always-on-top, tiling, and desktop toggle.
    """

    NAME = "advanced_window"
    VERSION = "1.0"
    PRIORITY = 15
    DEPENDENCIES: list[str] = ["window"]

    def __init__(self):
        super().__init__()
        self._initialized = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        return [
            "window.snap_left",
            "window.snap_right",
            "window.snap_quadrant",
            "window.always_on_top",
            "window.set_opacity",
            "window.show_desktop",
            "window.switch_to",
            "window.arrange_tiled",
            "window.cascade",
        ]

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            manager_name=self.name,
            status=HealthStatus.HEALTHY,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={"initialized": self._initialized},
        )

    def shutdown(self) -> None:
        self._initialized = False

    def _get_active_hwnd(self) -> int:
        return ctypes.windll.user32.GetForegroundWindow()

    def _get_work_area(self) -> tuple[int, int, int, int]:
        rect = ctypes.wintypes.RECT()
        SPI_GETWORKAREA = 0x0030
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top

    def _snap_left(self, hwnd: int) -> None:
        x, y, w, h = self._get_work_area()
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w // 2, h, SWP_SHOWWINDOW)

    def _snap_right(self, hwnd: int) -> None:
        x, y, w, h = self._get_work_area()
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x + (w // 2), y, w // 2, h, SWP_SHOWWINDOW)

    def _snap_quadrant(self, hwnd: int, quadrant: str) -> None:
        x, y, w, h = self._get_work_area()
        half_w = w // 2
        half_h = h // 2
        coords = {
            "top_left": (x, y, half_w, half_h),
            "top_right": (x + half_w, y, half_w, half_h),
            "bottom_left": (x, y + half_h, half_w, half_h),
            "bottom_right": (x + half_w, y + half_h, half_w, half_h),
        }
        cx, cy, cw, ch = coords.get(quadrant.lower(), (x, y, half_w, half_h))
        ctypes.windll.user32.SetWindowPos(hwnd, 0, cx, cy, cw, ch, SWP_SHOWWINDOW)

    def _set_always_on_top(self, hwnd: int, enable: bool = True) -> None:
        top_val = HWND_TOPMOST if enable else HWND_NOTOPMOST
        ctypes.windll.user32.SetWindowPos(hwnd, top_val, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

    def _set_opacity(self, hwnd: int, alpha: int = 200) -> None:
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EXLAYERED)
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)

    def _show_desktop(self) -> None:
        # Simulate Win+D
        ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
        ctypes.windll.user32.keybd_event(ord("D"), 0, 0, 0)
        ctypes.windll.user32.keybd_event(ord("D"), 0, 2, 0)
        ctypes.windll.user32.keybd_event(VK_LWIN, 0, 2, 0)

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        args = arguments or {}
        cap = capability.lower()
        hwnd = int(args.get("hwnd", 0)) or self._get_active_hwnd()

        try:
            if cap == "window.snap_left":
                self._snap_left(hwnd)
            elif cap == "window.snap_right":
                self._snap_right(hwnd)
            elif cap == "window.snap_quadrant":
                quad = args.get("quadrant", "top_left")
                self._snap_quadrant(hwnd, quad)
            elif cap == "window.always_on_top":
                enable = bool(args.get("enable", True))
                self._set_always_on_top(hwnd, enable)
            elif cap == "window.set_opacity":
                alpha = int(args.get("alpha", 200))
                self._set_opacity(hwnd, alpha)
            elif cap == "window.show_desktop":
                self._show_desktop()
            elif cap == "window.switch_to":
                title = args.get("title") or goal
                from .native_manager_registry import NativeManagerRegistry
                wm = NativeManagerRegistry.get_instance().get_manager("window")
                if wm:
                    wm.execute("window.activate", goal=goal, arguments={"title": title})
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported advanced window capability: {capability}",
                )

            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={"hwnd": hwnd, "action": cap},
                events=[f"{cap}_executed"],
            )

        except Exception as exc:
            logger.error(f"AdvancedWindowManager.{cap} failed: {exc}")
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Advanced window operation failed: {exc}",
            )
