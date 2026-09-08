"""
tests/unit/test_browser_session_manager.py

Unit tests for BrowserSessionManager singleton registry:
- Concurrency cap (1 active browser, eviction of prior sessions).
- Tombstone recording (bumped_by_new_goal, ttl_expired).
- Idle session reaping across AWAITING_USER.
- Strict isolation via MagicMock (zero live Playwright / browser processes).
"""

import time
from unittest.mock import MagicMock
import pytest

from browser.browser_session_manager import BrowserSessionManager
from core.orchestration.goal_state import GoalStatus


@pytest.fixture(autouse=True)
def reset_manager():
    """Ensure a clean registry before and after every test."""
    BrowserSessionManager.reset_for_testing()
    yield
    BrowserSessionManager.reset_for_testing()


def test_acquire_and_get_session():
    mgr = BrowserSessionManager.get_instance()
    mock_sess = MagicMock()
    mock_sess.page = MagicMock()
    mock_sess.active_page.return_value = mock_sess.page

    sess = mgr.acquire_session("goal-101", session_factory=lambda: mock_sess)
    assert sess is mock_sess
    assert mgr.get_session("goal-101") is mock_sess
    assert mgr.get_page("goal-101") is mock_sess.page


def test_concurrency_cap_evicts_older_session_with_tombstone():
    mgr = BrowserSessionManager.get_instance()
    mock_sess1 = MagicMock()
    mock_sess2 = MagicMock()

    mgr.acquire_session("goal-old", session_factory=lambda: mock_sess1)
    assert mgr.get_session("goal-old") is mock_sess1

    # Acquire for new goal -> must cleanly close old session under 1-browser cap
    mgr.acquire_session("goal-new", session_factory=lambda: mock_sess2)
    mock_sess1.close.assert_called_once()
    assert mgr.get_session("goal-old") is None
    assert mgr.get_session("goal-new") is mock_sess2

    # Tombstone check for goal-old
    tomb = mgr.get_tombstone("goal-old")
    assert tomb is not None
    assert tomb["reason"] == "bumped_by_new_goal"
    assert "timestamp" in tomb


def test_close_session_completed_records_no_tombstone():
    mgr = BrowserSessionManager.get_instance()
    mock_sess = MagicMock()
    mgr.acquire_session("goal-done", session_factory=lambda: mock_sess)

    mgr.close_session("goal-done", reason="completed")
    mock_sess.close.assert_called_once()
    assert mgr.get_session("goal-done") is None
    assert mgr.get_tombstone("goal-done") is None


def test_reap_idle_sessions_in_awaiting_user():
    mgr = BrowserSessionManager.get_instance()
    mock_sess1 = MagicMock()
    mock_sess2 = MagicMock()

    # Directly attach two sessions to test reaping multi-session edge cases
    mgr._active_sessions["goal-stale"] = mock_sess1
    mgr._active_sessions["goal-fresh"] = mock_sess2

    now = time.time()
    mock_goal_store = MagicMock()

    goal_stale = MagicMock()
    goal_stale.status = GoalStatus.AWAITING_USER
    goal_stale.updated_at = now - 1200.0  # 20 mins ago (> 15 min TTL)

    goal_fresh = MagicMock()
    goal_fresh.status = GoalStatus.AWAITING_USER
    goal_fresh.updated_at = now - 60.0    # 1 min ago (< 15 min TTL)

    def get_mock_goal(gid):
        if gid == "goal-stale":
            return goal_stale
        if gid == "goal-fresh":
            return goal_fresh
        return None

    mock_goal_store.get_goal.side_effect = get_mock_goal

    reaped = mgr.reap_idle_sessions(mock_goal_store, max_idle_seconds=900.0)
    assert reaped == ["goal-stale"]
    mock_sess1.close.assert_called_once()
    mock_sess2.close.assert_not_called()

    assert mgr.get_session("goal-stale") is None
    assert mgr.get_session("goal-fresh") is mock_sess2

    tomb = mgr.get_tombstone("goal-stale")
    assert tomb is not None
    assert tomb["reason"] == "ttl_expired"


def test_operation_scope_in_flight_lease_rejects_concurrent_eviction():
    """
    Proves that when Goal A holds an in-flight operation lease via operation_scope,
    a concurrent acquire_session for Goal B raises RuntimeError rather than evicting Goal A.
    """
    mgr = BrowserSessionManager.get_instance()
    mock_sess_a = MagicMock()
    mock_sess_b = MagicMock()

    mgr.acquire_session("goal-a", session_factory=lambda: mock_sess_a)
    assert mgr.get_session("goal-a") is mock_sess_a

    # Enter in-flight operation scope for Goal A
    with mgr.operation_scope("goal-a"):
        assert mgr.is_operation_in_flight("goal-a") is True

        # Goal B attempts to acquire -> MUST raise RuntimeError, NOT evict Goal A
        with pytest.raises(RuntimeError) as excinfo:
            mgr.acquire_session("goal-b", session_factory=lambda: mock_sess_b)

        assert "is actively executing a browser operation" in str(excinfo.value)
        assert "Concurrent in-flight browser execution is rejected" in str(excinfo.value)

        # Goal A must NOT have been closed or evicted
        mock_sess_a.close.assert_not_called()
        assert mgr.get_session("goal-a") is mock_sess_a
        assert mgr.get_session("goal-b") is None

    # After operation completes and lease is released:
    assert mgr.is_operation_in_flight("goal-a") is False

    # Now Goal B can acquire session cleanly, evicting the now-idle Goal A
    mgr.acquire_session("goal-b", session_factory=lambda: mock_sess_b)
    mock_sess_a.close.assert_called_once()
    assert mgr.get_session("goal-a") is None
    assert mgr.get_session("goal-b") is mock_sess_b

    tomb = mgr.get_tombstone("goal-a")
    assert tomb is not None
    assert tomb["reason"] == "bumped_by_new_goal"


@pytest.mark.asyncio
async def test_run_on_browser_thread_async_non_blocking():
    """
    Proves that run_on_browser_thread_async executes functions on the dedicated
    worker thread via run_in_executor without blocking the event loop.
    """
    import threading
    from browser.browser_session_manager import run_on_browser_thread_async

    def _worker_fn(val, suffix=""):
        return f"{threading.current_thread().name}:{val}{suffix}"

    res = await run_on_browser_thread_async(_worker_fn, 42, suffix="-ok")
    assert "AuraDedicatedBrowserThread" in res
    assert ":42-ok" in res
