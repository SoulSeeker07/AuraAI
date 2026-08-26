"""
Home Assistant integration client for AuraAI's smarthome capability domain.

Provides:
- HAWebSocketClient: a single persistent WebSocket connection to HA's event
  stream, with automatic reconnect/backoff and a leak-free state-change
  waiter registry used for command verification.
- HomeAssistantClient: REST client for service calls and state queries, with
  a bounded Execute -> Verify -> Report loop (execute_verified_command).

Ground-truth note
------------------
HA's REST service-call response and its `state_changed` WebSocket events both
reflect *Home Assistant's* view of the entity, not a guaranteed fresh read
from the physical device. Polling-based integrations (e.g. TP-Link Tapo)
commonly report an *optimistic* state immediately after a command and only
reconcile with the device on the next poll cycle. Callers that need real
hardware confirmation should pass force_device_poll=True, which calls
`homeassistant.update_entity` before the final state read. Results are
tagged with `verification_confidence` ("ha_reported" | "device_polled" |
"unverified") so this distinction is never silently lost downstream.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

import aiohttp

logger = logging.getLogger("aura.integrations.smarthome.ha_client")


class HAConnectionError(Exception):
    """Raised when the Home Assistant REST or WebSocket API is unreachable or rejects auth."""


@dataclass
class VerifiedCommandResult:
    success: bool
    entity_id: str
    state: Optional[dict[str, Any]]
    verification_confidence: str  # "ha_reported" | "device_polled" | "unverified"
    attempts: int
    error: Optional[str] = None


def state_matches(
    state_obj: dict[str, Any],
    expected_state: Optional[str],
    expected_attributes: Optional[dict[str, float]] = None,
    attribute_tolerances: Optional[dict[str, float]] = None,
) -> bool:
    """Compare an HA state object against an expected state/attributes.

    Numeric attributes (brightness, color_temp, etc.) use a tolerance rather
    than exact equality, since devices commonly round or clamp requested
    values before reporting them back.
    """
    if expected_state is not None and state_obj.get("state") != expected_state:
        return False
    if expected_attributes:
        actual_attrs = state_obj.get("attributes", {})
        tolerances = attribute_tolerances or {}
        for key, expected_val in expected_attributes.items():
            actual_val = actual_attrs.get(key)
            if actual_val is None:
                return False
            tol = tolerances.get(key, 0)
            if tol:
                if abs(float(actual_val) - float(expected_val)) > tol:
                    return False
            elif actual_val != expected_val:
                return False
    return True


class HAWebSocketClient:
    """Persistent, reconnecting WebSocket client for HA's event stream.

    Run exactly one instance of this per HA instance for the life of the
    application. Callers needing to wait on a state change should use
    `register_state_waiter`, not open their own subscription.
    """

    def __init__(self, base_url: str, token: str, event_bus: Any | None = None) -> None:
        self._ws_url = (
            base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
            + "/api/websocket"
        )
        self._token = token
        self._event_bus = event_bus
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stopping = False
        self._connected = asyncio.Event()
        self._msg_id = 0
        self._waiter_lock = asyncio.Lock()
        self._state_waiters: dict[str, list[tuple[asyncio.Future, Callable[[dict], bool]]]] = {}

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """The event loop this client's background task and all its pending
        waiter Futures actually live on. Callers bridging from synchronous
        code or another thread MUST target this loop (e.g. via
        asyncio.run_coroutine_threadsafe) rather than spinning up a new one --
        Futures cannot be safely resolved across event loops/threads."""
        return self._loop

    def start(self) -> None:
        """Start the background connect/listen/reconnect loop. Idempotent.
        Must be called from within the event loop this client should live on.
        """
        if self._task is None or self._task.done():
            self._stopping = False
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.create_task(self._run(), name="ha-ws-client")

    async def stop(self) -> None:
        self._stopping = True
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._session is not None and not self._session.closed:
            await self._session.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        async with self._waiter_lock:
            for waiters in self._state_waiters.values():
                for future, _ in waiters:
                    if not future.done():
                        future.set_exception(HAConnectionError("HA WebSocket client stopped"))
            self._state_waiters.clear()

    async def _run(self) -> None:
        backoff = 1.0
        while not self._stopping:
            try:
                await self._connect_and_listen()
                backoff = 1.0  # reset after a clean session
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - any failure here means "reconnect"
                logger.warning("HA WebSocket connection lost: %s. Reconnecting in %.1fs", exc, backoff)
            self._connected.clear()
            if self._stopping:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    async def _connect_and_listen(self) -> None:
        self._session = aiohttp.ClientSession()
        async with self._session.ws_connect(self._ws_url, heartbeat=30) as ws:
            self._ws = ws
            await self._authenticate(ws)
            await self._subscribe_state_changed(ws)
            self._connected.set()
            logger.info("HA WebSocket connected and subscribed to state_changed")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(json.loads(msg.data))
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                    break
        self._connected.clear()

    async def _authenticate(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        first = json.loads((await ws.receive()).data)
        if first.get("type") != "auth_required":
            raise HAConnectionError(f"Unexpected first WS message: {first}")
        await ws.send_json({"type": "auth", "access_token": self._token})
        resp = json.loads((await ws.receive()).data)
        if resp.get("type") != "auth_ok":
            raise HAConnectionError(f"HA WebSocket auth failed: {resp}")

    async def _subscribe_state_changed(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._msg_id += 1
        await ws.send_json({"id": self._msg_id, "type": "subscribe_events", "event_type": "state_changed"})
        resp = json.loads((await ws.receive()).data)
        if not resp.get("success", False):
            raise HAConnectionError(f"Failed to subscribe to state_changed: {resp}")

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        """Exposed as a coroutine (rather than folded into the read loop) so tests
        can drive it directly without a real socket."""
        if msg.get("type") != "event":
            return
        event = msg.get("event", {})
        if event.get("event_type") != "state_changed":
            return
        data = event.get("data", {})
        entity_id = data.get("entity_id")
        new_state = data.get("new_state")
        if entity_id is None or new_state is None:
            return

        if self._event_bus is not None:
            try:
                self._event_bus.publish("ha.state_changed", entity_id=entity_id, new_state=new_state)
            except Exception:  # noqa: BLE001 - a broken subscriber must not kill the WS loop
                logger.exception("EventBus subscriber raised while handling ha.state_changed")

        async with self._waiter_lock:
            waiters = list(self._state_waiters.get(entity_id, []))
        for future, predicate in waiters:
            if future.done():
                continue
            try:
                if predicate(new_state):
                    future.set_result(new_state)
            except Exception:  # noqa: BLE001 - a bad predicate must not crash the listener
                logger.exception("State waiter predicate raised for %s", entity_id)

    async def register_state_waiter(
        self,
        entity_id: str,
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float = 3.0,
    ) -> dict[str, Any]:
        """Wait up to `timeout` seconds for a state_changed event on entity_id
        whose new_state satisfies `predicate`.

        Raises asyncio.TimeoutError on timeout. Always removes its own entry
        from the waiter table on every exit path (success, timeout, or
        cancellation) to prevent unbounded growth of `_state_waiters`.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        async with self._waiter_lock:
            self._state_waiters.setdefault(entity_id, []).append((future, predicate))

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            async with self._waiter_lock:
                if entity_id in self._state_waiters:
                    self._state_waiters[entity_id] = [
                        (f, p) for (f, p) in self._state_waiters[entity_id] if f is not future
                    ]
                    if not self._state_waiters[entity_id]:
                        del self._state_waiters[entity_id]


