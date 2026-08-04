"""
Cache Manager

Manages caching of research results to avoid redundant searches.
"""

import logging
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta

from .models import ResearchReport, SearchQuery

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching of research results.

    Implements Smart Cache with content-type-based TTLs to optimize
    cache lifetime based on how often information changes.
    """

    # Content type to TTL mapping (in seconds)
    CONTENT_TYPE_TTL = {
        'stocks': 60,            # 1 minute
        'crypto': 30,            # 30 seconds
        'github': 86400,         # 1 day
        'github_releases': 86400, # 1 day
        'github_release': 86400,  # 1 day
        'wikipedia': 2592000,    # 30 days
        'wiki': 2592000,         # 30 days
        'docs': 604800,          # 7 days
        'official_docs': 604800, # 7 days
        'rfc': 31536000,         # 365 days
        'rfc_editor': 31536000,  # 365 days
        'news': 900,             # 15 minutes
        'breaking_news': 900,    # 15 minutes
        'stackoverflow': 1209600, # 14 days
        'stack_overflow': 1209600, # 14 days
        'tech_blog': 7200,       # 2 hours
        'general': 1800,         # 30 minutes (default)
    }

    def __init__(self, ttl: int = None):
        """
        Initialize the cache manager.

        Args:
            ttl: Time-to-live in seconds (default: content-type-based TTL)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_dir = Path("Data/cache/research")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = ttl if ttl is not None else self.CONTENT_TYPE_TTL['general']

    def get(self, key: str, query_obj: Optional[SearchQuery] = None) -> Optional[ResearchReport]:
        """
        Get a cached report with content-type-based TTL validation.

        Args:
            key: Cache key
            query_obj: Optional search query for determining content type

        Returns:
            Cached ResearchReport or None if not found/expired
        """
        if key not in self.cache:
            return None

        cached = self.cache[key]
        timestamp = cached.get("timestamp")

        # Get the appropriate TTL based on content type
        content_type = cached.get("content_type", "general")
        ttl = self._get_ttl_for_content_type(content_type)

        if timestamp:
            age = time.time() - timestamp
            if age > ttl:
                logger.debug(f"Cache entry expired (content_type: {content_type}, ttl: {ttl}s, age: {age:.1f}s): {key}")
                del self.cache[key]
                return None

        # Load from disk if not in memory
        if not cached.get("in_memory"):
            cached_data = self._load_from_disk(key)
            if cached_data:
                self.cache[key] = cached_data
                return ResearchReport.from_dict(self._to_report_dict(cached_data))

        return ResearchReport.from_dict(self._to_report_dict(cached))

    def _to_report_dict(self, cached: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a raw cache entry into a dict safe for ResearchReport.from_dict().

        The cache stores "timestamp" as a Unix epoch float for TTL/age math,
        but ResearchReport.from_dict() expects "timestamp" as an ISO-format
        string (matching what ResearchReport.to_dict() produces). This
        translates between the two without mutating the original cache entry.

        Args:
            cached: Raw cache entry dict

        Returns:
            A copy of the dict with "timestamp" converted to an ISO string
        """
        report_dict = dict(cached)
        timestamp = report_dict.get("timestamp")
        if isinstance(timestamp, (int, float)):
            report_dict["timestamp"] = datetime.fromtimestamp(timestamp).isoformat()
        return report_dict

    def set(
        self,
        key: str,
        report: Optional[ResearchReport],
        results: Optional[List] = None,
        query_obj: Optional[SearchQuery] = None,
    ) -> None:
        """
        Cache a research report.

        Args:
            key: Cache key
            report: Research report to cache. Can be None if you only want to
                cache raw `results` (e.g. before a full report has been built).
            results: Optional raw search results. Used when `report` is None,
                or to override `report.results` for content-type detection.
            query_obj: Optional search query, used to determine content type
                (and therefore TTL) for this cache entry. If omitted, the
                entry defaults to the 'general' content type.
        """
        # Determine which results to use for content-type detection and storage
        results_list = results if results else (report.results if report else [])

        cache_data = {
            "query": report.query if report else (query_obj.query_text if query_obj else ""),
            "results": [r.to_dict() if hasattr(r, 'to_dict') else r for r in results_list],
            "merged_evidence": report.merged_evidence if report else [],
            "citations": [c.to_dict() for c in report.citations] if report else [],
            "conflicts": report.conflicts if report else [],
            "primary_sources": report.primary_sources if report else [],
            "summary": report.summary if report else None,
            "detailed_findings": report.detailed_findings if report else {},
            "key_stats": report.key_stats if report else {},
            "timestamp": time.time(),
            "duration": report.duration if report else 0.0,
            "metadata": report.metadata if report else {},
            "confidence_score": report.get_confidence_score() if report else 0.0,
            "in_memory": True,
            "content_type": "general",
        }

        # Determine content type from the query and/or results, if available
        if query_obj is not None:
            content_type = self._get_content_type(query_obj, results_list)
            cache_data["content_type"] = content_type

        self.cache[key] = cache_data
        self._save_to_disk(key, cache_data)
        logger.debug(f"Cached research for: {cache_data['query']}")

    def has_cache(self, key: str) -> bool:
        """
        Check if a cache entry exists and is valid.

        Args:
            key: Cache key

        Returns:
            True if cache exists and is valid
        """
        return self.get(key) is not None

    def invalidate(self, key: str) -> bool:
        """
        Invalidate a cache entry.

        Args:
            key: Cache key

        Returns:
            True if cache was invalidated
        """
        if key in self.cache:
            del self.cache[key]
            self._delete_from_disk(key)
            logger.debug(f"Invalidated cache: {key}")
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self._clear_disk_cache()
        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics with content-type breakdown.

        Returns:
            Dictionary with cache statistics including content-type breakdown
        """
        now = time.time()
        total_entries = len(self.cache)

        # Count valid entries by content type
        content_type_stats = {}
        total_valid = 0

        for key, data in self.cache.items():
            content_type = data.get("content_type", "general")
            timestamp = data.get("timestamp", 0)
            ttl = self._get_ttl_for_content_type(content_type)

            if now - timestamp <= ttl:
                total_valid += 1

                if content_type not in content_type_stats:
                    content_type_stats[content_type] = {
                        "count": 0,
                        "ttl": ttl,
                        "ttl_seconds": ttl,
                        "valid": 0,
                        "expired": 0
                    }

                content_type_stats[content_type]["count"] += 1
                if now - timestamp <= ttl:
                    content_type_stats[content_type]["valid"] += 1
                else:
                    content_type_stats[content_type]["expired"] += 1

        # Calculate expired entries
        expired_entries = total_entries - total_valid

        # Build statistics dictionary
        stats = {
            "total_entries": total_entries,
            "valid_entries": total_valid,
            "expired_entries": expired_entries,
            "cache_dir": str(self.cache_dir),
            "default_ttl": self.default_ttl,
            "content_type_stats": content_type_stats
        }

        return stats

    def _generate_key(self, query_obj: SearchQuery) -> str:
        """
        Generate a cache key for a query.

        Args:
            query_obj: Search query

        Returns:
            Cache key
        """
        import hashlib

        data = {
            "query": query_obj.query_text,
            "mode": query_obj.mode.value,
            "max_results": query_obj.max_results,
            "language": query_obj.language
        }

        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _get_content_type(self, query_obj: SearchQuery, results: Optional[List] = None) -> str:
        """
        Determine content type from query text and/or results.

        Args:
            query_obj: Search query object
            results: Optional search results to check source domains

        Returns:
            Content type string (default: 'general')
        """
        query_lower = query_obj.query_text.lower()

        # Check query text for content type keywords (more specific types first)
        content_keywords = {
            'github_releases': ['release notes', 'download', 'release assets', 'releases page', 'release v'],
            'stocks': ['stock', 'ticker', 'share', 'market'],
            'crypto': ['crypto', 'bitcoin', 'ethereum', 'token'],
            'github': ['github', 'repo', 'repository', 'code'],
            'wikipedia': ['wikipedia', 'wiki'],
            'docs': ['docs', 'documentation'],
            'rfc': ['rfc', 'draft', 'internet'],
            'news': ['news', 'breaking'],
            'stackoverflow': ['stackoverflow', 'stack overflow', 'coding question'],
        }

        for content_type, keywords in content_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                logger.debug(f"Detected content type: {content_type} from query")
                return content_type

        # Check results for source domains
        if results:
            for result in results:
                if hasattr(result, 'source') and result.source:
                    source_lower = result.source.lower()
                    if 'github.com' in source_lower:
                        # Check if it's a release by checking URL pattern
                        if '/releases/' in source_lower or '/tag/' in source_lower:
                            return 'github_releases'
                        return 'github'
                    elif 'wikipedia.org' in source_lower or 'wiki' in source_lower:
                        return 'wikipedia'
                    elif 'rfc-editor.org' in source_lower:
                        return 'rfc'
                    elif 'stackoverflow.com' in source_lower:
                        return 'stackoverflow'
                    elif 'news' in source_lower or 'times' in source_lower:
                        return 'news'

        # Default to general content type
        return 'general'

    def _get_ttl_for_content_type(self, content_type: str) -> int:
        """
        Get TTL for a specific content type.

        Args:
            content_type: Content type string

        Returns:
            TTL in seconds
        """
        # Normalize content type
        content_type = content_type.lower().replace('_', ' ')
        
        # Check exact match
        if content_type in self.CONTENT_TYPE_TTL:
            return self.CONTENT_TYPE_TTL[content_type]
        
        # Check for partial matches (e.g., 'github_releases' -> 'github')
        for key, ttl in self.CONTENT_TYPE_TTL.items():
            if content_type in key or key in content_type:
                logger.debug(f"Content type '{content_type}' maps to '{key}'")
                return ttl
        
        # Default to general TTL
        logger.debug(f"Content type '{content_type}' using default TTL")
        return self.default_ttl

    def get_ttl(self, query_obj: SearchQuery, results: Optional[List] = None) -> int:
        """
        Get TTL for a specific query based on content type.

        Args:
            query_obj: Search query object
            results: Optional search results to check source domains

        Returns:
            TTL in seconds
        """
        content_type = self._get_content_type(query_obj, results)
        ttl = self._get_ttl_for_content_type(content_type)
        logger.debug(f"Content type: {content_type}, TTL: {ttl}s")
        return ttl

    def _save_to_disk(self, key: str, data: Dict[str, Any]) -> None:
        """
        Save cache entry to disk.

        Args:
            key: Cache key
            data: Cache data
        """
        try:
            cache_file = self.cache_dir / f"{key}.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cache to disk: {e}")

    def _load_from_disk(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Load cache entry from disk.

        Args:
            key: Cache key

        Returns:
            Cache data or None
        """
        try:
            cache_file = self.cache_dir / f"{key}.json"
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cache from disk: {e}")
            return None

    def _delete_from_disk(self, key: str) -> None:
        """
        Delete cache entry from disk.

        Args:
            key: Cache key
        """
        try:
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.error(f"Failed to delete cache from disk: {e}")

    def _clear_disk_cache(self) -> None:
        """Clear all cache entries from disk."""
        try:
            if self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                logger.info("Cleared disk cache")
        except Exception as e:
            logger.error(f"Failed to clear disk cache: {e}")

    def optimize_cache(self, min_age: int = 86400) -> None:
        """
        Optimize cache by removing old entries.

        Args:
            min_age: Minimum age in seconds to keep entries
        """
        now = time.time()
        removed = 0

        for key, data in list(self.cache.items()):
            timestamp = data.get("timestamp", 0)
            if now - timestamp > min_age:
                self.invalidate(key)
                removed += 1

        if removed > 0:
            logger.info(f"Optimized cache: removed {removed} old entries")

    def get_cache_age(self, key: str) -> Optional[float]:
        """
        Get the age of a cache entry.

        Args:
            key: Cache key

        Returns:
            Age in seconds or None
        """
        if key not in self.cache:
            return None

        timestamp = self.cache[key].get("timestamp")
        if timestamp:
            return time.time() - timestamp
        return None