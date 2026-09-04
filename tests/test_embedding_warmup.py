import asyncio
import time
import pytest
from core.embedding_warmup import EmbeddingModelWarmup

@pytest.mark.asyncio
async def test_embedding_warmup_single_load_guarantee():
    load_count = 0

    def slow_loader():
        nonlocal load_count
        load_count += 1
        time.sleep(0.05)
        return "mock_model_v1"

    warmup = EmbeddingModelWarmup(load_fn=slow_loader)
    warmup.start_background_warmup()

    # Fire 5 concurrent requests simultaneously while warmup is in flight
    results = await asyncio.gather(
        warmup.ensure_ready(),
        warmup.ensure_ready(),
        warmup.ensure_ready(),
        warmup.ensure_ready(),
        warmup.ensure_ready(),
    )

    assert all(r == "mock_model_v1" for r in results)
    assert load_count == 1  # Exactly ONE invocation!
    assert warmup.is_ready is True


@pytest.mark.asyncio
async def test_embedding_warmup_fallback_without_start():
    load_count = 0

    def loader():
        nonlocal load_count
        load_count += 1
        return "fallback_model"

    warmup = EmbeddingModelWarmup(load_fn=loader)
    assert warmup.is_ready is False

    res = await warmup.ensure_ready()
    assert res == "fallback_model"
    assert load_count == 1
    assert warmup.is_ready is True


def test_embedding_warmup_sync():
    warmup = EmbeddingModelWarmup(load_fn=lambda: "sync_model")
    res = warmup.ensure_ready_sync(timeout=1.0)
    assert res == "sync_model"
    assert warmup.is_ready is True
