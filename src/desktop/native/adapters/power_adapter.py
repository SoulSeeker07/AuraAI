"""
Power Adapter Hierarchy & Implementation

Provides PowerAdapter interface and backends:
1. WMIPowerAdapter (Primary, WMI Win32_Battery & Win32_OperatingSystem)
2. Win32PowerAdapter (Fallback, Kernel32 GetSystemPowerStatus & User32 LockWorkStation API)
3. DummyPowerAdapter (Fallback mock backend)
"""

import ctypes
import logging
from abc import abstractmethod
from ctypes import wintypes
from typing import Any

from .base_adapter import BaseNativeAdapter
from .base_adapter_factory import BaseAdapterFactory

logger = logger = logging.getLogger(__name__)


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("SystemStatusFlag", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


class PowerAdapter(BaseNativeAdapter):
    """Abstract interface for native power adapters."""

    NAME = "power_adapter"

    @abstractmethod
    def get_battery_status(self) -> dict[str, Any]:
        """Get battery level percentage and charging status."""
        raise NotImplementedError

    @abstractmethod
    def get_ac_status(self) -> dict[str, Any]:
        """Get AC power line status."""
        raise NotImplementedError

    @abstractmethod
    def get_power_plan(self) -> dict[str, Any]:
        """Get active Windows power plan scheme."""
        raise NotImplementedError

    @abstractmethod
    def lock_workstation(self) -> bool:
        """Lock the current Windows desktop session."""
        raise NotImplementedError

    @abstractmethod
    def sleep(self) -> bool:
        """Put system into sleep mode."""
        raise NotImplementedError

    @abstractmethod
    def hibernate(self) -> bool:
        """Put system into hibernate mode."""
        raise NotImplementedError

    @abstractmethod
    def shutdown(self, force: bool = False, timeout_sec: int = 0) -> bool:
        """Initiate system shutdown."""
        raise NotImplementedError

    @abstractmethod
    def restart(self, force: bool = False, timeout_sec: int = 0) -> bool:
        """Initiate system restart."""
        raise NotImplementedError

    @abstractmethod
    def logoff(self, force: bool = False) -> bool:
        """Logoff current user session."""
        raise NotImplementedError


class WMIPowerAdapter(PowerAdapter):
    """Primary WMI power adapter."""

    NAME = "wmi"
    PRIORITY = 10

    def is_available(self) -> bool:
        try:
            import wmi

            c = wmi.WMI()
            # Test OS or battery class access
            return len(c.Win32_OperatingSystem()) > 0
        except Exception as e:
            logger.debug(f"WMIPowerAdapter not available: {e}")
            return False

    def get_battery_status(self) -> dict[str, Any]:
        try:
            import wmi

            c = wmi.WMI()
            batteries = c.Win32_Battery()
            if batteries:
                b = batteries[0]
                status_code = getattr(b, "BatteryStatus", 1)
                charging = status_code in (2, 6, 7, 8, 9)
                percent = getattr(b, "EstimatedChargeRemaining", 100)
                return {
                    "has_battery": True,
                    "percent": percent,
                    "is_charging": charging,
                    "status_code": status_code,
                    "backend": self.name,
                }
        except Exception as e:
            logger.debug(f"WMI battery status read failed: {e}")

        # Fallback if no battery or desktop PC
        return {
            "has_battery": False,
            "percent": 100,
            "is_charging": True,
            "backend": self.name,
        }

    def get_ac_status(self) -> dict[str, Any]:
        batt = self.get_battery_status()
        return {
            "ac_online": batt.get("is_charging", True)
            or not batt.get("has_battery", False),
            "backend": self.name,
        }

    def get_power_plan(self) -> dict[str, Any]:
        try:
            import wmi

            c = wmi.WMI(namespace="root\\cimv2\\power")
            plans = c.Win32_PowerPlan(IsActive=True)
            if plans:
                p = plans[0]
                return {
                    "name": getattr(p, "ElementName", "Balanced"),
                    "guid": getattr(p, "InstanceID", ""),
                    "backend": self.name,
                }
        except Exception as e:
            logger.debug(f"WMI power plan query failed: {e}")

        return {"name": "Balanced", "guid": "", "backend": self.name}

    def lock_workstation(self) -> bool:
        try:
            return bool(ctypes.windll.user32.LockWorkStation())
        except Exception as e:
            logger.error(f"WMIPowerAdapter lock_workstation failed: {e}")
            return False

    def sleep(self) -> bool:
        try:
            return bool(ctypes.windll.powrprof.SetSuspendState(0, 0, 0))
        except Exception as e:
            logger.error(f"WMIPowerAdapter sleep failed: {e}")
            return False

    def hibernate(self) -> bool:
        try:
            return bool(ctypes.windll.powrprof.SetSuspendState(1, 0, 0))
        except Exception as e:
            logger.error(f"WMIPowerAdapter hibernate failed: {e}")
            return False

    def shutdown(self, force: bool = False, timeout_sec: int = 0) -> bool:
        try:
            import wmi

            c = wmi.WMI()
            os_sys = c.Win32_OperatingSystem()[0]
            # 1 = Shutdown, 4 = Forced Shutdown
            flags = 4 if force else 1
            os_sys.Win32Shutdown(flags)
            return True
        except Exception as e:
            logger.error(f"WMIPowerAdapter shutdown failed: {e}")
            return False

    def restart(self, force: bool = False, timeout_sec: int = 0) -> bool:
        try:
            import wmi

            c = wmi.WMI()
            os_sys = c.Win32_OperatingSystem()[0]
            # 2 = Reboot, 6 = Forced Reboot
            flags = 6 if force else 2
            os_sys.Win32Shutdown(flags)
            return True
        except Exception as e:
            logger.error(f"WMIPowerAdapter restart failed: {e}")
            return False

    def logoff(self, force: bool = False) -> bool:
        try:
            import wmi

            c = wmi.WMI()
            os_sys = c.Win32_OperatingSystem()[0]
            # 0 = Logoff, 4 = Forced Logoff
            flags = 4 if force else 0
            os_sys.Win32Shutdown(flags)
            return True
        except Exception as e:
            logger.error(f"WMIPowerAdapter logoff failed: {e}")
            return False


class Win32PowerAdapter(PowerAdapter):
    """Fallback Win32 Ctypes power adapter."""

    NAME = "win32"
    PRIORITY = 20

    def is_available(self) -> bool:
        try:
            return hasattr(ctypes.windll, "kernel32") and hasattr(
                ctypes.windll, "user32"
            )
        except Exception:
            return False

    def get_battery_status(self) -> dict[str, Any]:
        try:
            sps = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                has_batt = sps.BatteryFlag != 128 and sps.BatteryFlag != 255
                pct = (
                    int(sps.BatteryLifePercent)
                    if sps.BatteryLifePercent <= 100
                    else 100
                )
                charging = bool(sps.ACLineStatus == 1)
                return {
                    "has_battery": has_batt,
                    "percent": pct,
                    "is_charging": charging,
                    "backend": self.name,
                }
        except Exception as e:
            logger.debug(f"Win32 GetSystemPowerStatus failed: {e}")

        return {
            "has_battery": False,
            "percent": 100,
            "is_charging": True,
            "backend": self.name,
        }

    def get_ac_status(self) -> dict[str, Any]:
        batt = self.get_battery_status()
        return {"ac_online": batt.get("is_charging", True), "backend": self.name}

    def get_power_plan(self) -> dict[str, Any]:
        return {"name": "Balanced", "guid": "", "backend": self.name}

    def lock_workstation(self) -> bool:
        try:
            return bool(ctypes.windll.user32.LockWorkStation())
        except Exception:
            return False

    def sleep(self) -> bool:
        try:
            return bool(ctypes.windll.powrprof.SetSuspendState(0, 0, 0))
        except Exception:
            return False

    def hibernate(self) -> bool:
        try:
            return bool(ctypes.windll.powrprof.SetSuspendState(1, 0, 0))
        except Exception:
            return False

    def shutdown(self, force: bool = False, timeout_sec: int = 0) -> bool:
        try:
            # EWX_SHUTDOWN = 0x00000001, EWX_FORCE = 0x00000004
            flags = 0x00000001 | (0x00000004 if force else 0)
            return bool(ctypes.windll.user32.ExitWindowsEx(flags, 0))
        except Exception:
            return False

    def restart(self, force: bool = False, timeout_sec: int = 0) -> bool:
        try:
            # EWX_REBOOT = 0x00000002
            flags = 0x00000002 | (0x00000004 if force else 0)
            return bool(ctypes.windll.user32.ExitWindowsEx(flags, 0))
        except Exception:
            return False

    def logoff(self, force: bool = False) -> bool:
        try:
            # EWX_LOGOFF = 0x00000000
            flags = 0x00000000 | (0x00000004 if force else 0)
            return bool(ctypes.windll.user32.ExitWindowsEx(flags, 0))
        except Exception:
            return False


class DummyPowerAdapter(PowerAdapter):
    """Fallback dummy power adapter for virtualized/test environments."""

    NAME = "dummy"
    PRIORITY = 100

    def is_available(self) -> bool:
        return True

    def get_battery_status(self) -> dict[str, Any]:
        return {
            "has_battery": True,
            "percent": 95,
            "is_charging": True,
            "backend": self.name,
        }

    def get_ac_status(self) -> dict[str, Any]:
        return {"ac_online": True, "backend": self.name}

    def get_power_plan(self) -> dict[str, Any]:
        return {"name": "High Performance", "guid": "mock_guid", "backend": self.name}

    def lock_workstation(self) -> bool:
        return True

    def sleep(self) -> bool:
        return True

    def hibernate(self) -> bool:
        return True

    def shutdown(self, force: bool = False, timeout_sec: int = 0) -> bool:
        return True

    def restart(self, force: bool = False, timeout_sec: int = 0) -> bool:
        return True

    def logoff(self, force: bool = False) -> bool:
        return True


class PowerAdapterFactory(BaseAdapterFactory[PowerAdapter]):
    """Factory to discover and instantiate power adapters in priority order."""

    _adapter_classes = [WMIPowerAdapter, Win32PowerAdapter, DummyPowerAdapter]
