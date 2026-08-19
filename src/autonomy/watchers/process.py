"""
ProcessMonitor Dumb Telemetry Producer (M24 Phase 6)
Location: src/autonomy/watchers/process.py

Native OS process lifecycle monitor emitting raw AuraEvent telemetry into the EventRuntime.

Architectural Invariants:
1. Pure Dumb Sensor: Observes process creation, execution, and termination facts.
   NEVER evaluates business logic, NEVER executes repair tools, NEVER calls LLMs.
2. Non-Invasive: Observes legitimate OS process tables via psutil without invasive hooking.
3. Clean Lifecycle: Thread-safe polling loop with clean start/stop controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any

import psutil

from ..events import AuraEvent, EventSource, EventType
from ..event_runtime import EventRuntime

logger = logging.getLogger(__name__)


@dataclass
class _ObservedProcessInfo:
    pid: int
    name: str
    cmdline: list[str]
    ppid: int | None
    started_at: float


class ProcessMonitor:
    """
    Physical Process Telemetry Producer.
    Monitors process lifecycle transitions (launch, termination, crash) and emits raw AuraEvents.
    """

    def __init__(
        self,
        runtime: EventRuntime,
        target_process_names: set[str] | list[str] | None = None,
        poll_interval_seconds: float = 0.5,
    ) -> None:
        self.runtime = runtime
        self.poll_interval = poll_interval_seconds
        self.target_names = {n.lower().strip() for n in target_process_names} if target_process_names else None

        self._active_processes: dict[int, _ObservedProcessInfo] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        """Starts background process polling loop."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._snapshot_initial_processes()
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="AuraProcessMonitor")
            self._thread.start()
            logger.info("[ProcessMonitor] Started native OS process lifecycle monitor.")

    def stop(self, timeout: float = 2.0) -> None:
        """Stops process monitor loop cleanly."""
        with self._lock:
            if self._thread is None:
                return

            self._stop_event.set()
            self._thread.join(timeout=timeout)
            self._thread = None
            logger.info("[ProcessMonitor] Stopped native OS process lifecycle monitor.")

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def record_process_exit(
        self,
        process_name: str,
        exit_code: int,
        correlation_id: str | None = None,
        stderr_snippet: str | None = None,
        pid: int | None = None,
    ) -> AuraEvent:
        """
        Explicit observation recording for supervised executions or test runs.
        Emits a factual PROCESS_EXITED or PROCESS_CRASHED AuraEvent.
        """
        event_type = EventType.PROCESS_CRASHED if exit_code < 0 or exit_code in [139, 3221225477] else EventType.PROCESS_EXITED
        payload: dict[str, Any] = {
            "process_name": process_name.lower().strip(),
            "exit_code": exit_code,
            "pid": pid or 0,
        }
        if stderr_snippet:
            payload["stderr"] = stderr_snippet[:1024]

        event = AuraEvent.create(
            event_type=event_type,
            source=EventSource.PROCESS,
            payload=payload,
            correlation_id=correlation_id,
        )
        self.runtime.ingest(event)
        return event

    def _snapshot_initial_processes(self) -> None:
        """Takes an initial snapshot of active processes to avoid firing storm on startup."""
        now = time.monotonic()
        for proc in psutil.process_iter(["pid", "name", "cmdline", "ppid"]):
            try:
                p_name = (proc.info.get("name") or "").lower().strip()
                if self._matches_filter(p_name):
                    self._active_processes[proc.info["pid"]] = _ObservedProcessInfo(
                        pid=proc.info["pid"],
                        name=p_name,
                        cmdline=proc.info.get("cmdline") or [],
                        ppid=proc.info.get("ppid"),
                        started_at=now,
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _matches_filter(self, proc_name: str) -> bool:
        if not self.target_names:
            return True
        return any(target in proc_name for target in self.target_names)

    def _monitor_loop(self) -> None:
        """Polling loop observing process births and deaths."""
        while not self._stop_event.is_set():
            try:
                current_pids: dict[int, _ObservedProcessInfo] = {}
                now = time.monotonic()

                for proc in psutil.process_iter(["pid", "name", "cmdline", "ppid"]):
                    try:
                        pid = proc.info["pid"]
                        p_name = (proc.info.get("name") or "").lower().strip()

                        if not self._matches_filter(p_name):
                            continue

                        current_pids[pid] = _ObservedProcessInfo(
                            pid=pid,
                            name=p_name,
                            cmdline=proc.info.get("cmdline") or [],
                            ppid=proc.info.get("ppid"),
                            started_at=now,
                        )

                        # Check for newly started process
                        if pid not in self._active_processes:
                            self._emit_started_event(current_pids[pid])

                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Check for exited processes
                for old_pid, old_info in list(self._active_processes.items()):
                    if old_pid not in current_pids:
                        self._emit_exited_event(old_info, exit_code=0)

                self._active_processes = current_pids

            except Exception as e:
                logger.debug(f"[ProcessMonitor] Exception in monitor loop: {e}")

            self._stop_event.wait(self.poll_interval)

    def _emit_started_event(self, p_info: _ObservedProcessInfo) -> None:
        try:
            event = AuraEvent.create(
                event_type=EventType.PROCESS_STARTED,
                source=EventSource.PROCESS,
                payload={
                    "pid": p_info.pid,
                    "process_name": p_info.name,
                    "cmdline": p_info.cmdline,
                    "ppid": p_info.ppid,
                },
            )
            self.runtime.ingest(event)
        except Exception as e:
            logger.debug(f"[ProcessMonitor] Error emitting started event: {e}")

    def _emit_exited_event(self, p_info: _ObservedProcessInfo, exit_code: int = 0) -> None:
        try:
            event = AuraEvent.create(
                event_type=EventType.PROCESS_EXITED,
                source=EventSource.PROCESS,
                payload={
                    "pid": p_info.pid,
                    "process_name": p_info.name,
                    "exit_code": exit_code,
                    "ppid": p_info.ppid,
                },
            )
            self.runtime.ingest(event)
        except Exception as e:
            logger.debug(f"[ProcessMonitor] Error emitting exited event: {e}")
