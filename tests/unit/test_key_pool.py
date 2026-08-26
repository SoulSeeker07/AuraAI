"""
tests/unit/test_key_pool.py

Unit tests for KeyPool (Multi-API Key Rotation Engine).
"""

from __future__ import annotations

import os
import time
import pytest

from ai.key_pool import KeyPool


def test_key_pool_explicit_keys():
    """Verify KeyPool initializes with explicit key dictionaries."""
    pool = KeyPool(explicit_keys={"groq": ["key_a", "key_b", "key_c"]})
    assert pool.count("groq") == 3
    assert pool.get_all_keys("groq") == ["key_a", "key_b", "key_c"]
    assert pool.get_active_key("groq") == "key_a"


def test_key_pool_round_robin_rotation():
    """Verify round-robin rotation advances through keys."""
    pool = KeyPool(explicit_keys={"groq": ["key_1", "key_2", "key_3"]})
    assert pool.get_active_key("groq") == "key_1"
    
    k2 = pool.rotate("groq")
    assert k2 == "key_2"
    
    k3 = pool.rotate("groq")
    assert k3 == "key_3"
    
    k1 = pool.rotate("groq")
    assert k1 == "key_1"


def test_key_pool_rate_limiting_cooldown():
    """Verify that marking a key rate-limited skips it in rotation."""
    pool = KeyPool(explicit_keys={"groq": ["key_1", "key_2", "key_3"]})
    
    # Mark key_1 as rate-limited for 60 seconds
    pool.mark_rate_limited("key_1", cooldown_seconds=60.0, service="groq")
    
    # Active key should immediately skip key_1 and give key_2
    active = pool.get_active_key("groq")
    assert active == "key_2"
    
    # Rotate should cycle between key_2 and key_3 (skipping key_1)
    assert pool.rotate("groq") == "key_3"
    assert pool.rotate("groq") == "key_2"


def test_key_pool_execute_with_failover_success():
    """Verify execute_with_failover runs without error on healthy key."""
    pool = KeyPool(explicit_keys={"groq": ["good_key_1", "good_key_2"]})
    
    def mock_operation(key: str) -> str:
        return f"result_with_{key}"
    
    res = pool.execute_with_failover(mock_operation, service="groq")
    assert res == "result_with_good_key_1"


def test_key_pool_execute_with_failover_on_429():
    """Verify execute_with_failover catches 429 and rotates to next key automatically."""
    pool = KeyPool(explicit_keys={"groq": ["exhausted_key", "healthy_key"]})
    
    call_log = []
    
    def mock_api_call(key: str) -> str:
        call_log.append(key)
        if key == "exhausted_key":
            raise RuntimeError("Error code: 429 - Rate limit reached on tokens per day (TPD).")
        return f"success_from_{key}"
    
    res = pool.execute_with_failover(mock_api_call, service="groq")
    assert res == "success_from_healthy_key"
    assert call_log == ["exhausted_key", "healthy_key"]
    
    # Next call should now use healthy_key directly
    assert pool.get_active_key("groq") == "healthy_key"


def test_key_pool_env_discovery(monkeypatch):
    """Verify auto-discovery of single, comma-separated, and numbered environment variables."""
    # Clear any ambient env vars first
    for k in list(os.environ.keys()):
        if "GROQ" in k:
            monkeypatch.delenv(k, raising=False)

    monkeypatch.setenv("GROQ_API_KEY", "env_key_0")
    monkeypatch.setenv("GROQ_API_KEY1", "env_key_1")
    monkeypatch.setenv("GROQ_API_KEY2", "env_key_2")
    monkeypatch.setenv("GROQ_API_KEYS", "env_key_3,env_key_4")
    
    pool = KeyPool()
    keys = pool.get_all_keys("groq")
    assert len(keys) == 5
    assert set(keys) == {"env_key_0", "env_key_1", "env_key_2", "env_key_3", "env_key_4"}
