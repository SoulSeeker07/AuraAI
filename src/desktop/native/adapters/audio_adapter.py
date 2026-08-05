"""
Audio Adapter Hierarchy & Implementation

Provides AudioAdapter interface and backends:
1. PyCAWAudioAdapter (Primary, CoreAudio via PyCAW / comtypes)
2. WinMMAudioAdapter (Fallback, WinMM API)
3. DummyAudioAdapter (Fallback mock backend)
"""

import ctypes
import logging
from abc import abstractmethod
from typing import Any

from .base_adapter import BaseNativeAdapter
from .base_adapter_factory import BaseAdapterFactory

logger = logging.getLogger(__name__)


class AudioAdapter(BaseNativeAdapter):
    """Abstract interface for native audio adapters."""

    NAME = "audio_adapter"

    @abstractmethod
    def list_devices(self) -> list[dict[str, Any]]:
        """List connected audio input and output devices."""
        raise NotImplementedError

    @abstractmethod
    def get_default_output(self) -> dict[str, Any] | None:
        """Get default audio output device."""
        raise NotImplementedError

    @abstractmethod
    def get_default_input(self) -> dict[str, Any] | None:
        """Get default audio input device."""
        raise NotImplementedError

    @abstractmethod
    def get_volume(self) -> dict[str, Any]:
        """Get current volume level (0-100) and mute status."""
        raise NotImplementedError

    @abstractmethod
    def set_volume(self, level: float) -> bool:
        """Set volume level (0-100)."""
        raise NotImplementedError

    @abstractmethod
    def get_mute(self) -> bool:
        """Get mute status."""
        raise NotImplementedError

    @abstractmethod
    def set_mute(self, muted: bool) -> bool:
        """Set mute status."""
        raise NotImplementedError


class PyCAWAudioAdapter(AudioAdapter):
    """Primary audio adapter using PyCAW and comtypes (CoreAudio Windows Endpoint Volume)."""

    NAME = "pycaw"
    PRIORITY = 10

    def is_available(self) -> bool:
        """Check if pycaw and comtypes are installed and functional."""
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            comtypes.CoInitialize()
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
                )
                volume_ctrl = ctypes.cast(
                    interface, ctypes.POINTER(IAudioEndpointVolume)
                )
                return volume_ctrl is not None
            finally:
                comtypes.CoUninitialize()
        except Exception as e:
            logger.debug(f"PyCAWAudioAdapter not available: {e}")
            return False

    def list_devices(self) -> list[dict[str, Any]]:
        devices = []
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities

            comtypes.CoInitialize()
            try:
                speakers = AudioUtilities.GetSpeakers()
                devices.append(
                    {
                        "id": "pycaw_default_output",
                        "name": getattr(
                            speakers, "FriendlyName", "Default Output Speakers"
                        ),
                        "type": "output",
                        "is_default": True,
                    }
                )
                microphone = AudioUtilities.GetMicrophone()
                if microphone:
                    devices.append(
                        {
                            "id": "pycaw_default_input",
                            "name": getattr(
                                microphone, "FriendlyName", "Default Microphone"
                            ),
                            "type": "input",
                            "is_default": True,
                        }
                    )
            finally:
                comtypes.CoUninitialize()
        except Exception as e:
            logger.error(f"PyCAW list_devices failed: {e}")
        return devices

    def get_default_output(self) -> dict[str, Any] | None:
        devs = self.list_devices()
        return next((d for d in devs if d["type"] == "output"), None)

    def get_default_input(self) -> dict[str, Any] | None:
        devs = self.list_devices()
        return next((d for d in devs if d["type"] == "input"), None)

    def _get_volume_ctrl(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        comtypes.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
        )
        return comtypes, ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))

    def get_volume(self) -> dict[str, Any]:
        try:
            comtypes, volume_ctrl = self._get_volume_ctrl()
            try:
                vol_scalar = volume_ctrl.GetMasterVolumeLevelScalar()
                muted = bool(volume_ctrl.GetMute())
                level = round(vol_scalar * 100, 1)
                return {"level": level, "muted": muted, "backend": self.name}
            finally:
                comtypes.CoUninitialize()
        except Exception as e:
            logger.error(f"PyCAW get_volume failed: {e}")
            return {
                "level": 50.0,
                "muted": False,
                "backend": self.name,
                "error": str(e),
            }

    def set_volume(self, level: float) -> bool:
        target = max(0.0, min(100.0, float(level))) / 100.0
        try:
            comtypes, volume_ctrl = self._get_volume_ctrl()
            try:
                volume_ctrl.SetMasterVolumeLevelScalar(target, None)
                return True
            finally:
                comtypes.CoUninitialize()
        except Exception as e:
            logger.error(f"PyCAW set_volume failed: {e}")
            return False

    def get_mute(self) -> bool:
        res = self.get_volume()
        return res.get("muted", False)

    def set_mute(self, muted: bool) -> bool:
        try:
            comtypes, volume_ctrl = self._get_volume_ctrl()
            try:
                volume_ctrl.SetMute(1 if muted else 0, None)
                return True
            finally:
                comtypes.CoUninitialize()
        except Exception as e:
            logger.error(f"PyCAW set_mute failed: {e}")
            return False


