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
    from unittest.mock import patch

    # Clear any ambient env vars first
    for k in list(os.environ.keys()):
        if "GROQ" in k or "GEMINI" in k:
            monkeypatch.delenv(k, raising=False)

    monkeypatch.setenv("GROQ_API_KEY", "env_key_0")
    monkeypatch.setenv("GROQ_API_KEY1", "env_key_1")
    monkeypatch.setenv("GROQ_API_KEY2", "env_key_2")
    monkeypatch.setenv("GROQ_API_KEYS", "env_key_3,env_key_4")

    with patch("dotenv.load_dotenv"):
        pool = KeyPool()
        keys = pool.get_all_keys("groq")
        assert len(keys) == 5
        assert set(keys) == {"env_key_0", "env_key_1", "env_key_2", "env_key_3", "env_key_4"}


def test_key_pool_tpm_burst_vs_tpd_classification():
    """Verify TPM rate limit with 'try again in 3s' gets ~5s cooldown, while TPD gets daily 5am IST."""
    pool = KeyPool(explicit_keys={"groq": ["tpm_key", "tpd_key", "healthy_key"]})

    # 1. Trigger TPM error with exact seconds
    def mock_tpm_call(key: str) -> str:
        if key == "tpm_key":
            raise RuntimeError(
                "Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` "
                "on tokens per minute (TPM): Limit 6000, Used 5980, Requested 300. Please try again in 3.0s.', "
                "'type': 'tokens', 'code': 'rate_limit_exceeded'}}"
            )
        return f"success_{key}"

    res = pool.execute_with_failover(mock_tpm_call, service="groq")
    assert res == "success_tpd_key"

    # Cooldown for tpm_key should be ~5.0s (3.0s + 2.0s buffer), NOT 18 hours
    now = time.time()
    tpm_expire = pool._cooldowns["groq"]["tpm_key"]
    assert 3.0 <= (tpm_expire - now) <= 10.0

    # 2. Trigger TPD (daily quota) error
    def mock_tpd_call(key: str) -> str:
        if key == "tpd_key":
            raise RuntimeError(
                "Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` "
                "on tokens per day (TPD): Limit 200000, Used 200000, Requested 300. Please try again in 18h.', "
                "'type': 'tokens', 'code': 'rate_limit_exceeded'}}"
            )
        return f"success_{key}"

    res2 = pool.execute_with_failover(mock_tpd_call, service="groq")
    assert res2 == "success_healthy_key"

    # Cooldown for tpd_key should be until tomorrow 5am IST (> 60s)
    tpd_expire = pool._cooldowns["groq"]["tpd_key"]
    assert (tpd_expire - now) > 60.0


def test_key_pool_fail_fast_when_all_in_cooldown():
    """Verify that when all keys are on cooldown, execute_with_failover fails fast without making network calls."""
    from ai.exceptions import KeyPoolExhaustedError

    pool = KeyPool(explicit_keys={"groq": ["k1", "k2"]})
    pool.mark_rate_limited("k1", cooldown_seconds=60.0, service="groq")
    pool.mark_rate_limited("k2", cooldown_seconds=60.0, service="groq")

    network_attempts = 0

    def mock_network_call(key: str) -> str:
        nonlocal network_attempts
        network_attempts += 1
        return "should_never_reach"

    with pytest.raises(KeyPoolExhaustedError) as exc_info:
        pool.execute_with_failover(mock_network_call, service="groq")

    # Zero network calls should have been made!
    assert network_attempts == 0
    assert "rate-limited on cooldown" in str(exc_info.value)


def test_key_pool_cooldown_persistence(tmp_path):
    """Verify cooldowns save to disk and reload upon KeyPool initialization."""
    cooldown_file = tmp_path / "test_cooldowns.json"

    pool1 = KeyPool(explicit_keys={"groq": ["key_persist_1", "key_persist_2"]}, persist_cooldowns=True)
    pool1._cooldown_file = cooldown_file

    pool1.mark_rate_limited("key_persist_1", cooldown_seconds=120.0, service="groq")
    assert cooldown_file.exists()

    # Create pool2 pointing to same file
    pool2 = KeyPool(explicit_keys={"groq": ["key_persist_1", "key_persist_2"]}, persist_cooldowns=True)
    pool2._cooldown_file = cooldown_file
    pool2._load_cooldowns()

    # key_persist_1 should still be on cooldown in pool2
    assert "key_persist_1" in pool2._cooldowns["groq"]
    assert pool2.get_active_key("groq") == "key_persist_2"


