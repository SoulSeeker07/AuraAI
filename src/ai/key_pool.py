"""
src/ai/key_pool.py

Centralized Multi-Key Rotation Pool for AuraAI.
Manages discovery, round-robin load-balancing, rate-limit cooldowns,
and seamless failover across multiple API keys for Groq (and other providers).

Key Discovery Patterns Supported:
  1. GROQ_API_KEYS="key1,key2,key3" (comma/space/semicolon delimited)
  2. GROQ_API_KEY="key1" (standard single key or comma-separated)
  3. Numbered keys: GROQ_API_KEY1, GROQ_API_KEY2, GROQ_API_KEY3, ...
  4. Underscore numbered keys: GROQ_API_KEY_1, GROQ_API_KEY_2, ...
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class KeyPool:
    """Thread-safe API Key Pool with automatic rotation and cooldown tracking."""

    _instance: Optional["KeyPool"] = None
    _lock = threading.Lock()

    def __init__(self, explicit_keys: Optional[Dict[str, List[str]]] = None):
        self._keys: Dict[str, List[str]] = {}
        self._key_indices: Dict[str, int] = {}
        self._cooldowns: Dict[str, Dict[str, float]] = {}  # service -> {key: expire_timestamp}
        self._mu = threading.RLock()

        if explicit_keys:
            for service, keys in explicit_keys.items():
                self._keys[service] = [k.strip() for k in keys if k and k.strip()]
                self._key_indices[service] = 0
                self._cooldowns[service] = {}
        else:
            self._discover_keys()

    @classmethod
    def get_instance(cls) -> "KeyPool":
        """Singleton accessor for the system-wide key pool."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for tests or env reloads)."""
        with cls._lock:
            cls._instance = None

    def reload(self) -> None:
        """Re-scan environment variables to refresh the key pool."""
        with self._mu:
            self._discover_keys()

    def _discover_keys(self) -> None:
        """Discover all API keys from environment variables."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass

        # 1. Discover Groq keys
        groq_keys: List[str] = []

        # Check comma-separated GROQ_API_KEYS
        multi_keys = os.environ.get("GROQ_API_KEYS", "")
        if multi_keys:
            for part in re.split(r"[,;\s\n]+", multi_keys):
                k = part.strip()
                if k and k not in groq_keys:
                    groq_keys.append(k)

        # Check standard GROQ_API_KEY (could be single or comma-separated)
        single_key = os.environ.get("GROQ_API_KEY", "")
        if single_key:
            for part in re.split(r"[,;\s\n]+", single_key):
                k = part.strip()
                if k and k not in groq_keys:
                    groq_keys.append(k)

        # Check numbered variations: GROQ_API_KEY1..20 and GROQ_API_KEY_1..20
        for i in range(1, 25):
            for var_name in (
                f"GROQ_API_KEY{i}",
                f"GROQ_API_KEY_{i}",
                f"GROQ_KEY_{i}",
                f"GROQ_KEY{i}",
            ):
                val = os.environ.get(var_name, "").strip()
                if val and val not in groq_keys:
                    groq_keys.append(val)

        self._keys["groq"] = groq_keys
        self._key_indices["groq"] = 0
        self._cooldowns["groq"] = {}

        if groq_keys:
            logger.info(
                f"[KeyPool] Loaded {len(groq_keys)} Groq API key(s) into rotation pool."
            )
        else:
            logger.debug("[KeyPool] No Groq API keys found in environment.")

    # -------------------------------------------------------------------------
    # Pool Querying & Rotation
    # -------------------------------------------------------------------------

    def get_all_keys(self, service: str = "groq") -> List[str]:
        """Return all known keys for a service."""
        with self._mu:
            return list(self._keys.get(service, []))

    def count(self, service: str = "groq") -> int:
        """Return total number of keys registered for a service."""
        with self._mu:
            return len(self._keys.get(service, []))

    def get_active_key(self, service: str = "groq") -> str:
        """
        Get the currently active, non-cooldown API key for a service.
        Advances round-robin if the current key is in cooldown.
        Raises RuntimeError if no keys are available.
        """
        with self._mu:
            keys = self._keys.get(service, [])
            if not keys:
                raise RuntimeError(
                    f"No API keys configured for service '{service}'. "
                    f"Set {service.upper()}_API_KEY or {service.upper()}_API_KEYS in .env"
                )

            now = time.time()
            cooldowns = self._cooldowns.setdefault(service, {})

            # Clean expired cooldowns
            expired = [k for k, exp in cooldowns.items() if exp <= now]
            for k in expired:
                del cooldowns[k]

            # Try finding a non-cooldown key starting from current index
            start_idx = self._key_indices.get(service, 0) % len(keys)
            for offset in range(len(keys)):
                idx = (start_idx + offset) % len(keys)
                candidate = keys[idx]
                if candidate not in cooldowns:
                    self._key_indices[service] = idx
                    return candidate

            # If all keys are in cooldown, pick the one that expires soonest
            soonest_key = min(keys, key=lambda k: cooldowns.get(k, 0))
            wait_time = max(0.0, cooldowns.get(soonest_key, 0) - now)
            logger.warning(
                f"[KeyPool] All {len(keys)} {service} keys are rate-limited. "
                f"Using earliest available key (resets in {wait_time:.1f}s)."
            )
            return soonest_key

    @staticmethod
    def get_seconds_until_next_5am_ist() -> float:
        """Calculate seconds until 05:00 AM IST (Indian Standard Time)."""
        import datetime
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset

        # Target next 05:00 AM IST
        target_ist = now_ist.replace(hour=5, minute=0, second=0, microsecond=0)
        if target_ist <= now_ist:
            target_ist += datetime.timedelta(days=1)

        diff = (target_ist - now_ist).total_seconds()
        return max(60.0, diff)

    def mark_rate_limited(
        self,
        key: str,
        cooldown_seconds: Optional[float] = None,
        service: str = "groq",
        is_daily_quota: bool = False,
    ) -> None:
        """
        Mark a key as rate-limited and advance rotation to the next key.
        If is_daily_quota is True, skips the key until next day 5:00 AM IST.
        """
        if is_daily_quota or cooldown_seconds is None:
            cooldown_seconds = self.get_seconds_until_next_5am_ist()

        with self._mu:
            cooldowns = self._cooldowns.setdefault(service, {})
            cooldowns[key] = time.time() + cooldown_seconds

            keys = self._keys.get(service, [])
            if keys:
                current_idx = self._key_indices.get(service, 0)
                self._key_indices[service] = (current_idx + 1) % len(keys)

            masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "key"
            hours_left = cooldown_seconds / 3600.0
            logger.warning(
                f"[KeyPool] Key '{masked}' hit rate limit. Auto-skipped until next day 05:00 AM IST "
                f"({hours_left:.1f}h cooldown). Active pool: {len(keys) - len(cooldowns)}/{len(keys)}"
            )

    def rotate(self, service: str = "groq") -> str:
        """Force advance to the next available key and return it."""
        with self._mu:
            keys = self._keys.get(service, [])
            if keys:
                self._key_indices[service] = (self._key_indices.get(service, 0) + 1) % len(keys)
            return self.get_active_key(service)

    # -------------------------------------------------------------------------
    # Execution Wrapper with Automatic Failover
    # -------------------------------------------------------------------------

    def execute_with_failover(
        self,
        operation: Callable[[str], T],
        service: str = "groq",
        max_retries: Optional[int] = None,
    ) -> T:
        """
        Execute an operation callable that receives `api_key: str`.
        Automatically catches 429 RateLimitErrors, marks the exhausted key,
        rotates to the next key, and retries until all keys have been attempted.
        """
        keys = self.get_all_keys(service)
        if not keys:
            from ai.exceptions import KeyPoolExhaustedError
            raise KeyPoolExhaustedError(f"No API keys configured for {service}.")

        attempts = max_retries or len(keys)
        last_exception: Optional[Exception] = None

        for attempt in range(attempts):
            key = self.get_active_key(service)
            try:
                return operation(key)
            except Exception as exc:
                err_str = str(exc).lower()
                status_code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
                is_rate_limit = (
                    status_code == 429
                    or "429" in err_str
                    or "rate_limit" in err_str
                    or "rate limit" in err_str
                    or "tokens per day" in err_str
                    or "tokens per minute" in err_str
                    or "limit reached for model" in err_str
                    or "tpd" in err_str
                    or "tpm" in err_str
                    or "rpd" in err_str
                    or "quota" in err_str
                )

                if is_rate_limit:
                    last_exception = exc
                    is_daily = (
                        "day" in err_str
                        or "daily" in err_str
                        or "tpd" in err_str
                        or "rpd" in err_str
                        or "limit reached for model" in err_str
                        or "quota" in err_str
                    )

                    if is_daily:
                        cooldown = self.get_seconds_until_next_5am_ist()
                    else:
                        cooldown = 180.0
                        match = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", err_str)
                        if match:
                            try:
                                cooldown = float(match.group(1)) + 5.0
                            except ValueError:
                                pass

                    self.mark_rate_limited(key, cooldown_seconds=cooldown, service=service, is_daily_quota=is_daily)
                    logger.warning(
                        f"[KeyPool] 429 Rate Limit on attempt {attempt+1}/{attempts}. "
                        f"Failing over to next available {service} key."
                    )
                    continue
                else:
                    # Non-rate-limit error: re-raise immediately
                    raise

        from ai.exceptions import KeyPoolExhaustedError
        if last_exception:
            raise KeyPoolExhaustedError(f"All {attempts} {service} keys rate-limited: {last_exception}") from last_exception
        raise KeyPoolExhaustedError(f"Failed to execute operation across all {attempts} {service} keys.")
