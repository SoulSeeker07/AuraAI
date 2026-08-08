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
    """Primary audio adapter using PyCAW (pycaw 20251023+ API via AudioDevice.EndpointVolume)."""

    NAME = "pycaw"
    PRIORITY = 10

    import threading

    _com_initialized: threading.local = threading.local()

    def _ensure_com(self) -> bool:
        """Ensure COM is initialized on the current thread. Returns True if WE initialized it."""
        import threading

        import comtypes

        if not getattr(self._com_initialized, "done", False):
            try:
                comtypes.CoInitialize()
                self._com_initialized.done = True
                self._com_initialized.we_inited = True
                return True
            except Exception:
                # Already initialized by another caller on this thread — safe to use
                self._com_initialized.done = True
                self._com_initialized.we_inited = False
        return False

    def _vol(self):
        """Return the EndpointVolume controller for the default speakers."""
        self._ensure_com()
        from pycaw.pycaw import AudioUtilities

        return AudioUtilities.GetSpeakers().EndpointVolume

    def is_available(self) -> bool:
        """Check if pycaw is installed and an audio endpoint is accessible."""
        try:
            return self._vol() is not None
        except Exception as e:
            logger.debug(f"PyCAWAudioAdapter not available: {e}")
            return False

    def list_devices(self) -> list[dict[str, Any]]:
        devices = []
        try:
            self._ensure_com()
            from pycaw.pycaw import AudioUtilities

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
        except Exception as e:
            logger.error(f"PyCAW list_devices failed: {e}")
        return devices

    def get_default_output(self) -> dict[str, Any] | None:
        devs = self.list_devices()
        return next((d for d in devs if d["type"] == "output"), None)

    def get_default_input(self) -> dict[str, Any] | None:
        devs = self.list_devices()
        return next((d for d in devs if d["type"] == "input"), None)

    def get_volume(self) -> dict[str, Any]:
        try:
            vol = self._vol()
            vol_scalar = vol.GetMasterVolumeLevelScalar()
            muted = bool(vol.GetMute())
            level = round(vol_scalar * 100, 1)
            return {"level": level, "muted": muted, "backend": self.name}
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
            self._vol().SetMasterVolumeLevelScalar(target, None)
            return True
        except Exception as e:
            logger.error(f"PyCAW set_volume failed: {e}")
            return False

    def get_mute(self) -> bool:
        res = self.get_volume()
        return res.get("muted", False)

    def set_mute(self, muted: bool) -> bool:
        try:
            self._vol().SetMute(1 if muted else 0, None)
            return True
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
