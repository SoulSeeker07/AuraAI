"""
SmartHome Backend Adapter
=========================
Location: src/core/backends/adapters/smarthome_backend.py

Connects MasterOrchestrator and capability execution to HomeAssistantClient
and direct Tapo / Kasa device control.
Executes smarthome capabilities with verified post-conditions and structured
ExecutionResult.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, Optional

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter
from integrations.smarthome.ha_client import (
    HAConnectionError,
    HAWebSocketClient,
    HomeAssistantClient,
    VerifiedCommandResult,
)
from integrations.smarthome.tapo_client import TapoDirectClient

logger = logging.getLogger("aura.backends.smarthome")


class SmartHomeBackendAdapter(BaseBackendAdapter):
    """Execution backend adapter for Home Assistant and direct Tapo smart home devices."""

    def __init__(
        self,
        client: Optional[HomeAssistantClient] = None,
        tapo_client: Optional[TapoDirectClient] = None,
        base_url: str = "http://127.0.0.1:8123",
        token: str = "",
        event_bus: Any | None = None,
    ) -> None:
        self._custom_client = client
        self._custom_tapo_client = tapo_client
        self._base_url = base_url
        self._token = token
        self._event_bus = event_bus
        self._client_instance: Optional[HomeAssistantClient] = None
        self._tapo_client_instance: Optional[TapoDirectClient] = None
        self._ws_client_instance: Optional[HAWebSocketClient] = None

    @property
    def name(self) -> str:
        return "SmartHome Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "smarthome",
            "smarthome.light.turn_on", "smarthome.light.turn_off", "smarthome.light.toggle",
            "smarthome.light.set_brightness",
            "smarthome.switch.turn_on", "smarthome.switch.turn_off", "smarthome.switch.toggle",
            "smarthome.fan.turn_on", "smarthome.fan.turn_off", "smarthome.fan.set_speed",
            "smarthome.entity.get_state", "smarthome.entity.list_all", "smarthome.entity.update_entity",
            "smarthome.camera.get_stream_url",
            "light.turn_on", "light.turn_off", "light.toggle", "light.set_brightness",
            "switch.turn_on", "switch.turn_off", "switch.toggle",
            "fan.turn_on", "fan.turn_off", "fan.set_speed",
            "entity.get_state", "entity.list_all", "entity.update_entity",
            "camera.get_stream_url",
        ]

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "capabilities": self.capabilities, "latency_ms": 120.0, "cost": 0.0, "is_local": True}

    def health_check(self) -> bool:
        return True

    def _get_client(self) -> Optional[HomeAssistantClient]:
        if self._custom_client is not None:
            return self._custom_client
        if self._client_instance is None:
            from core.settings import Settings
            settings = Settings()
            base_url = settings.ha_url or self._base_url
            token = settings.ha_token or self._token
            if token:
                self._ws_client_instance = HAWebSocketClient(base_url=base_url, token=token, event_bus=self._event_bus)
                self._ws_client_instance.start()
                self._client_instance = HomeAssistantClient(
                    base_url=base_url, token=token, ws_client=self._ws_client_instance, command_timeout_seconds=15.0
                )
        return self._client_instance

    def _get_tapo_client(self) -> TapoDirectClient:
        if self._custom_tapo_client is not None:
            return self._custom_tapo_client
        if self._tapo_client_instance is None:
            self._tapo_client_instance = TapoDirectClient()
        return self._tapo_client_instance

    def execute(self, capability: str, goal: str, arguments: dict[str, Any] | None = None) -> ExecutionResult:
        """Synchronous entrypoint bridging to async loop safely."""
        client = self._get_client()
        ws_loop = self._ws_client_instance.loop if self._ws_client_instance else None

        try:
            asyncio.get_running_loop()
            in_running_loop = True
        except RuntimeError:
            in_running_loop = False

        if not in_running_loop:
            return asyncio.run(self.execute_async(capability, goal, arguments))

        if ws_loop is not None:
            future = asyncio.run_coroutine_threadsafe(
                self.execute_async(capability, goal, arguments), ws_loop
            )
            return future.result()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(asyncio.run, self.execute_async(capability, goal, arguments))
            return fut.result()

    async def execute_async(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        client = self._get_client()
        tapo = self._get_tapo_client()
        args = arguments or {}
        cap = capability.replace("smarthome.", "")
        entity_id = args.get("entity_id", "")
        force_device_poll = bool(args.get("force_device_poll", False))

        # Direct Tapo execution if HA client is absent or if target is a Tapo host
        use_direct_tapo = (client is None and tapo.is_available) or ("tapo" in entity_id.lower() and client is None)

        if use_direct_tapo:
            return await self._execute_direct_tapo(cap, goal, args)

        if client is None:
            if tapo.is_available:
                return await self._execute_direct_tapo(cap, goal, args)
            return ExecutionResult(
                success=False,
                planner="smarthome",
                goal=goal,
                observations=["Neither Home Assistant token (HASS_TOKEN) nor Tapo credentials (TAPO_USERNAME/TAPO_PASSWORD) are configured."],
                data={"error": "unconfigured_smarthome"},
            )

        try:
            if cap == "light.turn_on":
                service_data: dict[str, Any] = {}
                if "brightness" in args:
                    service_data["brightness"] = int(args["brightness"])
                if "rgb_color" in args:
                    service_data["rgb_color"] = args["rgb_color"]
                if "color_temp" in args:
                    service_data["color_temp"] = int(args["color_temp"])
                expected_attrs, tolerances = {}, {}
                if "brightness" in args:
                    expected_attrs["brightness"] = float(args["brightness"])
                    tolerances["brightness"] = 5.0
                res = await client.execute_verified_command(
                    domain="light", service="turn_on", entity_id=entity_id,
                    service_data=service_data or None, expected_state="on",
                    expected_attributes=expected_attrs or None, attribute_tolerances=tolerances or None,
                    force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.turn_off":
                res = await client.execute_verified_command(
                    domain="light", service="turn_off", entity_id=entity_id,
                    expected_state="off", force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.set_brightness":
                brightness = int(args.get("brightness", 255))
                res = await client.execute_verified_command(
                    domain="light", service="turn_on", entity_id=entity_id,
                    service_data={"brightness": brightness}, expected_state="on",
                    expected_attributes={"brightness": float(brightness)}, attribute_tolerances={"brightness": 5.0},
                    force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.set_color":
                color_val = args.get("color")
                res = await client.execute_verified_command(
                    domain="light", service="turn_on", entity_id=entity_id,
                    service_data={"color_name": color_val} if isinstance(color_val, str) else {"rgb_color": color_val},
                    expected_state="on", force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.set_color_temp":
                color_temp_val = int(args.get("color_temp", 2700))
                res = await client.execute_verified_command(
                    domain="light", service="turn_on", entity_id=entity_id,
                    service_data={"color_temp_kelvin": color_temp_val},
                    expected_state="on", force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.set_effect":
                effect_name = str(args.get("effect", "Party"))
                res = await client.execute_verified_command(
                    domain="light", service="turn_on", entity_id=entity_id,
                    service_data={"effect": effect_name},
                    expected_state="on", force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.toggle":
                curr = await client.get_state(entity_id)
                target_state = "off" if curr.get("state") == "on" else "on"
                res = await client.execute_verified_command(
                    domain="light", service="toggle", entity_id=entity_id,
                    expected_state=target_state, force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "switch.turn_on":
                res = await client.execute_verified_command(
                    domain="switch", service="turn_on", entity_id=entity_id,
                    expected_state="on", force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "switch.turn_off":
                res = await client.execute_verified_command(
                    domain="switch", service="turn_off", entity_id=entity_id,
                    expected_state="off", force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "switch.toggle":
                curr = await client.get_state(entity_id)
                target_state = "off" if curr.get("state") == "on" else "on"
                res = await client.execute_verified_command(
                    domain="switch", service="toggle", entity_id=entity_id,
                    expected_state=target_state, force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "fan.turn_on":
                service_data = {}
                if "percentage" in args:
                    service_data["percentage"] = int(args["percentage"])
                res = await client.execute_verified_command(
                    domain="fan", service="turn_on", entity_id=entity_id,
                    service_data=service_data or None, expected_state="on", force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "fan.turn_off":
                res = await client.execute_verified_command(
                    domain="fan", service="turn_off", entity_id=entity_id,
                    expected_state="off", force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "fan.set_speed":
                percentage = int(args.get("percentage", 100))
                res = await client.execute_verified_command(
                    domain="fan", service="set_percentage", entity_id=entity_id,
                    service_data={"percentage": percentage}, expected_state="on",
                    expected_attributes={"percentage": float(percentage)}, attribute_tolerances={"percentage": 2.0},
                    force_device_poll=force_device_poll,
                )
                return self._to_execution_result(res, goal, cap)

            elif cap == "entity.get_state":
                state = await client.get_state(entity_id)
                return ExecutionResult(
                    success=True, planner="smarthome", goal=goal,
                    observations=[f"Fetched state for {entity_id}: {state.get('state')}"],
                    data={"state": state, "entity_id": entity_id},
                )

            elif cap == "entity.list_all":
                states = await client.list_states(domain_filter=args.get("domain_filter"))
                return ExecutionResult(
                    success=True, planner="smarthome", goal=goal,
                    observations=[f"Found {len(states)} entities in Home Assistant"],
                    data={"entities": states, "count": len(states)},
                )

            elif cap == "entity.update_entity":
                await client.force_device_poll(entity_id)
                new_state = await client.get_state(entity_id)
                return ExecutionResult(
                    success=True, planner="smarthome", goal=goal,
                    observations=[f"Forced device poll for {entity_id}, state is now {new_state.get('state')}"],
                    data={"state": new_state, "entity_id": entity_id},
                )

            elif cap == "camera.get_stream_url":
                state = await client.get_state(entity_id)
                attrs = state.get("attributes", {})
                stream_source = attrs.get("stream_source") or attrs.get("rtsp_url")
                if not stream_source:
                    return ExecutionResult(
                        success=False, planner="smarthome", goal=goal,
                        observations=[f"No live stream source exposed for {entity_id}"],
                        data={"entity_id": entity_id, "error": "no_stream_source"},
                    )
                return ExecutionResult(
                    success=True, planner="smarthome", goal=goal,
                    observations=[f"Retrieved camera stream URL for {entity_id}"],
                    data={"stream_url": stream_source, "entity_id": entity_id, "attributes": attrs},
                )

            else:
                return ExecutionResult(
                    success=False, planner="smarthome", goal=goal,
                    observations=[f"Unsupported capability '{capability}' in SmartHomeBackendAdapter"],
                    data={"error": f"Unsupported capability: {capability}"},
                )

        except HAConnectionError as exc:
            logger.error("SmartHome operation %s failed: %s", capability, exc)
            return ExecutionResult(
                success=False, planner="smarthome", goal=goal,
                observations=[f"HA connection error: {exc}"], data={"error": str(exc)},
            )

    async def _execute_direct_tapo(self, cap: str, goal: str, args: dict[str, Any]) -> ExecutionResult:
        """Direct control path using python-kasa without Home Assistant."""
        tapo = self._get_tapo_client()
        host = args.get("host") or args.get("ip") or tapo.default_host

        try:
            if cap in ("light.turn_on", "switch.turn_on"):
                brightness = args.get("brightness")
                res = await tapo.execute_verified_command("turn_on", host=host, brightness=brightness)
                return self._to_execution_result(res, goal, cap)

            elif cap in ("light.turn_off", "switch.turn_off"):
                res = await tapo.execute_verified_command("turn_off", host=host)
                return self._to_execution_result(res, goal, cap)

            elif cap in ("light.toggle", "switch.toggle"):
                res = await tapo.execute_verified_command("toggle", host=host)
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.set_brightness":
                brightness = int(args.get("brightness", 100))
                res = await tapo.execute_verified_command("set_brightness", host=host, brightness=brightness)
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.set_color":
                color_name = args.get("color")
                hsv = args.get("hsv")
                brightness = args.get("brightness")
                res = await tapo.execute_verified_command("set_color", host=host, color=color_name, hsv=hsv, brightness=brightness)
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.set_color_temp":
                color_temp = int(args.get("color_temp", 2700))
                brightness = args.get("brightness")
                res = await tapo.execute_verified_command("set_color_temp", host=host, color_temp=color_temp, brightness=brightness)
                return self._to_execution_result(res, goal, cap)

            elif cap == "light.set_effect":
                effect_name = str(args.get("effect", "Party"))
                brightness = args.get("brightness")
                res = await tapo.execute_verified_command("set_effect", host=host, effect=effect_name, brightness=brightness)
                return self._to_execution_result(res, goal, cap)

            elif cap == "entity.get_state":
                state = await tapo.get_state(host=host)
                return ExecutionResult(
                    success=True, planner="smarthome", goal=goal,
                    observations=[f"Fetched direct Tapo state for {state['alias']}: {state['state']}"],
                    data={"state": state, "entity_id": state["entity_id"]},
                )

            elif cap == "entity.list_all":
                devices = await tapo.list_devices()
                return ExecutionResult(
                    success=True, planner="smarthome", goal=goal,
                    observations=[f"Found {len(devices)} Tapo devices on LAN"],
                    data={"entities": devices, "count": len(devices)},
                )

            else:
                return ExecutionResult(
                    success=False, planner="smarthome", goal=goal,
                    observations=[f"Direct Tapo does not support '{cap}'"],
                    data={"error": f"unsupported_direct_tapo_capability: {cap}"},
                )
        except Exception as exc:
            logger.error("Direct Tapo operation %s failed: %s", cap, exc)
            return ExecutionResult(
                success=False, planner="smarthome", goal=goal,
                observations=[f"Direct Tapo connection error: {exc}"], data={"error": str(exc)},
            )

    def _to_execution_result(self, result: VerifiedCommandResult, goal: str, capability: str) -> ExecutionResult:
        return ExecutionResult(
            success=result.success, planner="smarthome", goal=goal,
            observations=[
                f"SmartHome {capability} on {result.entity_id}: "
                f"{'SUCCESS' if result.success else 'FAILED'} "
                f"(confidence: {result.verification_confidence}, attempts: {result.attempts})"
            ],
            warnings=[result.error] if result.error and not result.success else [],
            data={
                "entity_id": result.entity_id, "state": result.state,
                "verification_confidence": result.verification_confidence,
                "attempts": result.attempts, "error": result.error,
            },
        )
