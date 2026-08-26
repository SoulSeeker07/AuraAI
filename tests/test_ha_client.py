"""
Unit tests for the smarthome HA client. These run fully offline: no real
HTTP or WebSocket connection is made. HomeAssistantClient's REST calls are
monkeypatched at the method level; HAWebSocketClient's waiter registry and
message handling are exercised directly, since they don't require an active
socket to function.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from integrations.smarthome.ha_client import (  # noqa: E402
    HAConnectionError,
    HAWebSocketClient,
    HomeAssistantClient,
    VerifiedCommandResult,
    state_matches,
)


# ---------------------------------------------------------------------------
# state_matches
# ---------------------------------------------------------------------------

def test_state_matches_simple_state_equality():
    assert state_matches({"state": "on"}, expected_state="on") is True
    assert state_matches({"state": "off"}, expected_state="on") is False


def test_state_matches_numeric_tolerance():
    state = {"state": "on", "attributes": {"brightness": 198}}
    # Exact match required, no tolerance given -> fails on off-by-two
    assert state_matches(state, "on", {"brightness": 200}, {}) is False
    # Tolerance of 5 -> passes
    assert state_matches(state, "on", {"brightness": 200}, {"brightness": 5}) is True


def test_state_matches_missing_attribute_fails():
    state = {"state": "on", "attributes": {}}
    assert state_matches(state, "on", {"brightness": 200}, {"brightness": 5}) is False


# ---------------------------------------------------------------------------
# HAWebSocketClient: waiter registration, cleanup, and message dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_state_waiter_resolves_on_matching_event():
    ws = HAWebSocketClient("http://localhost:8123", "fake-token")

    waiter = asyncio.ensure_future(
        ws.register_state_waiter("light.bulb", lambda s: s.get("state") == "on", timeout=2.0)
    )
    await asyncio.sleep(0.05)  # let the waiter register before the event arrives

    await ws._handle_message(
        {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {"entity_id": "light.bulb", "new_state": {"state": "on"}},
            },
        }
    )

    result = await waiter
    assert result == {"state": "on"}
    # Cleanup: no dangling waiter entries left behind.
    assert ws._state_waiters == {}


@pytest.mark.asyncio
async def test_register_state_waiter_ignores_non_matching_event_then_times_out():
    ws = HAWebSocketClient("http://localhost:8123", "fake-token")

    waiter = asyncio.ensure_future(
        ws.register_state_waiter("light.bulb", lambda s: s.get("state") == "on", timeout=0.2)
    )
    await asyncio.sleep(0.05)

    await ws._handle_message(
        {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {"entity_id": "light.bulb", "new_state": {"state": "off"}},
            },
        }
    )

    with pytest.raises(asyncio.TimeoutError):
        await waiter

    # Even on timeout, the waiter table must be cleaned up (no leak).
    assert ws._state_waiters == {}


@pytest.mark.asyncio
async def test_waiter_table_cleaned_up_even_with_multiple_concurrent_waiters():
    ws = HAWebSocketClient("http://localhost:8123", "fake-token")

    w1 = asyncio.ensure_future(
        ws.register_state_waiter("light.bulb", lambda s: s.get("state") == "on", timeout=0.2)
    )
    w2 = asyncio.ensure_future(
        ws.register_state_waiter("light.bulb", lambda s: s.get("state") == "off", timeout=2.0)
    )
    await asyncio.sleep(0.05)

    # Resolves only w2; w1 should independently time out and clean itself up.
    await ws._handle_message(
        {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {"entity_id": "light.bulb", "new_state": {"state": "off"}},
            },
        }
    )

    with pytest.raises(asyncio.TimeoutError):
        await w1
    result = await w2
    assert result == {"state": "off"}

    assert ws._state_waiters == {}


@pytest.mark.asyncio
async def test_handle_message_publishes_to_event_bus():
    published: list[tuple[str, dict[str, Any]]] = []

    class FakeEventBus:
        def publish(self, event_name: str, **payload: Any) -> None:
            published.append((event_name, payload))

    ws = HAWebSocketClient("http://localhost:8123", "fake-token", event_bus=FakeEventBus())

    await ws._handle_message(
        {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {"entity_id": "light.bulb", "new_state": {"state": "on"}},
            },
        }
    )

    assert published == [("ha.state_changed", {"entity_id": "light.bulb", "new_state": {"state": "on"}})]


@pytest.mark.asyncio
async def test_handle_message_survives_broken_event_bus_subscriber():
    class BrokenEventBus:
        def publish(self, event_name: str, **payload: Any) -> None:
            raise RuntimeError("subscriber exploded")

    ws = HAWebSocketClient("http://localhost:8123", "fake-token", event_bus=BrokenEventBus())

    # Must not raise -- a broken subscriber must not kill the WS message loop.
    await ws._handle_message(
        {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {"entity_id": "light.bulb", "new_state": {"state": "on"}},
            },
        }
    )


# ---------------------------------------------------------------------------
# HomeAssistantClient: timeout safety-margin enforcement
# ---------------------------------------------------------------------------

def test_command_timeout_must_exceed_ha_internal_timeout():
    ws = HAWebSocketClient("http://localhost:8123", "fake-token")
    with pytest.raises(ValueError):
        HomeAssistantClient("http://localhost:8123", "fake-token", ws, command_timeout_seconds=10.0)
    with pytest.raises(ValueError):
        HomeAssistantClient("http://localhost:8123", "fake-token", ws, command_timeout_seconds=5.0)
    # Should not raise:
    HomeAssistantClient("http://localhost:8123", "fake-token", ws, command_timeout_seconds=15.0)


# ---------------------------------------------------------------------------
# HomeAssistantClient.execute_verified_command: the Execute -> Verify -> Report loop
# ---------------------------------------------------------------------------

class StubWSClient(HAWebSocketClient):
    """A waiter registry with no real network -- lets tests control exactly
    when (or whether) a matching state_changed event 'arrives'."""

    def __init__(self, resolve_after: float | None = None, resolved_state: dict | None = None):
        super().__init__("http://localhost:8123", "fake-token")
        self._resolve_after = resolve_after
        self._resolved_state = resolved_state

    async def register_state_waiter(self, entity_id, predicate, timeout=3.0):
        if self._resolve_after is not None and self._resolve_after < timeout:
            await asyncio.sleep(self._resolve_after)
            if predicate(self._resolved_state):
                return self._resolved_state
        await asyncio.sleep(timeout)
        raise asyncio.TimeoutError()


@pytest.mark.asyncio
async def test_execute_verified_command_fast_path_success(monkeypatch):
    ws = StubWSClient()
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    async def fake_call_service(domain, service, entity_id, service_data=None):
        return [{"entity_id": entity_id, "state": "on", "attributes": {}}]

    monkeypatch.setattr(client, "call_service", fake_call_service)

    result = await client.execute_verified_command(
        "light", "turn_on", "light.bulb", expected_state="on"
    )
    assert result.success is True
    assert result.verification_confidence == "ha_reported"
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_execute_verified_command_falls_back_to_ws_waiter(monkeypatch):
    # REST response doesn't include our entity (edge case per HA docs), but the
    # WS event arrives shortly after.
    ws = StubWSClient(resolve_after=0.1, resolved_state={"entity_id": "light.bulb", "state": "on"})
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    async def fake_call_service(domain, service, entity_id, service_data=None):
        return []  # nothing in the fast-path array

    monkeypatch.setattr(client, "call_service", fake_call_service)

    result = await client.execute_verified_command(
        "light", "turn_on", "light.bulb", expected_state="on", fast_path_timeout=1.0
    )
    assert result.success is True
    assert result.verification_confidence == "ha_reported"


@pytest.mark.asyncio
async def test_execute_verified_command_falls_back_to_poll_with_device_poll(monkeypatch):
    ws = StubWSClient()  # never resolves -> always times out
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    forced_poll_calls: list[str] = []

    async def fake_call_service(domain, service, entity_id, service_data=None):
        if domain == "homeassistant" and service == "update_entity":
            forced_poll_calls.append(entity_id)
            return []
        return []  # main service call: nothing in fast-path array

    async def fake_get_state(entity_id):
        return {"entity_id": entity_id, "state": "on", "attributes": {}}

    monkeypatch.setattr(client, "call_service", fake_call_service)
    monkeypatch.setattr(client, "get_state", fake_get_state)

    result = await client.execute_verified_command(
        "light",
        "turn_on",
        "light.bulb",
        expected_state="on",
        force_device_poll=True,
        fast_path_timeout=0.1,
    )
    assert result.success is True
    assert result.verification_confidence == "device_polled"
    assert forced_poll_calls == ["light.bulb"]


@pytest.mark.asyncio
async def test_execute_verified_command_retries_once_then_fails(monkeypatch):
    ws = StubWSClient()  # never resolves
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    call_count = {"n": 0}

    async def fake_call_service(domain, service, entity_id, service_data=None):
        call_count["n"] += 1
        return []

    async def fake_get_state(entity_id):
        # Device stubbornly reports "off" no matter how many times we ask.
        return {"entity_id": entity_id, "state": "off", "attributes": {}}

    monkeypatch.setattr(client, "call_service", fake_call_service)
    monkeypatch.setattr(client, "get_state", fake_get_state)

    result = await client.execute_verified_command(
        "light", "turn_on", "light.bulb", expected_state="on", fast_path_timeout=0.05
    )
    assert result.success is False
    assert result.attempts == 2  # exactly one retry, never more
    assert "Post-condition failed" in result.error
    # Two attempts, each calling the domain.service once (update_entity not requested here).
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_execute_verified_command_actually_forwards_service_data(monkeypatch):
    """Regression test: service_data (the real command payload, e.g. brightness)
    must reach call_service. This is the exact gap that let smarthome_backend.py
    call a keyword argument (`service_data=`) that execute_verified_command
    didn't accept -- invisible in smarthome_backend's own tests because they
    monkeypatch execute_verified_command itself with a **kwargs fake that
    silently accepts any signature.
    """
    ws = StubWSClient()
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    received_calls: list[tuple] = []

    async def fake_call_service(domain, service, entity_id, service_data=None):
        received_calls.append((domain, service, entity_id, service_data))
        return [{"entity_id": entity_id, "state": "on", "attributes": {"brightness": 200}}]

    monkeypatch.setattr(client, "call_service", fake_call_service)

    result = await client.execute_verified_command(
        "light",
        "turn_on",
        "light.bulb",
        expected_state="on",
        expected_attributes={"brightness": 200},
        attribute_tolerances={"brightness": 5},
        service_data={"brightness": 200},
    )

    assert result.success is True
    assert received_calls[0] == ("light", "turn_on", "light.bulb", {"brightness": 200})


@pytest.mark.asyncio
async def test_list_states_returns_all_entities(monkeypatch):
    client = HomeAssistantClient(
        "http://localhost:8123", "tok", StubWSClient(), command_timeout_seconds=15.0
    )

    async def fake_get_session():
        class FakeResp:
            status = 200

            async def json(self):
                return [
                    {"entity_id": "light.bulb", "state": "on"},
                    {"entity_id": "fan.ceiling", "state": "off"},
                    {"entity_id": "light.desk", "state": "off"},
                ]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        class FakeSession:
            def get(self, url):
                return FakeResp()

        return FakeSession()

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    all_states = await client.list_states()
    assert len(all_states) == 3

    lights_only = await client.list_states(domain_filter="light")
    assert len(lights_only) == 2
    assert all(s["entity_id"].startswith("light.") for s in lights_only)


@pytest.mark.asyncio
async def test_execute_verified_command_rest_error_reports_unverified(monkeypatch):
    ws = StubWSClient()
    client = HomeAssistantClient("http://localhost:8123", "tok", ws, command_timeout_seconds=15.0)

    async def fake_call_service(domain, service, entity_id, service_data=None):
        raise HAConnectionError("HA unreachable")

    monkeypatch.setattr(client, "call_service", fake_call_service)

    result = await client.execute_verified_command("light", "turn_on", "light.bulb", expected_state="on")
    assert result.success is False
    assert result.verification_confidence == "unverified"
    assert "HA unreachable" in result.error
