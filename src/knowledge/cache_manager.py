"""
Cache Manager - Manages search result caching.

This module stores search results to avoid redundant searches and improve performance:

    Before (Milestone 1-2):
        User asks: "Latest Python version"
        Search again -> Get result

        Ten minutes later...
        User asks: "Latest Python version"
        Search again -> Get result (WASTE!)

    After (Milestone 3):
        User asks: "Latest Python version"
        Search -> Store result in cache

        Ten minutes later...
        User asks: "Latest Python version"
        Check cache -> Found! Return immediately

Cache levels:
    - Memory cache (fast, in-memory)
    - Disk cache (persistent, SQLite)
    - Category-based expiry (news expires faster than docs)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class CachedSearchResult:
    """A cached search result."""

    query: str
    results: list[dict[str, Any]]
    timestamp: str
    category: str
    expires: str
    source: str
    query_hash: str = ""  # For faster lookup

    def __post_init__(self):
        if not self.query_hash:
            self.query_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Calculate a hash for the query for fast lookup."""
        query_str = f"{self.query}_{self.category}"
        return hashlib.md5(query_str.encode()).hexdigest()

    def is_valid(self) -> bool:
        """Check if cache entry is still valid."""
        try:
            expiry = datetime.strptime(self.expires, "%Y-%m-%d %H:%M:%S")
            return datetime.now() < expiry
        except (ValueError, AttributeError):
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class CacheManager:
    """
    Manages search result caching to avoid redundant searches.

    Features:
    - In-memory cache for fast access
    - Disk cache for persistence
    - Category-based expiry times
    - Automatic cleanup of stale entries
    - Cache statistics
    - Support for multiple cache levels
    """

    # Default expiry times (in minutes)
    CACHE_EXPIRY_MAP: dict[str, int] = {
        "News": 60,  # 1 hour
        "Weather": 10,  # 10 minutes
        "Technology": 1440,  # 1 day
        "Programming": 4320,  # 3 days
        "Networking": 4320,  # 3 days
        "AI": 1440,  # 1 day
        "General": 360,  # 6 hours
        "Weather": 10,  # 10 minutes
    }

    def __init__(self, memory_cache_size: int = 1000, cache_db_path: str = "cache.db"):
        """
        Initialize cache manager.

        Args:
            memory_cache_size: Maximum number of items in memory cache
            cache_db_path: Path to cache database file
        """
        self.memory_cache_size = memory_cache_size
        self.cache_db_path = cache_db_path
        self._lock = threading.Lock()

        # Initialize memory cache (LRU cache)
        self._memory_cache: dict[str, CachedSearchResult] = {}

        # Initialize disk cache
        self._initialize_cache_database()

    def _initialize_cache_database(self):
        """Initialize cache database."""
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT NOT NULL,
                    query TEXT NOT NULL,
                    category TEXT NOT NULL,
                    results TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    expires TEXT NOT NULL,
                    source TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_hash ON cache(query_hash)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON cache(timestamp)
            """)

            conn.commit()
            conn.close()

    def _get_expiry(self, category: str) -> int:
        """
        Get cache expiry time for a category.

        Args:
            category: Category name

        Returns:
            Expiry time in minutes
        """
        return self.CACHE_EXPIRY_MAP.get(category, 360)  # Default 6 hours

    def _get_key(self, query: str, category: str) -> str:
        """
        Generate cache key.

        Args:
            query: Search query
            category: Category

        Returns:
            Cache key string
        """
        return f"{query}:{category}"

    def cache_search_result(
        self,
        query: str,
        results: list[dict[str, Any]],
        category: str = "General",
        source: str = "web",
    ) -> str:
        """
        Cache a search result.

        Args:
            query: Search query
            results: Search results list
            category: Category (affects expiry time)
            source: Source of results

        Returns:
            Cache entry ID
        """
        cache_entry = CachedSearchResult(
            query=query,
            results=results,
            category=category,
            source=source,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            expires=(
                datetime.now() + timedelta(minutes=self._get_expiry(category))
            ).strftime("%Y-%m-%d %H:%M:%S"),
        )

        cache_key = self._get_key(query, category)

        # Add to memory cache
        self._memory_cache[cache_key] = cache_entry

        # Prune memory cache if needed
        if len(self._memory_cache) > self.memory_cache_size:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]

        # Add to disk cache
        self._save_to_disk_cache(cache_entry)

        return cache_entry.query_hash

    def get_cached_result(
        self, query: str, category: str = "General"
    ) -> list[dict[str, Any]] | None:
        """
        Get cached search results if available.

        Args:
            query: Search query
            category: Category

        Returns:
            Cached results or None if not found/expired
        """
        cache_key = self._get_key(query, category)

        # Check memory cache first
        if cache_key in self._memory_cache:
            cache_entry = self._memory_cache[cache_key]
            if cache_entry.is_valid():
                return cache_entry.results

        # Check disk cache
        return self._get_from_disk_cache(query, category)

    def _get_from_disk_cache(
        self, query: str, category: str
    ) -> list[dict[str, Any]] | None:
        """
        Get result from disk cache.

        Args:
            query: Search query
            category: Category

        Returns:
            Cached results or None
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT results, expires FROM cache
                    WHERE query=? AND category=?
                """,
                    (query, category),
                )

                row = cursor.fetchone()
                conn.close()

                if row:
                    results_json, expires = row
                    expiry = datetime.strptime(expires, "%Y-%m-%d %H:%M:%S")

                    if datetime.now() < expiry:
                        results = json.loads(results_json)
                        return results

                return None

            except Exception as e:
                print(f"[CacheManager] Error getting from disk cache: {e}")
                return None

    def _save_to_disk_cache(self, cache_entry: CachedSearchResult) -> None:
        """
        Save cache entry to disk.

        Args:
            cache_entry: CachedSearchResult to save
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO cache (query_hash, query, category, results, timestamp, expires, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cache_entry.query_hash,
                        cache_entry.query,
                        cache_entry.category,
                        json.dumps(cache_entry.results),
                        cache_entry.timestamp,
                        cache_entry.expires,
                        cache_entry.source,
                    ),
                )

                conn.commit()
                conn.close()

            except Exception as e:
                print(f"[CacheManager] Error saving to disk cache: {e}")

    def invalidate_query(self, query: str, category: str = "General") -> bool:
        """
        Invalidate cache for a specific query.

        Args:
            query: Search query
            category: Category

        Returns:
            True if invalidated
        """
        cache_key = self._get_key(query, category)

        # Remove from memory cache
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]

        # Remove from disk cache
        return self._delete_from_disk_cache(query, category)

    def _delete_from_disk_cache(self, query: str, category: str) -> bool:
        """
        Delete from disk cache.

        Args:
            query: Search query
            category: Category

        Returns:
            True if deleted
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    DELETE FROM cache WHERE query=? AND category=?
                """,
                    (query, category),
                )

                deleted = cursor.rowcount > 0
                conn.commit()
                conn.close()

                return deleted

            except Exception as e:
                print(f"[CacheManager] Error deleting from disk cache: {e}")
                return False

    def invalidate_category(self, category: str) -> int:
        """
        Invalidate all cache entries for a category.

        Args:
            category: Category name

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute("DELETE FROM cache WHERE category=?", (category,))
                deleted = cursor.rowcount

                conn.commit()
                conn.close()

                return deleted

            except Exception as e:
                print(f"[CacheManager] Error invalidating category: {e}")
                return 0

    def clear_all(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._memory_cache.clear()

            try:
                conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute("DELETE FROM cache")
                conn.commit()
                conn.close()

            except Exception as e:
                print(f"[CacheManager] Error clearing all cache: {e}")

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            # Memory cache stats
            memory_stats = {
                "total_entries": len(self._memory_cache),
                "memory_cache_size": self.memory_cache_size,
            }

            # Disk cache stats
            try:
                conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN expires < CURRENT_TIMESTAMP THEN 1 ELSE 0 END) FROM cache"
                )
                total, expired = cursor.fetchone()
                conn.close()

                disk_stats = {"total_entries": total, "expired_entries": expired}
            except Exception:
                disk_stats = {"total_entries": 0, "expired_entries": 0}

            return {
                "memory_cache": memory_stats,
                "disk_cache": disk_stats,
                "cache_levels": "memory + disk",
            }

    def cleanup_expired_entries(self) -> int:
        """
        Remove expired entries from disk cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute("DELETE FROM cache WHERE expires < CURRENT_TIMESTAMP")
                removed = cursor.rowcount

                conn.commit()
                conn.close()

                return removed

            except Exception as e:
                print(f"[CacheManager] Error cleaning up expired entries: {e}")
                return 0

    def get_most_requested_queries(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get the most requested queries (from disk cache).

        Args:
            limit: Maximum number of queries

        Returns:
            List of query statistics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.cache_db_path, check_same_thread=False)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT query, COUNT(*) as request_count
                    FROM cache
                    GROUP BY query
                    ORDER BY request_count DESC
                    LIMIT ?
                """,
                    (limit,),
                )

                rows = cursor.fetchall()
                conn.close()

                return [{"query": row[0], "request_count": row[1]} for row in rows]

            except Exception as e:
                print(f"[CacheManager] Error getting most requested queries: {e}")
                return []

    def batch_cache_results(self, cache_entries: list[dict[str, Any]]) -> int:
        """
        Batch cache multiple search results.

        Args:
            cache_entries: List of dictionaries with query, results, category, source

        Returns:
            Number of entries cached
        """
        cached = 0

        for entry in cache_entries:
            query = entry.get("query", "")
            results = entry.get("results", [])
            category = entry.get("category", "General")
            source = entry.get("source", "web")

            if query and results:
                self.cache_search_result(query, results, category, source)
                cached += 1

        return cached
