"""
Display Win32 Helper Utilities

Internal low-level Win32 helper functions for monitor enumeration, resolution,
orientation, DPI awareness, and brightness configuration.
"""

import ctypes
import logging
from typing import Any

import win32api
import win32con

logger = logging.getLogger(__name__)


def enumerate_monitors() -> list[dict[str, Any]]:
    """
    Enumerate all connected display monitors and their adapters using Win32 API.

    Returns:
        List of dicts containing monitor properties (id, device_name, bounds, is_primary).
    """
    monitors = []
    i = 0
    primary_found = False

    try:
        monitor_handles = win32api.EnumDisplayMonitors()
        for handle, hdc, rect in monitor_handles:
            info = win32api.GetMonitorInfo(handle)
            monitor_rect = info.get("Monitor", rect)
            work_rect = info.get("Work", rect)
            device_name = info.get("Device", f"\\\\.\\DISPLAY{i+1}")
            flags = info.get("Flags", 0)
            is_primary = bool(flags & win32con.MONITORINFOF_PRIMARY)

            if is_primary:
                primary_found = True

            # Get display mode settings
            mode_settings = get_display_settings(device_name)

            monitors.append(
                {
                    "id": f"display_{i+1}",
                    "handle": int(handle),
                    "device_name": device_name,
                    "is_primary": is_primary,
                    "bounds": {
                        "left": monitor_rect[0],
                        "top": monitor_rect[1],
                        "right": monitor_rect[2],
                        "bottom": monitor_rect[3],
                        "width": monitor_rect[2] - monitor_rect[0],
                        "height": monitor_rect[3] - monitor_rect[1],
                    },
                    "work_area": {
                        "left": work_rect[0],
                        "top": work_rect[1],
                        "right": work_rect[2],
                        "bottom": work_rect[3],
                        "width": work_rect[2] - work_rect[0],
                        "height": work_rect[3] - work_rect[1],
                    },
                    "resolution": {
                        "width": mode_settings.get(
                            "width", monitor_rect[2] - monitor_rect[0]
                        ),
                        "height": mode_settings.get(
                            "height", monitor_rect[3] - monitor_rect[1]
                        ),
                    },
                    "refresh_rate": mode_settings.get("refresh_rate", 60),
                    "bits_per_pixel": mode_settings.get("bits_per_pixel", 32),
                    "orientation": mode_settings.get("orientation", 0),
                }
            )
            i += 1
    except Exception as e:
        logger.error(f"Error enumerating monitors via win32api: {e}")

    # Fallback to system metrics if no monitors enumerated
    if not monitors:
        width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        monitors.append(
            {
                "id": "display_1",
                "handle": 0,
                "device_name": "\\\\.\\DISPLAY1",
                "is_primary": True,
                "bounds": {
                    "left": 0,
                    "top": 0,
                    "right": width,
                    "bottom": height,
                    "width": width,
                    "height": height,
                },
                "work_area": {
                    "left": 0,
                    "top": 0,
                    "right": width,
                    "bottom": height,
                    "width": width,
                    "height": height,
                },
                "resolution": {"width": width, "height": height},
                "refresh_rate": 60,
                "bits_per_pixel": 32,
                "orientation": 0,
            }
        )

    return monitors


def get_display_settings(device_name: str) -> dict[str, Any]:
    """
    Get current display mode settings for a device name.

    Args:
        device_name: Windows device string (e.g., "\\\\.\\DISPLAY1")

    Returns:
        Dict with width, height, refresh_rate, bits_per_pixel, orientation.
    """
    try:
        devmode = win32api.EnumDisplaySettings(
            device_name, win32con.ENUM_CURRENT_SETTINGS
        )
        return {
            "width": devmode.PelsWidth,
            "height": devmode.PelsHeight,
            "refresh_rate": devmode.DisplayFrequency,
            "bits_per_pixel": devmode.BitsPerPel,
            "orientation": devmode.DisplayOrientation,
        }
    except Exception as e:
        logger.warning(f"Could not get display settings for {device_name}: {e}")
        return {
            "width": win32api.GetSystemMetrics(win32con.SM_CXSCREEN),
            "height": win32api.GetSystemMetrics(win32con.SM_CYSCREEN),
            "refresh_rate": 60,
            "bits_per_pixel": 32,
            "orientation": 0,
        }


def get_display_layout() -> dict[str, Any]:
    """
    Get overall virtual desktop bounding box and layout geometry across all monitors.

    Returns:
        Dict containing virtual screen bounds and total monitor count.
    """
    left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
    top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
    width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    monitor_count = win32api.GetSystemMetrics(win32con.SM_CMONITORS)

    return {
        "virtual_screen": {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "right": left + width,
            "bottom": top + height,
        },
        "monitor_count": monitor_count,
    }


