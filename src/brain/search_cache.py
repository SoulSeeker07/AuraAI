from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class SearchCache:
    """
    Smart caching system for search results with different TTLs.
    Caches search results to avoid redundant searches and API calls.
    """

    # Cache TTL configurations in minutes
    CACHE_TTL = {
        "weather": 10,
        "news": 30,
        "stock": 5,
        "crypto": 5,
        "live_information": 10,
        "time_date": 1,
        "default": 15,  # Default TTL for general queries
    }

    def __init__(self, cache_dir: Path | None = None):
        """
        Initialize the search cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir or Path("Data/search_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_stats = {"hits": 0, "misses": 0, "errors": 0}

    def _get_cache_key(self, query: str, category: str = "default") -> str:
        """
        Generate a cache key for a query.

        Args:
            query: Search query
            category: Query category

        Returns:
            Cache key string
        """
        # Normalize query: lower case, strip whitespace
        normalized_query = query.strip().lower()

        # Create unique hash
        hash_input = f"{category}:{normalized_query}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def _get_cache_file(self, cache_key: str) -> Path:
        """
        Get the file path for a cache entry.

        Args:
            cache_key: Cache key

        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{cache_key}.json"

    def _get_ttl(self, category: str) -> int:
        """
        Get TTL for a category in minutes.

        Args:
            category: Query category

        Returns:
            TTL in minutes
        """
        return self.CACHE_TTL.get(category, self.CACHE_TTL["default"])

    def get(
        self, query: str, category: str = "default", ttl_override: int | None = None
    ) -> dict[str, Any] | None:
        """
        Get cached search results if available and not expired.

        Args:
            query: Search query
            category: Query category
            ttl_override: Override TTL (minutes)

        Returns:
            Cached results dict or None if not found/expired
        """
        cache_key = self._get_cache_key(query, category)
        cache_file = self._get_cache_file(cache_key)

        if not cache_file.exists():
            self._cache_stats["misses"] += 1
            return None

        try:
            with open(cache_file, encoding="utf-8") as f:
                cached_data = json.load(f)

            # Check if expired
            expires_at = datetime.fromisoformat(cached_data.get("expires_at"))
            current_time = datetime.now()

            if current_time > expires_at:
                cache_file.unlink()  # Remove expired cache
                self._cache_stats["misses"] += 1
                return None

            # Cache hit
            self._cache_stats["hits"] += 1
            return cached_data["results"]

        except (OSError, json.JSONDecodeError):
            self._cache_stats["errors"] += 1
            return None

    def set(
        self,
        query: str,
        results: list[dict[str, Any]],
        category: str = "default",
        ttl_override: int | None = None,
    ) -> None:
        """
        Cache search results.

        Args:
            query: Search query
            results: Search results to cache
            category: Query category
            ttl_override: Override TTL (minutes)
        """
        cache_key = self._get_cache_key(query, category)
        cache_file = self._get_cache_file(cache_key)

        # Calculate expiration time
        ttl = ttl_override or self._get_ttl(category)
        expires_at = datetime.now() + timedelta(minutes=ttl)

        cache_data = {
            "query": query,
            "results": results,
            "category": category,
            "expires_at": expires_at.isoformat(),
            "cached_at": datetime.now().isoformat(),
        }

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"Warning: Could not save cache: {exc}")

    def invalidate(self, query: str, category: str = "default") -> None:
        """
        Invalidate a cache entry.

        Args:
            query: Search query
            category: Query category
        """
        cache_key = self._get_cache_key(query, category)
        cache_file = self._get_cache_file(cache_key)

        if cache_file.exists():
            cache_file.unlink()

    def invalidate_category(self, category: str) -> None:
        """
        Invalidate all cache entries for a category.

        Args:
            category: Query category
        """
        pattern = f"*{self._get_cache_key('', category)}.json"
        import glob

        for cache_file in glob.glob(str(self.cache_dir / pattern)):
            try:
                Path(cache_file).unlink()
            except OSError:
                pass

    def clear_all(self) -> None:
        """Clear all cached entries."""
        import glob

        for cache_file in glob.glob(str(self.cache_dir / "*.json")):
            try:
                Path(cache_file).unlink()
            except OSError:
                pass

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = (
            self._cache_stats["hits"] / total_requests * 100
            if total_requests > 0
            else 0
        )

        return {
            **self._cache_stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "cache_dir": str(self.cache_dir),
        }

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        import glob

        removed = 0
        current_time = datetime.now()

        pattern = "*.json"
        for cache_file in glob.glob(str(self.cache_dir / pattern)):
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cached_data = json.load(f)

                expires_at = datetime.fromisoformat(cached_data.get("expires_at"))

                if current_time > expires_at:
                    Path(cache_file).unlink()
                    removed += 1

            except (OSError, json.JSONDecodeError):
                continue

        return removed