class WinMMAudioAdapter(AudioAdapter):
    """Fallback audio adapter using Win32 WinMM API."""

    NAME = "winmm"
    PRIORITY = 20

    def is_available(self) -> bool:
        try:
            return hasattr(ctypes.windll, "winmm")
        except Exception:
            return False

    def list_devices(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "winmm_speakers",
                "name": "Windows Multimedia Audio",
                "type": "output",
                "is_default": True,
            }
        ]

    def get_default_output(self) -> dict[str, Any] | None:
        return self.list_devices()[0]

    def get_default_input(self) -> dict[str, Any] | None:
        return None

    def get_volume(self) -> dict[str, Any]:
        try:
            vol_val = ctypes.c_ulong()
            res = ctypes.windll.winmm.waveOutGetVolume(0, ctypes.byref(vol_val))
            if res == 0:
                # low word left channel, high word right channel
                left = vol_val.value & 0xFFFF
                level = round((left / 0xFFFF) * 100, 1)
                return {"level": level, "muted": False, "backend": self.name}
        except Exception as e:
            logger.debug(f"WinMM waveOutGetVolume failed: {e}")

        return {"level": 50.0, "muted": False, "backend": self.name}

    def set_volume(self, level: float) -> bool:
        try:
            target_scalar = max(0.0, min(100.0, float(level))) / 100.0
            word_val = int(target_scalar * 0xFFFF)
            dw_vol = (word_val & 0xFFFF) | ((word_val & 0xFFFF) << 16)
            res = ctypes.windll.winmm.waveOutSetVolume(0, dw_vol)
            return res == 0
        except Exception as e:
            logger.error(f"WinMM set_volume failed: {e}")
            return False

    def get_mute(self) -> bool:
        return False

    def set_mute(self, muted: bool) -> bool:
        if muted:
            return self.set_volume(0)
        return True


class DummyAudioAdapter(AudioAdapter):
    """Fallback dummy audio adapter for environments without audio hardware or testing."""

    NAME = "dummy"
    PRIORITY = 100

    def __init__(self):
        super().__init__()
        self._level: float = 50.0
        self._muted: bool = False

    def is_available(self) -> bool:
        return True

    def list_devices(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "dummy_output",
                "name": "Mock Default Speakers",
                "type": "output",
                "is_default": True,
            },
            {
                "id": "dummy_input",
                "name": "Mock Default Microphone",
                "type": "input",
                "is_default": True,
            },
        ]

    def get_default_output(self) -> dict[str, Any] | None:
        return self.list_devices()[0]

    def get_default_input(self) -> dict[str, Any] | None:
        return self.list_devices()[1]

    def get_volume(self) -> dict[str, Any]:
        return {"level": self._level, "muted": self._muted, "backend": self.name}

    def set_volume(self, level: float) -> bool:
        self._level = max(0.0, min(100.0, float(level)))
        return True

    def get_mute(self) -> bool:
        return self._muted

    def set_mute(self, muted: bool) -> bool:
        self._muted = bool(muted)
        return True


class AudioAdapterFactory(BaseAdapterFactory[AudioAdapter]):
    """Factory to discover and instantiate audio adapters in priority order."""

    _adapter_classes = [PyCAWAudioAdapter, WinMMAudioAdapter, DummyAudioAdapter]