class HomeAssistantClient:
    """REST client for Home Assistant with a bounded Execute -> Verify -> Report loop.

    HA's own POST /api/services/<domain>/<service> call blocks server-side for
    up to HA_INTERNAL_SERVICE_TIMEOUT seconds and returns the list of entity
    states that changed during execution. This client's HTTP timeout must
    exceed that with a safety margin, or the client can time out its own
    request right as HA is about to return a valid answer -- enforced in
    __init__, not left as a config footgun.
    """

    HA_INTERNAL_SERVICE_TIMEOUT = 10.0  # HA's own server-side cap; not configurable by us

    def __init__(
        self,
        base_url: str,
        token: str,
        ws_client: HAWebSocketClient,
        session: Optional[aiohttp.ClientSession] = None,
        command_timeout_seconds: float = 15.0,
        verify_device_poll_default: bool = False,
    ) -> None:
        if command_timeout_seconds <= self.HA_INTERNAL_SERVICE_TIMEOUT:
            raise ValueError(
                f"command_timeout_seconds ({command_timeout_seconds}) must exceed HA's own "
                f"{self.HA_INTERNAL_SERVICE_TIMEOUT}s internal service-call timeout, or requests "
                "can be cut off right as HA is about to respond."
            )
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._ws_client = ws_client
        self._session = session
        self._command_timeout = command_timeout_seconds
        self._verify_device_poll_default = verify_device_poll_default

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def call_service(
        self, domain: str, service: str, entity_id: str, service_data: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Call a HA service. Returns the list of changed state objects HA reports."""
        session = await self._get_session()
        payload = {"entity_id": entity_id, **(service_data or {})}
        url = f"{self._base_url}/api/services/{domain}/{service}"
        timeout = aiohttp.ClientTimeout(total=self._command_timeout)
        async with session.post(url, json=payload, timeout=timeout) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise HAConnectionError(f"HA service call {domain}.{service} failed ({resp.status}): {body}")
            return await resp.json()

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self._base_url}/api/states/{entity_id}"
        async with session.get(url) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise HAConnectionError(f"Failed to fetch state for {entity_id} ({resp.status}): {body}")
            return await resp.json()

    async def list_states(self, domain_filter: Optional[str] = None) -> list[dict[str, Any]]:
        """Return all entity states known to HA, optionally filtered to one domain
        (e.g. domain_filter="light" returns only light.* entities)."""
        session = await self._get_session()
        url = f"{self._base_url}/api/states"
        async with session.get(url) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise HAConnectionError(f"Failed to fetch states ({resp.status}): {body}")
            states: list[dict[str, Any]] = await resp.json()
        if domain_filter:
            prefix = f"{domain_filter}."
            states = [s for s in states if s.get("entity_id", "").startswith(prefix)]
        return states

    async def force_device_poll(self, entity_id: str) -> None:
        """Best-effort: ask HA to re-poll the entity instead of trusting its cached
        state. Not all integrations support this; failures are logged, not
        raised, since this is a confidence upgrade, not a required step.
        """
        try:
            await self.call_service("homeassistant", "update_entity", entity_id)
        except HAConnectionError:
            logger.warning(
                "homeassistant.update_entity not supported/failed for %s; "
                "falling back to ha_reported confidence",
                entity_id,
            )

    async def execute_verified_command(
        self,
        domain: str,
        service: str,
        entity_id: str,
        expected_state: Optional[str] = None,
        expected_attributes: Optional[dict[str, float]] = None,
        attribute_tolerances: Optional[dict[str, float]] = None,
        service_data: Optional[dict[str, Any]] = None,
        force_device_poll: bool = False,
        fast_path_timeout: float = 3.0,
        allow_retry: bool = True,
    ) -> VerifiedCommandResult:
        """Execute -> Verify -> Report loop for a single HA service call.

        `service_data` carries the actual command payload (e.g. {"brightness": 200},
        {"percentage": 75}) -- distinct from `expected_attributes`, which is what
        the post-condition check compares against. Never reports success on a
        bare 200 -- always requires a matching post-condition read, per AuraAI's
        agent execution contract. Retries at most once, then hard-fails.
        """
        def predicate(s: dict[str, Any]) -> bool:
            return state_matches(s, expected_state, expected_attributes, attribute_tolerances)

        result = await self._attempt(
            domain, service, entity_id, predicate, service_data, force_device_poll, fast_path_timeout, attempt=1
        )
        if result.success or not allow_retry:
            return result

        logger.info("Verification failed for %s on attempt 1, retrying once", entity_id)
        return await self._attempt(
            domain, service, entity_id, predicate, service_data, force_device_poll, fast_path_timeout, attempt=2
        )

    async def _attempt(
        self,
        domain: str,
        service: str,
        entity_id: str,
        predicate: Callable[[dict[str, Any]], bool],
        service_data: Optional[dict[str, Any]],
        force_device_poll: bool,
        fast_path_timeout: float,
        attempt: int,
    ) -> VerifiedCommandResult:
        # Register the waiter BEFORE issuing the command so a fast state_changed
        # event can't arrive before we start listening for it.
        waiter_task = asyncio.ensure_future(
            self._ws_client.register_state_waiter(entity_id, predicate, timeout=fast_path_timeout)
        )

        try:
            changed_states = await self.call_service(domain, service, entity_id, service_data)
        except HAConnectionError as exc:
            waiter_task.cancel()
            return VerifiedCommandResult(False, entity_id, None, "unverified", attempt, error=str(exc))

        # Fast path: HA's own service-call response already blocked until the
        # command finished, and lists whatever changed during that window.
        for state_obj in changed_states:
            if state_obj.get("entity_id") == entity_id and predicate(state_obj):
                waiter_task.cancel()
                return VerifiedCommandResult(True, entity_id, state_obj, "ha_reported", attempt)

        # Fallback: wait on the already-registered WS waiter.
        try:
            state_obj = await waiter_task
            return VerifiedCommandResult(True, entity_id, state_obj, "ha_reported", attempt)
        except asyncio.TimeoutError:
            pass
        except HAConnectionError as exc:
            return VerifiedCommandResult(False, entity_id, None, "unverified", attempt, error=str(exc))

        # Final fallback: single poll, optionally forcing a fresh device read.
        if force_device_poll or self._verify_device_poll_default:
            await self.force_device_poll(entity_id)
            confidence = "device_polled"
        else:
            confidence = "ha_reported"

        try:
            state_obj = await self.get_state(entity_id)
        except HAConnectionError as exc:
            return VerifiedCommandResult(False, entity_id, None, "unverified", attempt, error=str(exc))

        if predicate(state_obj):
            return VerifiedCommandResult(True, entity_id, state_obj, confidence, attempt)

        return VerifiedCommandResult(
            False,
            entity_id,
            state_obj,
            confidence,
            attempt,
            error=f"Post-condition failed: expected state/attrs not met, got {state_obj.get('state')!r}",
        )
