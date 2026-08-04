"""
Display Manager
Manages display operations.
"""
from typing import List
import logging

from .native_manager import NativeManager
from .native_models import DisplayInfo
from .native_exceptions import DisplayNotFoundError

logger = logging.getLogger(__name__)


class DisplayManager:
    """Manages display operations"""

    def __init__(self, native_manager: NativeManager):
        """
        Initialize the display manager.

        Args:
            native_manager: The NativeManager instance
        """
        self.native_manager = native_manager
        logger.debug("DisplayManager initialized")

    def list_displays(self) -> List[DisplayInfo]:
        """
        List all displays.

        Returns:
            List of DisplayInfo objects
        """
        logger.debug("Listing all displays")
        return self.native_manager._display_manager.list_displays()

    def get_primary_display(self) -> DisplayInfo:
        """
        Get primary display information.

        Returns:
            DisplayInfo object
        """
        logger.debug("Getting primary display")
        return self.native_manager._display_manager.get_primary_display()

    def get_display(self, index: int) -> DisplayInfo:
        """
        Get specific display information.

        Args:
            index: Display index

        Returns:
            DisplayInfo object

        Raises:
            DisplayNotFoundError: If display not found
        """
        logger.debug(f"Getting display at index: {index}")
        return self.native_manager._display_manager.get_display(index)

    def get_display_by_name(self, name: str) -> DisplayInfo:
        """
        Get display by name.

        Args:
            name: Display name

        Returns:
            DisplayInfo object

        Raises:
            DisplayNotFoundError: If display not found
        """
        displays = self.list_displays()
        for display in displays:
            if display.name.lower() == name.lower():
                return display
        raise DisplayNotFoundError(
            f"Display not found with name: {name}",
            "get_display_by_name",
            details={"name": name}
        )

    def get_primary_display_index(self) -> int:
        """
        Get index of primary display.

        Returns:
            Display index
        """
        logger.debug("Getting primary display index")
        return self.get_primary_display().index
