"""
AuraAI Live Weather & Geolocation Service
=========================================
Location: src/tools/weather_service.py

Provides zero‑config real‑time IP‑based geolocation and meteorological weather data
with:
1. 30‑second in‑memory caching for location & weather results.
2. Exponential‑backoff retry logic for all external HTTP calls.
3. IP Geolocation (via ip‑api.com with ipapi.co fallback)
4. Live Weather (via Open‑Meteo REST API)
5. WMO Weather code translation into Cyber HUD status & icons
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, Tuple, TypeVar, cast

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# WMO Weather interpretation codes
# --------------------------------------------------------------------------- #
WMO_MAP: Dict[int, Tuple[str, str]] = {
    0: ("CLEAR_SKY.OPTIMAL", "☀"),
    1: ("MAINLY_CLEAR.STABLE", "🌤"),
    2: ("PARTLY_CLOUDY.STABLE", "⛅"),
    3: ("OVERCAST.CLOUDY", "☁"),
    45: ("FOG_MIST.HAZY", "🌫"),
    48: ("DEPOSITING_RIME_FOG", "🌫"),
    51: ("LIGHT_DRIZZLE.ACTIVE", "🌦"),
    53: ("MODERATE_DRIZZLE.ACTIVE", "🌦"),
    55: ("DENSE_DRIZZLE.ACTIVE", "🌧"),
    61: ("SLIGHT_RAIN.ACTIVE", "🌧"),
    63: ("MODERATE_RAIN.ACTIVE", "🌧"),
    65: ("HEAVY_RAIN.ACTIVE", "🌧"),
    71: ("SLIGHT_SNOW.COLD", "🌨"),
    73: ("MODERATE_SNOW.COLD", "🌨"),
    75: ("HEAVY_SNOW.COLD", "❄"),
    80: ("RAIN_SHOWERS.ACTIVE", "🌧"),
    81: ("MODERATE_SHOWERS.ACTIVE", "🌧"),
    82: ("VIOLENT_SHOWERS.CAUTION", "⛈"),
    95: ("THUNDERSTORM.CAUTION", "⛈"),
    96: ("THUNDERSTORM_HAIL.CAUTION", "⛈"),
    99: ("SEVERE_THUNDERSTORM.DANGER", "⛈"),
}

# --------------------------------------------------------------------------- #
# Simple thread‑safe TTL cache
# --------------------------------------------------------------------------- #
_T = TypeVar("_T")


class TTLCache:
    """
    Very small thread‑safe in‑memory cache with a per‑key TTL.
    """

    def __init__(self, ttl: float = 30.0):
        self._ttl = ttl
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts < self._ttl:
                return value
            # expired – purge
            del self._store[key]
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# --------------------------------------------------------------------------- #
# Retry decorator with exponential back‑off + jitter
# --------------------------------------------------------------------------- #
def retry(
    *,
    max_attempts: int = 3,
    backoff_factor: float = 0.5,
    jitter: bool = True,
) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """
    Decorator that retries a callable with exponential back‑off.

    Parameters
    ----------
    max_attempts: int
        Total number of attempts (including the first call).
    backoff_factor: float
        Base delay in seconds.  Actual delay = backoff_factor * (2 ** (attempt-1)).
    jitter: bool
        If True, adds a random jitter up to 30 % of the calculated delay.
    """

    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        def wrapper(*args: Any, **kwargs: Any) -> _T:
            attempt = 0
            while True:
                try:
                    return cast(_T, func(*args, **kwargs))
                except Exception as exc:  # pragma: no cover – logging only
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.debug(
                            f"[{func.__name__}] Exhausted retries after {attempt} attempts: {exc}"
                        )
                        raise
                    delay = backoff_factor * (2 ** (attempt - 1))
                    if jitter:
                        delay *= random.uniform(0.7, 1.3)
                    logger.debug(
                        f"[{func.__name__}] Retry {attempt}/{max_attempts} after {delay:.2f}s – {exc}"
                    )
                    time.sleep(delay)

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Core HTTP JSON fetcher (with retry)
# --------------------------------------------------------------------------- #
@retry(max_attempts=3, backoff_factor=0.5, jitter=True)
def _fetch_json(
    url: str,
    headers: Dict[str, str] | None = None,
    timeout: float = 4.0,
) -> Dict[str, Any]:
    """
    Perform an HTTP GET request and return the parsed JSON payload.

    The function is wrapped by :func:`retry` to provide exponential back‑off.
    """
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload)


# --------------------------------------------------------------------------- #
# Core service
# --------------------------------------------------------------------------- #
class LiveWeatherService:
    """
    Service to fetch live location and real‑time weather.

    Results are cached in‑memory for 30 seconds to minimise external calls.
    """

    # Shared caches (class‑level)
    _location_cache = TTLCache(ttl=30.0)
    _weather_cache = TTLCache(ttl=30.0)

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    @classmethod
    def get_live_location(cls) -> Dict[str, Any]:
        """
        Return a dictionary with the current IP‑based location.

        The result is cached for 30 seconds.
        """
        cached = cls._location_cache.get("location")
        if cached is not None:
            logger.debug("[LiveWeatherService] Returning cached location")
            return cast(Dict[str, Any], cached)

        # ----------------------------------------------------------------- #
        # Default fallback – static Bengaluru data
        # ----------------------------------------------------------------- #
        location: Dict[str, Any] = {
            "city": "Bengaluru",
            "region": "Karnataka",
            "country": "India",
            "lat": 12.9716,
            "lon": 77.5946,
            "timezone": "Asia/Kolkata",
        }

        # ----------------------------------------------------------------- #
        # 1️⃣ ip‑api.com (primary)
        # ----------------------------------------------------------------- #
        try:
            data = _fetch_json(
                "http://ip-api.com/json/",
                headers={"User-Agent": "AuraAI/1.0", "Accept": "application/json"},
                timeout=3.5,
            )
            if data.get("status") == "success":
                location.update(
                    {
                        "city": data.get("city", location["city"]),
                        "region": data.get("regionName", location["region"]),
                        "country": data.get("country", location["country"]),
                        "lat": float(data.get("lat", location["lat"])),
                        "lon": float(data.get("lon", location["lon"])),
                        "timezone": data.get("timezone", location["timezone"]),
                    }
                )
                logger.debug("[LiveWeatherService] Location resolved via ip-api.com")
                cls._location_cache.set("location", location)
                return location
        except Exception as exc:  # pragma: no cover
            logger.debug(f"[LiveWeatherService] ip-api.com lookup failed: {exc}")

        # ----------------------------------------------------------------- #
        # 2️⃣ ipapi.co (fallback)
        # ----------------------------------------------------------------- #
        try:
            data = _fetch_json(
                "https://ipapi.co/json/",
                headers={"User-Agent": "AuraAI/1.0", "Accept": "application/json"},
                timeout=3.5,
            )
            if "city" in data:
                location.update(
                    {
                        "city": data.get("city", location["city"]),
                        "region": data.get("region", location["region"]),
                        "country": data.get("country_name", location["country"]),
                        "lat": float(data.get("latitude", location["lat"])),
                        "lon": float(data.get("longitude", location["lon"])),
                        "timezone": data.get("timezone", location["timezone"]),
                    }
                )
                logger.debug("[LiveWeatherService] Location resolved via ipapi.co")
        except Exception as exc:  # pragma: no cover
            logger.debug(f"[LiveWeatherService] ipapi.co lookup failed: {exc}")

        # Cache the (possibly default) result
        cls._location_cache.set("location", location)
        return location

    @classmethod
    def get_live_weather(
        cls,
        lat: float | None = None,
        lon: float | None = None,
    ) -> Dict[str, Any]:
        """
        Return a dictionary with the current weather for the detected location.

        The result is cached for 30 seconds.
        """
        cache_key = f"weather:{lat}:{lon}"
        cached = cls._weather_cache.get(cache_key)
        if cached is not None:
            logger.debug("[LiveWeatherService] Returning cached weather")
            return cast(Dict[str, Any], cached)

        # Resolve location if coordinates not supplied
        loc = cls.get_live_location()
        if lat is None or lon is None:
            lat, lon = loc["lat"], loc["lon"]
        city = loc["city"].upper()

        # ----------------------------------------------------------------- #
        # Base payload – will be overwritten by the API response when successful
        # ----------------------------------------------------------------- #
        weather: Dict[str, Any] = {
            "location": f"{city} // SECTOR {lat:.2f}N {lon:.2f}E",
            "city": loc["city"],
            "region": loc["region"],
            "country": loc["country"],
            "lat": lat,
            "lon": lon,
            "temp_c": 24,
            "condition": "PARTLY_CLOUDY.STATUS",
            "icon": "☁",
            "high": 28,
            "low": 20,
            "humidity": 65,
            "wind_kmh": 12,
            "aqi": 42,
            "uv": 4,
        }

        # ----------------------------------------------------------------- #
        # Open‑Meteo request (with retry/back‑off)
        # ----------------------------------------------------------------- #
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                "&daily=temperature_2m_max,temperature_2m_min,uv_index_max"
                "&timezone=auto"
            )
            data = _fetch_json(
                url,
                headers={"User-Agent": "AuraAI/1.0", "Accept": "application/json"},
                timeout=4.0,
            )

            current = data.get("current", {})
            daily = data.get("daily", {})

            temp_c = round(current.get("temperature_2m", weather["temp_c"]))
            humidity = round(current.get("relative_humidity_2m", weather["humidity"]))
            wind_kmh = round(current.get("wind_speed_10m", weather["wind_kmh"]))
            code = int(current.get("weather_code", 2))

            condition_str, icon_str = WMO_MAP.get(code, ("DYNAMIC_WEATHER.STATUS", "☁"))

            high_list = daily.get("temperature_2m_max", [temp_c + 3])
            low_list = daily.get("temperature_2m_min", [temp_c - 3])
            uv_list = daily.get("uv_index_max", [4])

            weather.update(
                {
                    "temp_c": temp_c,
                    "humidity": humidity,
                    "wind_kmh": wind_kmh,
                    "condition": condition_str,
                    "icon": icon_str,
                    "high": round(high_list[0]) if high_list else temp_c + 3,
                    "low": round(low_list[0]) if low_list else temp_c - 3,
                    "uv": round(uv_list[0]) if uv_list else 4,
                }
            )
            logger.info(
                f"[LiveWeatherService] Live weather fetched for {city}: {temp_c}°C, {condition_str}"
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(f"[LiveWeatherService] Open-Meteo fetch failed: {exc}")

        # Cache the final payload (key includes coordinates for possible overrides)
        cls._weather_cache.set(cache_key, weather)
        return weather
