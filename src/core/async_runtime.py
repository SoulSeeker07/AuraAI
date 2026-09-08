"""
AsyncRuntime - Dedicated persistent background asyncio event loop thread for AuraAI.

Replaces per-turn ephemeral event loop patterns (new_event_loop() + loop.close())
in GUI, Voice Notch, and worker execution threads so that background subagents,
monitoring tasks, and trigger loops are not orphaned or destroyed mid-flight.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import sys
import threading
from typing import Any, Coroutine, Optional, TypeVar

logger = logging.getLogger(__name__)

# TD-002: Pre-empt dual package root split-brain
if __name__ in sys.modules:
    sys.modules.setdefault("core.async_runtime", sys.modules[__name__])
    sys.modules.setdefault("src.core.async_runtime", sys.modules[__name__])

T = TypeVar("T")


class AsyncRuntime:
    """
    Singleton managing a long-lived daemon thread with a dedicated, persistent asyncio event loop.
    """

    _instance: Optional[AsyncRuntime] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        if AsyncRuntime._instance is not None:
            raise RuntimeError("AsyncRuntime is a singleton. Use AsyncRuntime.get_instance().")
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._started_event = threading.Event()
        self._stopped_event = threading.Event()
        self._is_running = False
        self._start_runtime_thread()

    @classmethod
    def get_instance(cls) -> AsyncRuntime:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Tears down the singleton instance, stopping the persistent loop."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
                cls._instance = None

    def _start_runtime_thread(self) -> None:
        self._thread = threading.Thread(
            target=self._run_loop,
            name="AuraAsyncRuntimeThread",
            daemon=True,
        )
        self._thread.start()
        if not self._started_event.wait(timeout=5.0):
            raise RuntimeError("AsyncRuntime thread failed to initialize within 5.0 seconds.")

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._is_running = True
        self._started_event.set()
        try:
            self._loop.run_forever()
        finally:
            self._is_running = False
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception as e:
                logger.debug(f"[AsyncRuntime] Exception during loop teardown: {e}")
            finally:
                self._loop.close()
                self._stopped_event.set()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or not self._is_running:
            raise RuntimeError("AsyncRuntime loop is not running.")
        return self._loop

    @property
    def is_running(self) -> bool:
        return self._is_running and self._loop is not None and self._loop.is_running()

    def run_coroutine_sync(
        self,
        coro: Coroutine[Any, Any, T],
        timeout: Optional[float] = None,
    ) -> T:
        """
        Submits a coroutine to the persistent runtime event loop and waits synchronously for its result.
        Safe to call from GUI threads, worker threads, or CLI threads.
        """
        if not self.is_running:
            raise RuntimeError("Cannot execute coroutine: AsyncRuntime loop is not running.")

        current_thread = threading.current_thread()
        if current_thread == self._thread:
            raise RuntimeError(
                "Deadlock avoidance: run_coroutine_sync cannot be called from within the AsyncRuntime thread."
            )

        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"AsyncRuntime coroutine timed out after {timeout} seconds.")
        except Exception:
            raise

    def create_task(self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        """
        Schedules a detached coroutine on the runtime loop thread-safely and returns a concurrent.futures.Future.
        """
        if not self.is_running:
            raise RuntimeError("Cannot create task: AsyncRuntime loop is not running.")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self, timeout: float = 3.0) -> None:
        """
        Stops the persistent event loop and joins the background thread.
        """
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._stopped_event.wait(timeout=timeout)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
