"""
Display Manager for Native Windows Layer

Manages Windows display operations (monitors, resolution, orientation, layout, DPI, brightness) using Win32 API.
All cross-cutting concerns (permissions, verification, rollback, diagnostics) are
handled by the execution pipeline.

This manager ONLY contains Windows-specific code.
"""

from typing import List, Dict, Any, Optional
import logging

from .base_manager import BaseNativeManager
from ..desktop_result import DesktopResult, DesktopStatus
from ..native_exceptions import NativeError
from . import display_helpers

logger = logging.getLogger(__name__)


class DisplayManager(BaseNativeManager):
    """
    Manages Windows display operations.

    Capabilities:
    - display.list / list_displays: Enumerate all connected display monitors
    - display.primary / get_primary_display: Get primary display monitor info
    - display.info / get_display_info: Get detailed info for specific display
    - display.layout / get_display_layout: Get overall virtual desktop layout
    - display.dpi / get_dpi: Get monitor DPI awareness info
    - display.brightness / get_brightness: Get display brightness level
    - display.set_brightness / set_brightness: Set display brightness level
    - display.set_resolution / set_resolution: Change display resolution
    - display.set_orientation / set_orientation: Change screen orientation
    """

    NAME = "display"
    VERSION = "1.0"
    PRIORITY = 20
    DEPENDENCIES = ["win32api", "win32con", "wmi"]

    def __init__(self):
        """Initialize display manager."""
        super().__init__()

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> List[str]:
        """Get list of capabilities supported by DisplayManager."""
        return [
            "list_displays",
            "get_primary_display",
            "get_display_info",
            "get_display_layout",
            "get_dpi",
            "get_brightness",
            "set_brightness",
            "set_resolution",
            "set_orientation",
            "display.list",
            "display.primary",
            "display.info",
            "display.layout",
            "display.dpi",
            "display.brightness",
            "display.set_brightness",
            "display.set_resolution",
            "display.set_orientation",
        ]

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> DesktopResult:
        """
        Execute native display operation for the given capability.

        Returns:
            DesktopResult with execution data or failure message.
        """
        arguments = arguments or {}
        arguments.update(kwargs)

        try:
            logger.info(f"DisplayManager executing capability: {capability}")
            cap_clean = capability.lower()

            if cap_clean in ("list_displays", "display.list"):
                return self._handle_list_displays(goal=goal, capability=capability)

            elif cap_clean in ("get_primary_display", "display.primary"):
                return self._handle_get_primary(goal=goal, capability=capability)

            elif cap_clean in ("get_display_info", "display.info"):
                return self._handle_get_info(goal=goal, capability=capability, arguments=arguments)

            elif cap_clean in ("get_display_layout", "display.layout"):
                return self._handle_get_layout(goal=goal, capability=capability)

            elif cap_clean in ("get_dpi", "display.dpi"):
                return self._handle_get_dpi(goal=goal, capability=capability, arguments=arguments)

            elif cap_clean in ("get_brightness", "display.brightness"):
                return self._handle_get_brightness(goal=goal, capability=capability)

            elif cap_clean in ("set_brightness", "display.set_brightness"):
                return self._handle_set_brightness(goal=goal, capability=capability, arguments=arguments)

            elif cap_clean in ("set_resolution", "display.set_resolution"):
                return self._handle_set_resolution(goal=goal, capability=capability, arguments=arguments)

            elif cap_clean in ("set_orientation", "display.set_orientation"):
                return self._handle_set_orientation(goal=goal, capability=capability, arguments=arguments)

            else:
                return DesktopResult.create_failure(
                    goal=goal, capability=capability, manager=self.name,
                    error=f"Capability '{capability}' not supported by DisplayManager"
                )

        except Exception as e:
            logger.error(f"DisplayManager execution failed: {e}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name,
                error=str(e)
            )

    # ==================== Handler Implementations ====================

    def _handle_list_displays(self, goal: str, capability: str) -> DesktopResult:
        monitors = display_helpers.enumerate_monitors()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name,
            data={"monitors": monitors, "count": len(monitors)},
            events=["displays_listed"],
        )

    def _handle_get_primary(self, goal: str, capability: str) -> DesktopResult:
        monitors = display_helpers.enumerate_monitors()
        primary = next((m for m in monitors if m.get("is_primary")), monitors[0] if monitors else None)
        if not primary:
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error="No primary display found"
            )

        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name,
            data={"primary_display": primary},
            events=["primary_display_retrieved"],
        )

    def _handle_get_info(self, goal: str, capability: str, arguments: Dict[str, Any]) -> DesktopResult:
        target_id = arguments.get("display_id") or arguments.get("device_name")
        monitors = display_helpers.enumerate_monitors()

        if target_id:
            target = next((m for m in monitors if m["id"] == target_id or m["device_name"] == target_id), None)
        else:
            target = next((m for m in monitors if m.get("is_primary")), monitors[0] if monitors else None)

        if not target:
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name,
                error=f"Display '{target_id}' not found"
            )

        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name,
            data={"display": target},
        )

    def _handle_get_layout(self, goal: str, capability: str) -> DesktopResult:
        layout = display_helpers.get_display_layout()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name,
            data=layout,
        )

    def _handle_get_dpi(self, goal: str, capability: str, arguments: Dict[str, Any]) -> DesktopResult:
        handle = arguments.get("handle")
        dpi_info = display_helpers.get_display_dpi(handle)
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name,
            data=dpi_info,
        )

    def _handle_get_brightness(self, goal: str, capability: str) -> DesktopResult:
        brightness_info = display_helpers.get_display_brightness()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name,
            data=brightness_info,
        )

    def _handle_set_brightness(self, goal: str, capability: str, arguments: Dict[str, Any]) -> DesktopResult:
        level = arguments.get("level")
        if level is None:
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error="Argument 'level' (0-100) is required"
            )

        res = display_helpers.set_display_brightness(level)
        if res.get("success"):
            return DesktopResult.create_success(
                goal=goal, capability=capability, manager=self.name, data=res, events=["brightness_changed"]
            )
        else:
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error=res.get("error", "Failed to set brightness")
            )

    def _handle_set_resolution(self, goal: str, capability: str, arguments: Dict[str, Any]) -> DesktopResult:
        width = arguments.get("width")
        height = arguments.get("height")
        device_name = arguments.get("device_name", "\\\\.\\DISPLAY1")

        if not width or not height:
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error="Arguments 'width' and 'height' required"
            )

        ok = display_helpers.set_display_resolution(device_name, width, height)
        if ok:
            return DesktopResult.create_success(
                goal=goal, capability=capability, manager=self.name,
                data={"device_name": device_name, "width": width, "height": height},
                events=["resolution_changed"]
            )
        else:
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error="Failed to change resolution"
            )

    def _handle_set_orientation(self, goal: str, capability: str, arguments: Dict[str, Any]) -> DesktopResult:
        orientation = arguments.get("orientation", 0)
        device_name = arguments.get("device_name", "\\\\.\\DISPLAY1")

        ok = display_helpers.set_display_orientation(device_name, orientation)
        if ok:
            return DesktopResult.create_success(
                goal=goal, capability=capability, manager=self.name,
                data={"device_name": device_name, "orientation": orientation},
                events=["orientation_changed"]
            )
        else:
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error="Failed to change orientation"
            )
