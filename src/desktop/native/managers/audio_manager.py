"""
Audio Manager for Native Windows Layer

Manages Windows audio operations (volume, mute, audio endpoints) via AudioAdapter abstraction.
All cross-cutting concerns (permissions, verification, rollback, diagnostics) are
handled by the execution pipeline.

This manager ONLY contains Windows-specific code via AudioAdapters.
"""

import logging
from typing import Any

from ..adapters.audio_adapter import AudioAdapter, AudioAdapterFactory
from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class AudioManager(BaseNativeManager):
    """
    Manages Windows audio operations using AudioAdapter abstraction.

    Capabilities:
    - audio.list_devices / list_audio_devices: List connected audio devices
    - audio.default_device / get_default_audio_device: Get default output audio device
    - audio.volume / get_volume: Get master volume level and mute state
    - audio.is_muted / is_muted: Check if audio is muted
    - audio.microphones / list_microphones: List input microphone devices
    - audio.set_volume / set_volume: Set master volume level (0-100)
    - audio.toggle_mute / toggle_mute: Mute or unmute audio
    - audio.set_default_output: Set default audio output endpoint
    """

    NAME = "audio"
    VERSION = "1.0"
    PRIORITY = 20
    DEPENDENCIES = ["pycaw", "comtypes"]

    def __init__(self, adapter: AudioAdapter | None = None):
        """Initialize audio manager with optional injected adapter."""
        super().__init__()
        self._adapter = adapter

    @property
    def adapter(self) -> AudioAdapter:
        """Get or initialize active audio adapter."""
        if self._adapter is None:
            self._adapter = AudioAdapterFactory.get_adapter()
        return self._adapter

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by AudioManager."""
        return [
            "list_audio_devices",
            "get_default_audio_device",
            "get_volume",
            "is_muted",
            "list_microphones",
            "set_volume",
            "toggle_mute",
            "set_default_output",
            "audio.list_devices",
            "audio.default_device",
            "audio.volume",
            "audio.is_muted",
            "audio.microphones",
            "audio.set_volume",
            "audio.toggle_mute",
            "audio.set_default_output",
        ]

    def health_check(self) -> HealthCheckResult:
        """
        Perform health check on AudioManager and its active adapter.

        Returns:
            HealthCheckResult with adapter status and fallback diagnostics.
        """
        active_adapter = self.adapter
        missing = []
        if active_adapter.name != "pycaw":
            missing.append("pycaw")

        status = (
            HealthStatus.HEALTHY
            if active_adapter.name == "pycaw"
            else HealthStatus.DEGRADED
        )

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=[active_adapter.name],
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={"active_adapter": active_adapter.name},
        )

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs,
    ) -> DesktopResult:
        """
        Execute native audio operation for the given capability.

        Returns:
            DesktopResult with execution data or failure message.
        """
        arguments = arguments or {}
        arguments.update(kwargs)

        try:
            logger.info(f"AudioManager executing capability: {capability}")
            cap_clean = capability.lower()

            if cap_clean in ("list_audio_devices", "audio.list_devices"):
                return self._handle_list_devices(goal=goal, capability=capability)

            elif cap_clean in ("get_default_audio_device", "audio.default_device"):
                return self._handle_get_default_device(goal=goal, capability=capability)

            elif cap_clean in ("get_volume", "audio.volume"):
                return self._handle_get_volume(goal=goal, capability=capability)

            elif cap_clean in ("is_muted", "audio.is_muted"):
                return self._handle_is_muted(goal=goal, capability=capability)

            elif cap_clean in ("list_microphones", "audio.microphones"):
                return self._handle_list_microphones(goal=goal, capability=capability)

            elif cap_clean in ("set_volume", "audio.set_volume"):
                return self._handle_set_volume(
                    goal=goal, capability=capability, arguments=arguments
                )

            elif cap_clean in ("toggle_mute", "audio.toggle_mute"):
                return self._handle_toggle_mute(
                    goal=goal, capability=capability, arguments=arguments
                )

            elif cap_clean in ("set_default_output", "audio.set_default_output"):
                return self._handle_set_default_output(
                    goal=goal, capability=capability, arguments=arguments
                )

            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Capability '{capability}' not supported by AudioManager",
                )

        except Exception as e:
            logger.error(f"AudioManager execution failed: {e}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error=str(e)
            )

    # ==================== Handler Implementations ====================

    def _handle_list_devices(self, goal: str, capability: str) -> DesktopResult:
        devices = self.adapter.list_devices()
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "devices": devices,
                "count": len(devices),
                "backend": self.adapter.name,
            },
            events=["audio_devices_listed"],
        )

    def _handle_get_default_device(self, goal: str, capability: str) -> DesktopResult:
        dev = self.adapter.get_default_output()
        if not dev:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="No default output audio device found",
            )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={"default_device": dev, "backend": self.adapter.name},
        )

    def _handle_get_volume(self, goal: str, capability: str) -> DesktopResult:
        vol_data = self.adapter.get_volume()
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=vol_data,
        )

    def _handle_is_muted(self, goal: str, capability: str) -> DesktopResult:
        muted = self.adapter.get_mute()
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={"muted": muted, "backend": self.adapter.name},
        )

    def _handle_list_microphones(self, goal: str, capability: str) -> DesktopResult:
        devices = self.adapter.list_devices()
        mics = [d for d in devices if d.get("type") == "input"]
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "microphones": mics,
                "count": len(mics),
                "backend": self.adapter.name,
            },
        )

    def _handle_set_volume(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        level = arguments.get("level") or arguments.get("volume")
        if level is None:
            level = 50.0

        ok = self.adapter.set_volume(float(level))
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={"level": float(level), "backend": self.adapter.name},
                events=["volume_changed"],
            )
        else:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Failed to set volume",
            )

    def _handle_toggle_mute(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        mute_arg = arguments.get("mute")
        if mute_arg is None:
            current_mute = self.adapter.get_mute()
            target_mute = not current_mute
        else:
            target_mute = bool(mute_arg)

        ok = self.adapter.set_mute(target_mute)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={"muted": target_mute, "backend": self.adapter.name},
                events=["mute_toggled"],
            )
        else:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Failed to toggle mute",
            )

    def _handle_set_default_output(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        device_id = arguments.get("device_id")
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "device_id": device_id,
                "status": "selected",
                "backend": self.adapter.name,
            },
        )
