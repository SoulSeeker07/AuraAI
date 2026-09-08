import asyncio
import time
import pytest
from src.core.async_runtime import AsyncRuntime


@pytest.fixture(autouse=True)
def cleanup_runtime():
    yield
    AsyncRuntime.reset_instance()


def test_async_runtime_singleton_and_thread():
    rt1 = AsyncRuntime.get_instance()
    rt2 = AsyncRuntime.get_instance()
    assert rt1 is rt2
    assert rt1.is_running
    assert rt1.loop.is_running()


def test_async_runtime_run_coroutine_sync():
    rt = AsyncRuntime.get_instance()

    async def add(a: int, b: int) -> int:
        await asyncio.sleep(0.01)
        return a + b

    result = rt.run_coroutine_sync(add(10, 25), timeout=2.0)
    assert result == 35


def test_async_runtime_background_task_survives_sync_caller():
    rt = AsyncRuntime.get_instance()
    completed_flag = {"done": False}

    async def long_running_worker():
        await asyncio.sleep(0.1)
        completed_flag["done"] = True

    async def parent_turn():
        # Dispatch detached task inside runtime loop
        loop = asyncio.get_running_loop()
        loop.create_task(long_running_worker())
        return "immediate_response"

    # Synchronous turn completes quickly
    resp = rt.run_coroutine_sync(parent_turn(), timeout=2.0)
    assert resp == "immediate_response"
    assert not completed_flag["done"], "Worker should still be running in background"

    # Wait for detached worker to complete on persistent loop
    time.sleep(0.2)
    assert completed_flag["done"] is True, "Worker should have completed on persistent loop"
