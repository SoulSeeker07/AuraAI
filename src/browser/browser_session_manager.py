"""
browser_session_manager.py

Long-lived singleton registry managing persistent Playwright browser sessions
keyed by goal_id. Survives across ephemeral AgentLoop instantiations (e.g.
across the AWAITING_USER pause and resume boundary).

Enforces:
1. Hard desktop concurrency cap of 1 active persistent browser context.
2. Eviction tombstones for distinct failure diagnostics (ttl_expired, bumped_by_new_goal).
3. Idle session reaping for abandoned goals in AWAITING_USER.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Set

from browser.browser_session import BrowserSession

logger = logging.getLogger(__name__)

# Dedicated single-thread worker for all Playwright Sync API operations.
# Sync Playwright is strictly thread-affine: any browser, context, or page
# initialized on Thread X MUST be interacted with and closed on Thread X.
# Pinned to a single worker thread to prevent thread-affinity corruption across async calls.
_BROWSER_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="AuraDedicatedBrowserThread",
)


def run_on_browser_thread(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Marshals a function onto the single dedicated Playwright OS worker thread."""
    future = _BROWSER_EXECUTOR.submit(fn, *args, **kwargs)
    return future.result()


async def run_on_browser_thread_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Non-blocking async invocation: schedules fn directly onto the dedicated browser worker
    thread via loop.run_in_executor without double-threading or blocking the asyncio event loop.
    """
    import asyncio
    import functools
    loop = asyncio.get_running_loop()
    if kwargs:
        call_fn = functools.partial(fn, *args, **kwargs)
        return await loop.run_in_executor(_BROWSER_EXECUTOR, call_fn)
    return await loop.run_in_executor(_BROWSER_EXECUTOR, fn, *args)


class BrowserSessionManager:
    """
    Thread-safe singleton registry that owns live BrowserSession instances.
    """

    _instance: Optional["BrowserSessionManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._active_sessions: Dict[str, BrowserSession] = {}
        self._tombstones: Dict[str, Dict[str, Any]] = {}
        self._in_flight_goals: Set[str] = set()
        self._registry_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BrowserSessionManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_for_testing(cls) -> None:
        """Close all active sessions and reset the singleton for test isolation."""
        with cls._lock:
            if cls._instance is not None:
                with cls._instance._registry_lock:
                    for gid, sess in list(cls._instance._active_sessions.items()):
                        try:
                            run_on_browser_thread(sess.close)
                        except Exception:
                            pass
                    cls._instance._active_sessions.clear()
                    cls._instance._tombstones.clear()
                    cls._instance._in_flight_goals.clear()
                cls._instance = None

    @contextlib.contextmanager
    def operation_scope(self, goal_id: str):
        """Marks a goal as actively executing a browser operation to protect it from eviction."""
        with self._registry_lock:
            self._in_flight_goals.add(goal_id)
        try:
            yield
        finally:
            with self._registry_lock:
                self._in_flight_goals.discard(goal_id)

    def is_operation_in_flight(self, goal_id: str) -> bool:
        with self._registry_lock:
            return goal_id in self._in_flight_goals

    def acquire_session(
        self,
        goal_id: str,
        headless: Optional[bool] = None,
        session_factory: Optional[Callable[[], BrowserSession]] = None,
    ) -> BrowserSession:
        """
        Acquires or creates a persistent BrowserSession for goal_id on the dedicated thread.
        Enforces a hard ceiling of 1 active browser context: if another goal
        holds a session and is IDLE, it is evicted and marked as 'bumped_by_new_goal'.
        If another goal is actively mid-operation, raises RuntimeError to prevent yank-crashes.
        """
        with self._registry_lock:
            # 1. If this goal already owns an active session, check if it's usable
            if goal_id in self._active_sessions:
                existing = self._active_sessions[goal_id]
                if getattr(existing, "page", None) is not None:
                    return existing

            # 2. Concurrency Cap: Check for active in-flight operations on other sessions
            for other_gid in list(self._active_sessions.keys()):
                if other_gid != goal_id:
                    if other_gid in self._in_flight_goals:
                        raise RuntimeError(
                            f"Cannot acquire browser for goal [{goal_id}]: "
                            f"Goal [{other_gid}] is actively executing a browser operation. "
                            "Concurrent in-flight browser execution is rejected under the 1-browser desktop cap."
                        )
                    logger.info(
                        "[BrowserSessionManager] Evicting idle browser for goal [%s] "
                        "(bumped by new goal [%s])",
                        other_gid,
                        goal_id,
                    )
                    self._close_session_locked(other_gid, reason="bumped_by_new_goal")

            # 3. Instantiate and enter the new browser session on the dedicated thread
            if session_factory is not None:
                session = session_factory()
            else:
                session = run_on_browser_thread(self._create_and_enter_session, headless)

            self._active_sessions[goal_id] = session
            self._tombstones.pop(goal_id, None)
            logger.info("[BrowserSessionManager] Attached browser session for goal [%s]", goal_id)
            return session

    @staticmethod
    def _create_and_enter_session(headless: Optional[bool]) -> BrowserSession:
        sess = BrowserSession(headless=headless)
        sess.__enter__()
        return sess

    def attach_session(self, goal_id: str, session: BrowserSession) -> None:
        """Directly attach an existing session object (useful for dependency injection / tests)."""
        with self._registry_lock:
            for other_gid in list(self._active_sessions.keys()):
                if other_gid != goal_id:
                    self._close_session_locked(other_gid, reason="bumped_by_new_goal")

            self._active_sessions[goal_id] = session
            self._tombstones.pop(goal_id, None)

    def get_session(self, goal_id: str) -> Optional[BrowserSession]:
        """Retrieve the active BrowserSession for goal_id, or None."""
        with self._registry_lock:
            return self._active_sessions.get(goal_id)

    def get_page(self, goal_id: str) -> Optional[Any]:
        """Retrieve the live Playwright Page for goal_id, or None."""
        with self._registry_lock:
            session = self._active_sessions.get(goal_id)
            if session is None:
                return None
            if hasattr(session, "active_page"):
                try:
                    return run_on_browser_thread(session.active_page)
                except Exception:
                    return getattr(session, "page", None)
            return getattr(session, "page", None)

    def close_session(self, goal_id: str, reason: str = "completed") -> None:
        """Close and detach the browser session for goal_id."""
        with self._registry_lock:
            self._close_session_locked(goal_id, reason=reason)

    def _close_session_locked(self, goal_id: str, reason: str = "completed") -> None:
        session = self._active_sessions.pop(goal_id, None)
        if session is not None:
            try:
                run_on_browser_thread(session.close)
            except Exception as ex:
                logger.warning(
                    "[BrowserSessionManager] Error closing browser for [%s]: %s", goal_id, ex
                )

        if reason != "completed":
            self._tombstones[goal_id] = {
                "reason": reason,
                "timestamp": time.time(),
            }
            logger.info(
                "[BrowserSessionManager] Recorded tombstone for goal [%s]: %s", goal_id, reason
            )

    def get_tombstone(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve eviction tombstone details for goal_id, if any."""
        with self._registry_lock:
            return self._tombstones.get(goal_id)

    def clear_tombstone(self, goal_id: str) -> None:
        with self._registry_lock:
            self._tombstones.pop(goal_id, None)

    def reap_idle_sessions(self, goal_store: Any, max_idle_seconds: float = 900.0) -> list[str]:
        """
        Reaps active browser sessions whose goal in GoalStore has been paused
        in AWAITING_USER for more than max_idle_seconds.
        """
        reaped: list[str] = []
        if goal_store is None:
            return reaped

        now = time.time()
        with self._registry_lock:
            for gid in list(self._active_sessions.keys()):
                try:
                    goal = goal_store.get_goal(gid)
                    if not goal:
                        continue

                    status_val = goal.status.value if hasattr(goal.status, "value") else str(goal.status)
                    if status_val.lower() == "awaiting_user":
                        idle_time = now - goal.updated_at
                        if idle_time >= max_idle_seconds:
                            logger.warning(
                                "[BrowserSessionManager] Reaping orphaned browser for goal [%s] "
                                "(idle in AWAITING_USER for %.1fs >= %.1fs)",
                                gid,
                                idle_time,
                                max_idle_seconds,
                            )
                            self._close_session_locked(gid, reason="ttl_expired")
                            reaped.append(gid)
                except Exception as ex:
                    logger.debug(
                        "[BrowserSessionManager] Error checking goal [%s] for reaping: %s", gid, ex
                    )

        return reaped
