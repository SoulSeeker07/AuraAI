"""
SmartHome Capability Provider
=============================
Location: src/core/capabilities/providers/smarthome_provider.py

Provides capability descriptors for the Smart Home subsystem (Home Assistant and Direct Tapo/Kasa integrations).
All capabilities map to verified execution via SmartHomeBackendAdapter.
Gracefully degrades to is_live=False, availability="offline" if neither HA nor Tapo is configured.
"""

from __future__ import annotations

import os
from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk


def _is_smarthome_configured() -> bool:
    """Check if Home Assistant credentials or Tapo credentials are configured in the environment."""
    ha_token = os.getenv("HASS_TOKEN", os.getenv("HA_TOKEN", ""))
    tapo_user = os.getenv("TAPO_USERNAME", "")
    tapo_pass = os.getenv("TAPO_PASSWORD", "")
    return bool((ha_token and ha_token.strip()) or (tapo_user and tapo_pass))


class SmartHomeCapabilityProvider(ICapabilityProvider):
    """Provider for Home Assistant and Tapo smart home devices, lights, switches, fans, cameras, and states."""

    DOMAIN = "smarthome"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = self._build_capabilities()

    @property
    def domain(self) -> str:
        return self.DOMAIN

    def _build_capabilities(self) -> dict[str, Capability]:
        is_live = _is_smarthome_configured()
        availability = "online" if is_live else "offline"

        caps = [
            # 1. Lights
            Capability(
                name="light.turn_on",
                domain=self.DOMAIN,
                description="Turn on a smart light with optional brightness and color settings.",
                category="light",
                input_schema={
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string", "description": "Target entity or bulb IP"},
                        "brightness": {"type": "integer", "minimum": 0, "maximum": 255},
                        "rgb_color": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3},
                        "color_temp": {"type": "integer"},
                        "force_device_poll": {"type": "boolean", "default": False},
                    },
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}, "state": {"type": "object"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "light", "turn_on"],
            ),
            Capability(
                name="light.turn_off",
                domain=self.DOMAIN,
                description="Turn off a smart light.",
                category="light",
                input_schema={
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "force_device_poll": {"type": "boolean", "default": False},
                    },
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}, "state": {"type": "object"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "light", "turn_off"],
            ),
            Capability(
                name="light.toggle",
                domain=self.DOMAIN,
                description="Toggle a smart light state between on and off.",
                category="light",
                input_schema={
                    "type": "object",
                    "properties": {"entity_id": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}, "state": {"type": "object"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "light", "toggle"],
            ),
            Capability(
                name="light.set_brightness",
                domain=self.DOMAIN,
                description="Set brightness level (0-255 or 0-100) for a smart light.",
                category="light",
                input_schema={
                    "type": "object",
                    "required": ["brightness"],
                    "properties": {
                        "entity_id": {"type": "string"},
                        "brightness": {"type": "integer", "minimum": 0, "maximum": 255},
                        "force_device_poll": {"type": "boolean", "default": False},
                    },
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}, "state": {"type": "object"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "light", "brightness"],
            ),
            # 2. Switches
            Capability(
                name="switch.turn_on",
                domain=self.DOMAIN,
                description="Turn on a smart switch or plug.",
                category="switch",
                input_schema={
                    "type": "object",
                    "properties": {"entity_id": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "switch", "turn_on"],
            ),
            Capability(
                name="switch.turn_off",
                domain=self.DOMAIN,
                description="Turn off a smart switch or plug.",
                category="switch",
                input_schema={
                    "type": "object",
                    "properties": {"entity_id": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "switch", "turn_off"],
            ),
            Capability(
                name="switch.toggle",
                domain=self.DOMAIN,
                description="Toggle a smart switch state.",
                category="switch",
                input_schema={
                    "type": "object",
                    "properties": {"entity_id": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "switch", "toggle"],
            ),
            # 3. Fans
            Capability(
                name="fan.turn_on",
                domain=self.DOMAIN,
                description="Turn on a smart fan with optional speed percentage.",
                category="fan",
                input_schema={
                    "type": "object",
                    "required": ["entity_id"],
                    "properties": {
                        "entity_id": {"type": "string"},
                        "percentage": {"type": "integer", "minimum": 0, "maximum": 100},
                    },
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "fan", "turn_on"],
            ),
            Capability(
                name="fan.turn_off",
                domain=self.DOMAIN,
                description="Turn off a smart fan.",
                category="fan",
                input_schema={
                    "type": "object",
                    "required": ["entity_id"],
                    "properties": {"entity_id": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "fan", "turn_off"],
            ),
            Capability(
                name="fan.set_speed",
                domain=self.DOMAIN,
                description="Set the speed percentage (0-100) of a smart fan.",
                category="fan",
                input_schema={
                    "type": "object",
                    "required": ["entity_id", "percentage"],
                    "properties": {
                        "entity_id": {"type": "string"},
                        "percentage": {"type": "integer", "minimum": 0, "maximum": 100},
                    },
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "fan", "speed"],
            ),
            # 4. Entity State Queries & Introspection
            Capability(
                name="entity.get_state",
                domain=self.DOMAIN,
                description="Get current state and attributes for a smart home device or entity.",
                category="introspection",
                input_schema={
                    "type": "object",
                    "properties": {"entity_id": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"state": {"type": "object"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "entity", "state", "read_only"],
            ),
            Capability(
                name="entity.list_all",
                domain=self.DOMAIN,
                description="List all available smart home entities/devices and their current states.",
                category="introspection",
                input_schema={"type": "object", "properties": {"domain_filter": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "entity", "list", "read_only"],
            ),
            Capability(
                name="entity.update_entity",
                domain=self.DOMAIN,
                description="Force a fresh poll of a physical device.",
                category="device_poll",
                input_schema={
                    "type": "object",
                    "properties": {"entity_id": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
                risk_level=ActionRisk.LOW,
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                tags=["smarthome", "entity", "update_entity", "poll"],
            ),
            # 5. Camera (Privacy-Sensitive: ActionRisk.MEDIUM)
            Capability(
                name="camera.get_stream_url",
                domain=self.DOMAIN,
                description="Retrieve live stream / RTSP URL for a camera entity (privacy audited).",
                category="camera",
                input_schema={
                    "type": "object",
                    "required": ["entity_id"],
                    "properties": {"entity_id": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"stream_url": {"type": "string"}}},
                risk_level=ActionRisk.MEDIUM,
                permissions=["camera:stream"],
                execution_backend="smarthome_backend",
                is_live=is_live,
                availability=availability,
                metadata={"privacy_sensitive": True, "requires_audit": True},
                tags=["smarthome", "camera", "stream", "privacy_sensitive"],
            ),
        ]
        return {cap.name: cap for cap in caps}

    def list_capabilities(self) -> list[Capability]:
        return list(self._capabilities.values())

    def get_capability(self, name: str) -> Capability | None:
        return self._capabilities.get(name)
