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

    def __init__(
        self,
        explicit_keys: Optional[Dict[str, List[str]]] = None,
        persist_cooldowns: Optional[bool] = None,
    ):
        from pathlib import Path

        self._keys: Dict[str, List[str]] = {}
        self._key_indices: Dict[str, int] = {}
        self._cooldowns: Dict[str, Dict[str, float]] = {}  # service -> {key: expire_timestamp}
        self._groq_clients: Dict[str, Any] = {}
        self._mu = threading.RLock()
        self._cooldown_file = Path(__file__).resolve().parents[2] / "Data" / "key_cooldowns.json"
        self._persist_cooldowns = (
            persist_cooldowns if persist_cooldowns is not None else (explicit_keys is None)
        )

        if explicit_keys:
            for service, keys in explicit_keys.items():
                self._keys[service] = [k.strip() for k in keys if k and k.strip()]
                self._key_indices[service] = 0
                self._cooldowns[service] = {}
        else:
            self._discover_keys()

        if self._persist_cooldowns:
            self._load_cooldowns()

    def _load_cooldowns(self) -> None:
        """Load unexpired cooldown timestamps from persistent disk file."""
        import json
        with self._mu:
            try:
                if self._cooldown_file.exists():
                    data = json.loads(self._cooldown_file.read_text(encoding="utf-8"))
                    now = time.time()
                    loaded_count = 0
                    for service, c_map in data.items():
                        if isinstance(c_map, dict):
                            svc_map = self._cooldowns.setdefault(service, {})
                            for k, exp in c_map.items():
                                if isinstance(exp, (int, float)) and exp > now:
                                    svc_map[k] = float(exp)
                                    loaded_count += 1
                    if loaded_count > 0:
                        logger.info(f"[KeyPool] Loaded {loaded_count} active cooldown timer(s) from disk.")
            except Exception as e:
                logger.debug(f"[KeyPool] Failed loading cooldowns from disk: {e}")

    def _save_cooldowns(self) -> None:
        """Persist active cooldown timestamps to disk."""
        if not self._persist_cooldowns:
            return
        import json
        with self._mu:
            try:
                self._cooldown_file.parent.mkdir(parents=True, exist_ok=True)
                now = time.time()
                serializable = {}
                for service, c_map in self._cooldowns.items():
                    active_entries = {k: exp for k, exp in c_map.items() if exp > now}
                    if active_entries:
                        serializable[service] = active_entries
                self._cooldown_file.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
            except Exception as e:
                logger.debug(f"[KeyPool] Failed saving cooldowns to disk: {e}")


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
            from pathlib import Path
            project_env = Path(__file__).resolve().parents[2] / ".env"
            if project_env.exists():
                load_dotenv(dotenv_path=project_env, override=False)
                logger.debug(f"[KeyPool] Loaded .env from explicit project path: {project_env}")
            else:
                load_dotenv()
        except Exception as e:
            logger.debug(f"[KeyPool] load_dotenv notice: {e}")

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

        # 2. Discover Gemini keys
        gemini_keys: List[str] = []
        multi_gemini = os.environ.get("GEMINI_API_KEYS", "")
        if multi_gemini:
            for part in re.split(r"[,;\s\n]+", multi_gemini):
                k = part.strip()
                if k and k not in gemini_keys:
                    gemini_keys.append(k)

        single_gemini = os.environ.get("GEMINI_API_KEY", "")
        if single_gemini:
            for part in re.split(r"[,;\s\n]+", single_gemini):
                k = part.strip()
                if k and k not in gemini_keys:
                    gemini_keys.append(k)

        for i in range(1, 25):
            for var_name in (
                f"GEMINI_API_KEY{i}",
                f"GEMINI_API_KEY_{i}",
                f"GEMINI_KEY_{i}",
                f"GEMINI_KEY{i}",
            ):
                val = os.environ.get(var_name, "").strip()
                if val and val not in gemini_keys:
                    gemini_keys.append(val)

        self._keys["gemini"] = gemini_keys
        self._key_indices["gemini"] = 0
        self._cooldowns["gemini"] = {}

        if gemini_keys:
            logger.info(
                f"[KeyPool] Loaded {len(gemini_keys)} Gemini API key(s) into rotation pool."
            )
        else:
            logger.debug("[KeyPool] No Gemini API keys found in environment.")


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

    def get_groq_client(self, api_key: str):
        """Return a persistent cached Groq client instance for an API key, reusing connection pools."""
        with self._mu:
            client = self._groq_clients.get(api_key)
            if client is None:
                from groq import Groq
                client = Groq(api_key=api_key)
                self._groq_clients[api_key] = client
            return client


    def get_active_key(self, service: str = "groq", allow_cooldown: bool = False) -> str:
        """
        Get the currently active, non-cooldown API key for a service.
        Advances round-robin if the current key is in cooldown.
        If allow_cooldown is False and all keys are on cooldown, raises KeyPoolExhaustedError immediately.
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
            if expired:
                for k in expired:
                    del cooldowns[k]
                self._save_cooldowns()

            # Try finding a non-cooldown key starting from current index
            start_idx = self._key_indices.get(service, 0) % len(keys)
            for offset in range(len(keys)):
                idx = (start_idx + offset) % len(keys)
                candidate = keys[idx]
                if candidate not in cooldowns:
                    self._key_indices[service] = idx
                    return candidate

            # If all keys are in cooldown:
            soonest_key = min(keys, key=lambda k: cooldowns.get(k, 0))
            wait_time = max(0.0, cooldowns.get(soonest_key, 0) - now)
            if not allow_cooldown:
                from ai.exceptions import KeyPoolExhaustedError
                raise KeyPoolExhaustedError(
                    f"All {len(keys)} {service} API keys are currently rate-limited. "
                    f"Earliest key resets in {wait_time:.1f}s."
                )

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
        if is_daily_quota:
            cooldown_seconds = self.get_seconds_until_next_5am_ist()
        elif cooldown_seconds is None:
            cooldown_seconds = 15.0

        with self._mu:
            cooldowns = self._cooldowns.setdefault(service, {})
            cooldowns[key] = time.time() + cooldown_seconds

            keys = self._keys.get(service, [])
            if keys:
                current_idx = self._key_indices.get(service, 0)
                self._key_indices[service] = (current_idx + 1) % len(keys)

            self._save_cooldowns()

            masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "key"
            if is_daily_quota or cooldown_seconds >= 3600.0:
                hours_left = cooldown_seconds / 3600.0
                logger.warning(
                    f"[KeyPool] Key '{masked}' hit DAILY quota. Auto-skipped until next day 05:00 AM IST "
                    f"({hours_left:.1f}h cooldown). Active pool: {len(keys) - len(cooldowns)}/{len(keys)}"
                )
            else:
                logger.warning(
                    f"[KeyPool] Key '{masked}' hit TPM/RPM burst rate limit. Auto-skipped for {cooldown_seconds:.1f}s. "
                    f"Active pool: {len(keys) - len(cooldowns)}/{len(keys)}"
                )

    def rotate(self, service: str = "groq") -> str:
        """Force advance to the next available key and return it."""
        with self._mu:
            keys = self._keys.get(service, [])
            if keys:
                self._key_indices[service] = (self._key_indices.get(service, 0) + 1) % len(keys)
            return self.get_active_key(service, allow_cooldown=True)

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
        rotates to the next key, and retries across available non-cooldown keys.
        If all keys are already in cooldown, fails fast immediately without wasting network calls.
        """
        keys = self.get_all_keys(service)
        if not keys:
            from ai.exceptions import KeyPoolExhaustedError
            raise KeyPoolExhaustedError(f"No API keys configured for {service}.")

        now = time.time()
        with self._mu:
            cooldowns = self._cooldowns.setdefault(service, {})
            expired = [k for k, exp in cooldowns.items() if exp <= now]
            if expired:
                for k in expired:
                    del cooldowns[k]
                self._save_cooldowns()

            # Fast check: Are ALL keys currently on cooldown?
            non_cooldown_keys = [k for k in keys if k not in cooldowns]
            if not non_cooldown_keys:
                soonest_key = min(keys, key=lambda k: cooldowns.get(k, 0))
                wait_time = max(0.0, cooldowns.get(soonest_key, 0) - now)
                from ai.exceptions import KeyPoolExhaustedError
                raise KeyPoolExhaustedError(
                    f"All {len(keys)} {service} API keys are currently rate-limited on cooldown "
                    f"(earliest key resets in {wait_time:.1f}s)."
                )

        attempts = max_retries or len(keys)
        tried_keys: set[str] = set()
        last_exception: Optional[Exception] = None

        for attempt in range(attempts):
            # Select next available non-cooldown key that hasn't been tried yet in this invocation
            key: Optional[str] = None
            with self._mu:
                now = time.time()
                cooldowns = self._cooldowns.setdefault(service, {})
                for k in [k for k, exp in cooldowns.items() if exp <= now]:
                    del cooldowns[k]

                start_idx = self._key_indices.get(service, 0) % len(keys)
                for offset in range(len(keys)):
                    idx = (start_idx + offset) % len(keys)
                    cand = keys[idx]
                    if cand not in cooldowns and cand not in tried_keys:
                        key = cand
                        self._key_indices[service] = idx
                        break

            if key is None:
                # No more non-cooldown keys available to try
                break

            tried_keys.add(key)
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
                    or "requests per minute" in err_str
                    or "requests per day" in err_str
                    or "tpd" in err_str
                    or "tpm" in err_str
                    or "rpd" in err_str
                    or "rpm" in err_str
                    or "quota" in err_str
                )

                if is_rate_limit:
                    last_exception = exc
                    # Precise classification: Daily quota vs TPM/RPM burst limit
                    is_daily = (
                        "tokens per day" in err_str
                        or "requests per day" in err_str
                        or "tpd" in err_str
                        or "rpd" in err_str
                        or ("daily" in err_str and not any(m in err_str for m in ("minute", "tpm", "rpm")))
                    )

                    if is_daily:
                        cooldown = self.get_seconds_until_next_5am_ist()
                    else:
                        cooldown = 15.0
                        # Parse seconds like: "try again in 2.45s" or "try again in 2s"
                        match_s = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", err_str)
                        # Parse minutes like: "try again in 1m20s"
                        match_m = re.search(r"try again in (\d+)\s*m\s*(\d+(?:\.\d+)?)\s*s", err_str)
                        if match_s:
                            try:
                                cooldown = float(match_s.group(1)) + 2.0  # safe small buffer
                            except ValueError:
                                pass
                        elif match_m:
                            try:
                                cooldown = float(match_m.group(1)) * 60.0 + float(match_m.group(2)) + 2.0
                            except ValueError:
                                pass

                    self.mark_rate_limited(key, cooldown_seconds=cooldown, service=service, is_daily_quota=is_daily)
                    logger.warning(
                        f"[KeyPool] 429 Rate Limit on attempt {attempt+1}/{attempts} "
                        f"({'Daily Quota' if is_daily else f'TPM/RPM wait {cooldown:.1f}s'}). "
                        f"Auto-skipping to next available {service} key."
                    )
                    continue
                else:
                    # Non-rate-limit error: re-raise immediately
                    raise

        from ai.exceptions import KeyPoolExhaustedError
        if last_exception:
            raise KeyPoolExhaustedError(
                f"All available {service} keys rate-limited (attempted {len(tried_keys)} keys): {last_exception}"
            ) from last_exception
        raise KeyPoolExhaustedError(f"Failed to execute operation across all {len(keys)} {service} keys.")
