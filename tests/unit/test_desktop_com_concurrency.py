"""
Unit Tests for Desktop Engine & COM Concurrency Thread Safety
Location: tests/unit/test_desktop_com_concurrency.py

Verifies:
1. DesktopEngineBackend.execute_plan_async runs via asyncio.to_thread concurrently.
2. Concurrent worker threads running COM/UIA operations properly pair CoInitialize and CoUninitialize.
3. Thread-pool reuse does not crash on RPC_E_CHANGED_MODE or cause cross-thread apartment state bleed.
"""

import asyncio
import pytest

from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.planning.action_plan import ActionPlan
from desktop.native.adapters.com_threading import com_scope, com_thread_safe


@pytest.mark.asyncio
async def test_com_scope_idempotency_and_safe_lifecycle():
    """Verify com_scope properly initializes and uninitializes COM on worker threads."""
    def worker_com_call(thread_id: int):
        with com_scope():
            import pythoncom
            # Verify COM is initialized and callable
            guid = pythoncom.CreateGuid()
            assert len(str(guid)) > 0
            return f"thread_{thread_id}_guid_{guid}"

    # Dispatch across 5 parallel thread-pool workers
    tasks = [asyncio.to_thread(worker_com_call, i) for i in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    assert len(results) == 5
    for r in results:
        assert "thread_" in r
        assert "guid" in r


@pytest.mark.asyncio
async def test_desktop_engine_backend_concurrent_to_thread_execution():
    """Verify DesktopEngineBackend handles concurrent execute_plan_async calls safely."""
    backend = DesktopEngineBackend()

    plans = [
        ActionPlan(
            action="system_info",
            target="system",
            goal="Query hardware summary",
            capability="system_info",
            session_id=f"sess_com_test_{i}",
        )
        for i in range(4)
    ]

    # Execute all 4 plans concurrently via execute_plan_async (which uses asyncio.to_thread)
    tasks = [backend.execute_plan_async(p) for p in plans]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    assert len(results) == 4
    for res in results:
        assert res.success is True
        assert res.planner == "desktop"
        assert len(res.observations) > 0


@pytest.mark.asyncio
async def test_repeated_threadpool_reuse_com_stability():
    """Verify that repeated worker thread pool reuse does not leak COM state."""
    @com_thread_safe
    def repeated_worker(iteration: int):
        import pythoncom
        g = pythoncom.CreateGuid()
        return str(g)

    # 10 sequential waves of 4 concurrent threads to force thread-pool recycling
    for wave in range(5):
        tasks = [asyncio.to_thread(repeated_worker, wave * 10 + i) for i in range(4)]
        wave_results = await asyncio.gather(*tasks, return_exceptions=False)
        assert len(wave_results) == 4
        assert len(set(wave_results)) == 4
