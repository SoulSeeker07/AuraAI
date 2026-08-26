"""
Unit tests for SmartHomeCapabilityProvider and SmartHomeBackendAdapter.
Fully offline: exercises capability descriptors, risk tiers, service translation, loop bridging, and execution adapter paths.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.backends.adapters.smarthome_backend import SmartHomeBackendAdapter
from core.capabilities.providers.smarthome_provider import SmartHomeCapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk
from integrations.smarthome.ha_client import (
    HAWebSocketClient,
    HomeAssistantClient,
    VerifiedCommandResult,
)


def test_smarthome_capability_provider_offline_graceful_degradation(monkeypatch):
    monkeypatch.delenv("HASS_TOKEN", raising=False)
    monkeypatch.delenv("HA_TOKEN", raising=False)
    monkeypatch.delenv("TAPO_USERNAME", raising=False)
    monkeypatch.delenv("TAPO_PASSWORD", raising=False)

    provider = SmartHomeCapabilityProvider()
    assert provider.domain == "smarthome"

    caps = provider.list_capabilities()
    assert len(caps) >= 12
    # Degrades gracefully to offline when no token is present without crashing registry
    for cap in caps:
        assert cap.is_live is False
        assert cap.availability == "offline"


def test_smarthome_capability_provider_online_when_token_configured(monkeypatch):
    monkeypatch.setenv("HASS_TOKEN", "fake_live_token")

    provider = SmartHomeCapabilityProvider()
    caps = provider.list_capabilities()
    for cap in caps:
        assert cap.is_live is True
        assert cap.availability == "online"

    # Check light capabilities
    turn_on = provider.get_capability("light.turn_on")
    assert turn_on is not None
    assert turn_on.risk_level == ActionRisk.LOW
    assert turn_on.execution_backend == "smarthome_backend"

    # Check camera privacy tier
    camera = provider.get_capability("camera.get_stream_url")
    assert camera is not None
    assert camera.risk_level == ActionRisk.MEDIUM
    assert camera.metadata.get("privacy_sensitive") is True


@pytest.mark.asyncio
async def test_smarthome_backend_adapter_execute_light_turn_on(monkeypatch):
    ws = HAWebSocketClient("http://localhost:8123", "tok")
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    service_calls = []

    async def fake_execute_verified_command(
        domain, service, entity_id, expected_state=None, expected_attributes=None,
        attribute_tolerances=None, service_data=None, force_device_poll=False,
        fast_path_timeout=3.0, allow_retry=True
    ):
        service_calls.append((domain, service, entity_id, service_data, force_device_poll))
        return VerifiedCommandResult(
            success=True,
            entity_id="light.bedroom",
            state={"state": "on", "attributes": {"brightness": 200}},
            verification_confidence="ha_reported",
            attempts=1,
        )

    monkeypatch.setattr(client, "execute_verified_command", fake_execute_verified_command)

    adapter = SmartHomeBackendAdapter(client=client)
    res = await adapter.execute_async(
        capability="smarthome.light.turn_on",
        goal="Turn on bedroom light",
        arguments={"entity_id": "light.bedroom", "brightness": 200},
    )

    assert res.success is True
    assert res.planner == "smarthome"
    assert res.data["verification_confidence"] == "ha_reported"
    assert res.data["entity_id"] == "light.bedroom"
    assert "ha_reported" in res.observations[0]
    assert service_calls[0] == ("light", "turn_on", "light.bedroom", {"brightness": 200}, False)


@pytest.mark.asyncio
async def test_smarthome_backend_service_translation_brightness_and_fan_speed(monkeypatch):
    """Confirm that light.set_brightness and fan.set_speed map to valid HA service names."""
    ws = HAWebSocketClient("http://localhost:8123", "tok")
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    dispatched_calls: list[dict[str, Any]] = []

    async def fake_execute_verified_command(
        domain, service, entity_id, expected_state=None, expected_attributes=None,
        attribute_tolerances=None, service_data=None, force_device_poll=False,
        fast_path_timeout=3.0, allow_retry=True
    ):
        dispatched_calls.append({
            "domain": domain, "service": service, "entity_id": entity_id,
            "service_data": service_data, "force_device_poll": force_device_poll,
        })
        return VerifiedCommandResult(
            success=True,
            entity_id=entity_id,
            state={"state": "on"},
            verification_confidence="device_polled" if force_device_poll else "ha_reported",
            attempts=1,
        )

    monkeypatch.setattr(client, "execute_verified_command", fake_execute_verified_command)
    adapter = SmartHomeBackendAdapter(client=client)

    # 1. Test light.set_brightness translates to domain="light", service="turn_on"
    await adapter.execute_async(
        capability="smarthome.light.set_brightness",
        goal="Set desk light brightness",
        arguments={"entity_id": "light.desk", "brightness": 128, "force_device_poll": True},
    )
    assert dispatched_calls[-1]["domain"] == "light"
    assert dispatched_calls[-1]["service"] == "turn_on"
    assert dispatched_calls[-1]["service_data"] == {"brightness": 128}
    assert dispatched_calls[-1]["force_device_poll"] is True

    # 2. Test fan.set_speed translates to domain="fan", service="set_percentage"
    await adapter.execute_async(
        capability="smarthome.fan.set_speed",
        goal="Set ceiling fan speed",
        arguments={"entity_id": "fan.ceiling", "percentage": 75},
    )
    assert dispatched_calls[-1]["domain"] == "fan"
    assert dispatched_calls[-1]["service"] == "set_percentage"
    assert dispatched_calls[-1]["service_data"] == {"percentage": 75}


@pytest.mark.asyncio
async def test_smarthome_backend_list_all_and_camera_stream(monkeypatch):
    ws = HAWebSocketClient("http://localhost:8123", "tok")
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    async def fake_list_states(domain_filter=None):
        return [{"entity_id": "light.desk", "state": "on"}, {"entity_id": "fan.ceiling", "state": "off"}]

    async def fake_get_state(entity_id):
        if entity_id == "camera.backyard":
            return {"entity_id": entity_id, "state": "idle", "attributes": {"stream_source": "rtsp://192.168.1.100:554/live"}}
        return {"entity_id": entity_id, "state": "idle", "attributes": {"entity_picture": "/api/camera_proxy/cam.jpg"}}

    monkeypatch.setattr(client, "list_states", fake_list_states)
    monkeypatch.setattr(client, "get_state", fake_get_state)

    adapter = SmartHomeBackendAdapter(client=client)

    # 1. Test entity.list_all
    list_res = await adapter.execute_async("smarthome.entity.list_all", "List entities")
    assert list_res.success is True
    assert list_res.data["count"] == 2

    # 2. Test camera with real stream source
    cam_res = await adapter.execute_async("camera.get_stream_url", "Get stream", {"entity_id": "camera.backyard"})
    assert cam_res.success is True
    assert cam_res.data["stream_url"] == "rtsp://192.168.1.100:554/live"

    # 3. Test camera without stream source (only static snapshot) -> fails safely, no silent false claim
    no_stream_res = await adapter.execute_async("camera.get_stream_url", "Get stream", {"entity_id": "camera.static_only"})
    assert no_stream_res.success is False
    assert no_stream_res.data["error"] == "no_stream_source"
