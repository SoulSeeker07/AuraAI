"""
src/api/status_server.py

A tiny, high‑performance local HTTP server that reports the current
battery and memory status of the host machine.  The server is built on
FastAPI/uvicorn for async handling and runs in a background daemon
thread so that the rest of the Aura application can continue to work
uninterrupted.

Endpoints
---------
GET /status
    Returns a JSON payload with the following fields:
        - battery_percent (float | None)
        - power_plugged   (bool | None)
        - memory_total    (int)   # bytes
        - memory_used     (int)   # bytes
        - memory_percent  (float)

Usage
-----
>>> from api.status_server import StatusServer
>>> server = StatusServer(host="127.0.0.1", port=8000)
>>> server.start()
>>> # ... later ...
>>> server.stop()
"""

from __future__ import annotations

import threading
import logging
from typing import Optional

import psutil
from fastapi import FastAPI
from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# Logging configuration – the host application may configure logging
# globally; we keep a module‑level logger for internal diagnostics.
# --------------------------------------------------------------------------- #
log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Pydantic model describing the JSON response.
# --------------------------------------------------------------------------- #
class StatusResponse(BaseModel):
    battery_percent: Optional[float]  # None when battery info is unavailable
    power_plugged: Optional[bool]     # None when battery info is unavailable
    memory_total: int                 # bytes
    memory_used: int                  # bytes
    memory_percent: float


# --------------------------------------------------------------------------- #
# FastAPI application definition.
# --------------------------------------------------------------------------- #
app = FastAPI(title="Aura Status Server", version="1.0.0")


def _collect_status() -> StatusResponse:
    """
    Gather battery and memory information using ``psutil`` and return a
    ``StatusResponse`` instance.
    """
    # Battery – psutil may raise NotImplementedError on platforms without a battery.
    try:
        batt = psutil.sensors_battery()
        if batt is None:
            battery_percent = None
            power_plugged = None
        else:
            battery_percent = batt.percent
            power_plugged = batt.power_plugged
    except Exception as exc:  # pragma: no cover – defensive
        log.debug("Failed to read battery info: %s", exc)
        battery_percent = None
        power_plugged = None

    vm = psutil.virtual_memory()
    return StatusResponse(
        battery_percent=battery_percent,
        power_plugged=power_plugged,
        memory_total=vm.total,
        memory_used=vm.used,
        memory_percent=vm.percent,
    )


@app.get("/status", response_model=StatusResponse, tags=["Status"])
async def status_endpoint() -> StatusResponse:
    """
    HTTP GET /status – returns the latest system status.
    """
    return _collect_status()


# --------------------------------------------------------------------------- #
# Server control class – encapsulates uvicorn server lifecycle.
# --------------------------------------------------------------------------- #
class StatusServer:
    """
    A thin wrapper around a uvicorn server that runs the FastAPI app in a
    background daemon thread.  The server is deliberately lightweight and
    intended for local inter‑process communication only (binds to 127.0.0.1
    by default).

    Example
    -------
    >>> server = StatusServer(port=8080)
    >>> server.start()
    >>> # The server is now reachable at http://127.0.0.1:8080/status
    >>> server.stop()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        *,
        log_level: str = "error",
    ) -> None:
        self.host = host
        self.port = port
        self.log_level = log_level

        self._thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

    # ------------------------------------------------------------------- #
    # Internal method that runs uvicorn.  It blocks until the server is
    # asked to shut down.
    # ------------------------------------------------------------------- #
    def _run_uvicorn(self) -> None:
        import uvicorn

        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level=self.log_level,
            # Using a single worker thread is sufficient for a local status API.
            workers=1,
        )
        server = uvicorn.Server(config)

        # uvicorn.Server.run() respects a ``should_exit`` flag; we poll the
        # threading.Event to trigger a graceful shutdown.
        log.info("Starting Aura status server on %s:%s", self.host, self.port)
        while not self._shutdown_event.is_set():
            # ``run`` returns only after the server stops; we therefore call it
            # once and then break when shutdown is requested.
            server.run()
            break

        log.info("Aura status server stopped")

    # ------------------------------------------------------------------- #
    # Public API
    # ------------------------------------------------------------------- #
    def start(self) -> None:
        """
        Start the HTTP server in a daemon thread.  If the server is already
        running this call is a no‑op.
        """
        if self._thread and self._thread.is_alive():
            log.debug("StatusServer already running")
            return

        self._shutdown_event.clear()
        self._thread = threading.Thread(
            target=self._run_uvicorn,
            name="AuraStatusServerThread",
            daemon=True,
        )
        self._thread.start()
        log.debug("StatusServer thread started")

    def stop(self, timeout: float = 5.0) -> None:
        """
        Signal the server to shut down and wait for the background thread to
        finish.  ``timeout`` seconds is the maximum wait time; after that the
        thread is left to terminate on its own (it is a daemon thread).
        """
        if not self._thread:
            log.debug("StatusServer stop called but server was never started")
            return

        log.debug("Stopping Aura status server")
        self._shutdown_event.set()
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            log.warning(
                "StatusServer thread did not exit within %.1f seconds; "
                "it will be terminated when the interpreter exits.",
                timeout,
            )
        else:
            log.debug("StatusServer stopped cleanly")
        self._thread = None

    # ------------------------------------------------------------------- #
    # Context‑manager helpers – convenient for ``with`` blocks.
    # ------------------------------------------------------------------- #
    def __enter__(self) -> "StatusServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # pragma: no cover
        self.stop()


# --------------------------------------------------------------------------- #
# If the module is executed directly, start a server for quick manual testing.
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys

    host = "127.0.0.1"
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            log.error("Invalid port number: %s", sys.argv[1])
            sys.exit(1)

    server = StatusServer(host=host, port=port, log_level="info")
    server.start()
    try:
        # Keep the main thread alive while the daemon thread serves requests.
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received – shutting down.")
        server.stop()