def get_display_dpi(handle: int | None = None) -> dict[str, Any]:
    """
    Get DPI awareness information for a monitor handle or primary screen.

    Returns:
        Dict with dpi_x, dpi_y, scale_factor.
    """
    try:
        shcore = ctypes.windll.shcore
        # PROCESS_PER_MONITOR_DPI_AWARE
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()

        if handle:
            shcore.GetDpiForMonitor(handle, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
            dx = dpi_x.value
            dy = dpi_y.value
        else:
            hdc = win32api.GetDC(0)
            dx = win32api.GetDeviceCaps(hdc, win32con.LOGPIXELSX)
            dy = win32api.GetDeviceCaps(hdc, win32con.LOGPIXELSY)
            win32api.ReleaseDC(0, hdc)

        scale_factor = round((dx / 96.0) * 100, 2)
        return {
            "dpi_x": dx,
            "dpi_y": dy,
            "scale_factor_percent": scale_factor,
        }
    except Exception as e:
        logger.warning(f"Could not get display DPI: {e}")
        return {"dpi_x": 96, "dpi_y": 96, "scale_factor_percent": 100.0}


def get_display_brightness() -> dict[str, Any]:
    """
    Get display brightness using WMI (WmiMonitorBrightness).

    Returns:
        Dict with current_brightness, levels, and method.
    """
    # Primary: screen_brightness_control
    try:
        import screen_brightness_control as sbc
        vals = sbc.get_brightness()
        if vals is not None:
            lvl = vals[0] if isinstance(vals, list) and vals else int(vals)
            return {
                "level": lvl,
                "supported": True,
                "method": "sbc",
            }
    except Exception as e:
        logger.debug(f"sbc brightness read notice: {e}")

    com_init = False
    try:
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_init = True
        except Exception:
            pass
        import wmi

        c = wmi.WMI(namespace="wmi")
        brightness_instances = c.WmiMonitorBrightness()
        if brightness_instances:
            inst = brightness_instances[0]
            return {
                "level": int(inst.CurrentBrightness),
                "supported": True,
                "method": "wmi",
            }
    except Exception as e:
        logger.debug(f"WMI brightness read failed/unsupported: {e}")
    finally:
        if com_init:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    # Software fallback
    return {
        "level": 100,
        "supported": False,
        "method": "fallback_software",
    }


def set_display_brightness(level: int) -> dict[str, Any]:
    """
    Set display brightness using screen_brightness_control with WMI fallback.

    Args:
        level: Target brightness level (0-100)

    Returns:
        Dict with success status and level.
    """
    target_level = max(0, min(100, int(level)))

    # 1. Primary: screen_brightness_control
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(target_level)
        return {"success": True, "level": target_level, "method": "sbc"}
    except Exception as e:
        logger.debug(f"sbc set_brightness notice: {e}")

    # 2. Secondary: WMI
    com_init = False
    try:
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_init = True
        except Exception:
            pass
        import wmi

        c = wmi.WMI(namespace="wmi")
        methods = c.WmiMonitorBrightnessMethods()
        if methods:
            methods[0].WmiSetBrightness(target_level, 0)
            return {"success": True, "level": target_level, "method": "wmi"}
    except Exception as e:
        logger.warning(f"Could not set brightness via WMI: {e}")
    finally:
        if com_init:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    return {
        "success": False,
        "level": target_level,
        "error": "Brightness control unsupported on hardware",
    }


def get_display_settings(device_name: str = "\\\\.\\DISPLAY1") -> dict[str, Any] | None:
    """Get current DEVMODE settings for a specific display device."""
    try:
        devmode = win32api.EnumDisplaySettings(
            device_name, win32con.ENUM_CURRENT_SETTINGS
        )
        if devmode:
            return {
                "width": devmode.PelsWidth,
                "height": devmode.PelsHeight,
                "orientation": devmode.DisplayOrientation,
                "bits_per_pel": devmode.BitsPerPel,
                "display_frequency": devmode.DisplayFrequency,
            }
    except Exception as e:
        logger.debug(f"EnumDisplaySettings failed for {device_name}: {e}")
    return None


def set_display_resolution(device_name: str, width: int, height: int) -> bool:
    """
    Change display resolution using ChangeDisplaySettingsEx.

    Args:
        device_name: Device string (e.g. "\\\\.\\DISPLAY1")
        width: Pixel width
        height: Pixel height

    Returns:
        True if successful.
    """
    try:
        devmode = win32api.EnumDisplaySettings(
            device_name, win32con.ENUM_CURRENT_SETTINGS
        )
        devmode.PelsWidth = width
        devmode.PelsHeight = height
        devmode.Fields = win32con.DM_PELSWIDTH | win32con.DM_PELSHEIGHT

        res = win32api.ChangeDisplaySettingsEx(device_name, devmode, 0)
        return res == win32con.DISP_CHANGE_SUCCESSFUL
    except Exception as e:
        logger.error(f"Failed to change display resolution for {device_name}: {e}")
        return False


def set_display_orientation(device_name: str, orientation: int) -> bool:
    """
    Change display orientation (0=landscape, 1=portrait, 2=flipped landscape, 3=flipped portrait).

    Args:
        device_name: Device string
        orientation: 0, 1, 2, or 3

    Returns:
        True if successful.
    """
    try:
        devmode = win32api.EnumDisplaySettings(
            device_name, win32con.ENUM_CURRENT_SETTINGS
        )
        # Swap width/height if orientation changes between landscape and portrait
        current_orient = devmode.DisplayOrientation
        if (current_orient in (0, 2) and orientation in (1, 3)) or (
            current_orient in (1, 3) and orientation in (0, 2)
        ):
            devmode.PelsWidth, devmode.PelsHeight = (
                devmode.PelsHeight,
                devmode.PelsWidth,
            )

        devmode.DisplayOrientation = orientation
        devmode.Fields = (
            win32con.DM_DISPLAYORIENTATION
            | win32con.DM_PELSWIDTH
            | win32con.DM_PELSHEIGHT
        )

        res = win32api.ChangeDisplaySettingsEx(device_name, devmode, 0)
        return res == win32con.DISP_CHANGE_SUCCESSFUL
    except Exception as e:
        logger.error(f"Failed to change display orientation for {device_name}: {e}")
        return False
