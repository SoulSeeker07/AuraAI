"""
Power Manager
Manages power operations.
"""
from typing import Optional
import logging

from .native_manager import NativeManager
from .native_models import DisplayInfo
from .native_exceptions import PowerError

logger = logging.getLogger(__name__)


class PowerManager:
    """Manages power operations"""

    def __init__(self, native_manager: NativeManager):
        """
        Initialize the power manager.

        Args:
            native_manager: The NativeManager instance
        """
        self.native_manager = native_manager
        logger.debug("PowerManager initialized")

    def shutdown(self) -> bool:
        """
        Shutdown the system.

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Shutting down system")
        return self.native_manager._power_manager.shutdown()

    def restart(self) -> bool:
        """
        Restart the system.

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Restarting system")
        return self.native_manager._power_manager.restart()

    def sleep(self) -> bool:
        """
        Sleep the system.

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Sleeping system")
        return self.native_manager._power_manager.sleep()

    def hibernate(self) -> bool:
        """
        Hibernate the system.

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Hibernating system")
        return self.native_manager._power_manager.hibernate()

    def lock(self) -> bool:
        """
        Lock the system.

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Locking system")
        return self.native_manager._power_manager.lock()

    def logoff(self) -> bool:
        """
        Log off the current user.

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Logging off user")
        return self.native_manager._power_manager.logoff()

    def get_battery_level(self) -> Optional[float]:
        """
        Get current battery level (0.0 to 1.0).

        Returns:
            Battery level as float (0.0-1.0) or None if not battery-powered
        """
        logger.debug("Getting battery level")
        return self.native_manager._power_manager.get_battery_level()

    def is_battery_charging(self) -> bool:
        """
        Check if battery is charging.

        Returns:
            True if charging, False otherwise
        """
        logger.debug("Checking if battery is charging")
        return self.native_manager._power_manager.is_battery_charging()
