"""
Audio Manager
Manages audio device operations.
"""
from typing import List
import logging

from .native_manager import NativeManager
from .native_models import AudioDevice
from .native_exceptions import AudioDeviceNotFoundError

logger = logging.getLogger(__name__)


class AudioManager:
    """Manages audio device operations"""

    def __init__(self, native_manager: NativeManager):
        """
        Initialize the audio manager.

        Args:
            native_manager: The NativeManager instance
        """
        self.native_manager = native_manager
        logger.debug("AudioManager initialized")

    def list_devices(self) -> List[AudioDevice]:
        """
        List all audio devices.

        Returns:
            List of AudioDevice objects
        """
        logger.debug("Listing all audio devices")
        return self.native_manager._audio_manager.list_devices()

    def get_default_output_device(self) -> AudioDevice:
        """
        Get default audio output device.

        Returns:
            AudioDevice object
        """
        logger.debug("Getting default output device")
        return self.native_manager._audio_manager.get_default_output_device()

    def get_default_input_device(self) -> AudioDevice:
        """
        Get default audio input device.

        Returns:
            AudioDevice object
        """
        logger.debug("Getting default input device")
        return self.native_manager._audio_manager.get_default_input_device()

    def get_device_by_index(self, index: int) -> AudioDevice:
        """
        Get audio device by index.

        Args:
            index: Device index

        Returns:
            AudioDevice object

        Raises:
            AudioDeviceNotFoundError: If device not found
        """
        logger.debug(f"Getting audio device at index: {index}")
        return self.native_manager._audio_manager.get_device_by_index(index)

    def get_device_by_name(self, name: str) -> AudioDevice:
        """
        Get audio device by name.

        Args:
            name: Device name

        Returns:
            AudioDevice object

        Raises:
            AudioDeviceNotFoundError: If device not found
        """
        devices = self.list_devices()
        for device in devices:
            if device.name.lower() == name.lower():
                return device
        raise AudioDeviceNotFoundError(
            f"Audio device not found with name: {name}",
            "get_device_by_name",
            details={"name": name}
        )

    def set_volume(self, device_index: int, volume: float) -> bool:
        """
        Set audio device volume (0.0 to 1.0).

        Args:
            device_index: Device index
            volume: Volume level (0.0 to 1.0)

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Setting volume for device {device_index}: {volume}")
        return self.native_manager._audio_manager.set_volume(device_index, volume)

    def get_volume(self, device_index: int) -> float:
        """
        Get audio device volume.

        Args:
            device_index: Device index

        Returns:
            Volume level (0.0 to 1.0)
        """
        logger.debug(f"Getting volume for device {device_index}")
        return self.native_manager._audio_manager.get_volume(device_index)

    def mute_device(self, device_index: int, mute: bool) -> bool:
        """
        Mute/unmute audio device.

        Args:
            device_index: Device index
            mute: True to mute, False to unmute

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"{'Muting' if mute else 'Unmuting'} device {device_index}")
        return self.native_manager._audio_manager.mute_device(device_index, mute)

    def is_device_muted(self, device_index: int) -> bool:
        """
        Check if audio device is muted.

        Args:
            device_index: Device index

        Returns:
            True if muted, False otherwise
        """
        logger.debug(f"Checking if device {device_index} is muted")
        return self.native_manager._audio_manager.is_device_muted(device_index)
