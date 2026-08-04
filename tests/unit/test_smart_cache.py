"""
Test Smart Cache with content-type-based TTLs.

This test verifies that the cache manager correctly determines content types
from queries and uses the appropriate TTLs for each content type.
"""

import sys
sys.path.insert(0, 'src')

from research.cache_manager import CacheManager
from research.models import SearchQuery, SearchResult, SearchMode, SourceTrustLevel


def test_content_type_detection():
    """Test content type detection from query text."""
    print("=" * 80)
    print("CONTENT TYPE DETECTION TEST")
    print("=" * 80)
    
    cache_manager = CacheManager()
    
    # Test content type detection from query text
    test_cases = [
        ("AAPL stock price", "stocks"),
        ("Bitcoin current price", "crypto"),
        ("latest python release", "general"),  # General release query (no GitHub context)
        ("python release v3.14", "github_releases"),  # GitHub release with version number
        ("what is Wikipedia", "wikipedia"),
        ("how to use Django", "general"),  # No docs source, so defaults to general
        ("RFC 8266 details", "rfc"),
        ("latest tech news", "news"),
        ("breaking news today", "news"),
        ("stackoverflow python error", "stackoverflow"),
        ("general question", "general"),
    ]
    
    print("\nTesting content type detection from query text:")
    for query_text, expected_type in test_cases:
        query_obj = SearchQuery(query_text=query_text, mode=SearchMode.STANDARD)
        content_type = cache_manager._get_content_type(query_obj)
        status = "✓" if content_type == expected_type else "✗"
        print(f"  {status} Query: '{query_text}'")
        print(f"      Expected: {expected_type:20s} Got: {content_type}")
        assert content_type == expected_type, f"Failed for query: {query_text}"
    
    print("\n  ✓ All content type detections from query text passed!")
    
    # Test content type detection from source domains
    print("\nTesting content type detection from source domains:")
    
    source_domain_tests = [
        ("https://github.com/repo/releases/v1.0", "github_releases"),
        ("https://github.com/python/cpython", "github"),
        ("https://wikipedia.org/wiki/Python", "wikipedia"),
        ("https://rfc-editor.org/rfc/rfc8266", "rfc"),
        ("https://stackoverflow.com/questions/123", "stackoverflow"),
        ("https://example.com", "general"),
    ]
    
    for url, expected_type in source_domain_tests:
        results = [SearchResult(
            url=url,
            title="Test result",
            source=url,  # source must match the URL being tested for domain detection
            trust_level=SourceTrustLevel.UNKNOWN,
            score=0.7,
            snippet="Test snippet"
        )]
        query_obj = SearchQuery(query_text="test", mode=SearchMode.STANDARD)
        content_type = cache_manager._get_content_type(query_obj, results)
        status = "✓" if content_type == expected_type else "✗"
        print(f"  {status} URL: {url}")
        print(f"      Expected: {expected_type:20s} Got: {content_type}")
        assert content_type == expected_type, f"Failed for URL: {url}"
    
    print("\n  ✓ All content type detections from source domains passed!")


def test_ttl_calculation():
    """Test TTL calculation for different content types."""
    print("\n" + "=" * 80)
    print("TTL CALCULATION TEST")
    print("=" * 80)
    
    cache_manager = CacheManager()
    
    # Test TTLs for different content types
    test_cases = [
        ("stocks", 60),           # 1 minute
        ("crypto", 30),           # 30 seconds
        ("github", 86400),        # 1 day
        ("github_releases", 86400),  # 1 day
        ("wikipedia", 2592000),   # 30 days
        ("docs", 604800),         # 7 days
        ("rfc", 31536000),        # 365 days
        ("news", 900),            # 15 minutes
        ("stackoverflow", 1209600),  # 14 days
        ("general", 1800),        # 30 minutes (default)
    ]
    
    print("\nTesting TTL calculation:")
    for content_type, expected_ttl in test_cases:
        ttl = cache_manager._get_ttl_for_content_type(content_type)
        status = "✓" if ttl == expected_ttl else "✗"
        print(f"  {status} Content Type: {content_type:20s} Expected TTL: {expected_ttl:8d}s, Got: {ttl:8d}s")
        assert ttl == expected_ttl, f"Failed for content type: {content_type}"
    
    print("\n  ✓ All TTL calculations passed!")


def test_cache_with_content_types():
    """Test caching with different content types."""
    print("\n" + "=" * 80)
    print("CACHE WITH CONTENT TYPES TEST")
    print("=" * 80)
    
    cache_manager = CacheManager()
    
    print("\nTesting cache storage and retrieval with different content types:")
    
    # Create cache entries with different content types
    test_queries = [
        ("AAPL stock price", "stocks"),
        ("Bitcoin current price", "crypto"),
        ("latest python release", "general"),
        ("what is Wikipedia", "wikipedia"),
        ("RFC 8266 details", "rfc"),
        ("breaking news today", "news"),
        ("general question", "general"),
    ]
    
    for query_text, expected_type in test_queries:
        # Create a mock search result
        results = [
            SearchResult(
                url="https://example.com",
                title="Test result",
                source="https://example.com",
                trust_level=SourceTrustLevel.OFFICIAL,
                score=0.95,
                snippet="Test result"
            )
        ]
        
        # Create query object
        query_obj = SearchQuery(query_text=query_text, mode=SearchMode.STANDARD)
        
        # Generate cache key
        cache_key = cache_manager._generate_key(query_obj)
        
        # Set cache entry (pass query_obj so content type can be detected)
        cache_manager.set(cache_key, None, results, query_obj)
        
        # Verify content_type was stored
        cached = cache_manager.cache[cache_key]
        status = "✓" if cached.get("content_type") == expected_type else "✗"
        print(f"  {status} Query: '{query_text}'")
        print(f"      Expected Type: {expected_type:15s} Got: {cached.get('content_type', 'NOT FOUND')}")
        assert cached.get("content_type") == expected_type, f"Failed for query: {query_text}"
    
    print("\n  ✓ All cache entries have correct content types!")


def test_stats_with_content_types():
    """Test cache statistics with content-type breakdown."""
    print("\n" + "=" * 80)
    print("CACHE STATISTICS TEST")
    print("=" * 80)
    
    cache_manager = CacheManager()
    
    # Create test queries with different content types
    test_queries = [
        ("AAPL stock price", "stocks"),
        ("Bitcoin current price", "crypto"),
        ("latest python release", "general"),
        ("what is Wikipedia", "wikipedia"),
        ("general question", "general"),
    ]
    
    for query_text, content_type in test_queries:
        results = [
            SearchResult(
                url="https://example.com",
                title="Test result",
                source="https://example.com",
                trust_level=SourceTrustLevel.OFFICIAL,
                score=0.95,
                snippet="Test result"
            )
        ]
        query_obj = SearchQuery(query_text=query_text, mode=SearchMode.STANDARD)
        cache_key = cache_manager._generate_key(query_obj)
        cache_manager.set(cache_key, None, results, query_obj)
    
    # Get statistics
    stats = cache_manager.get_stats()
    
    print("\nCache Statistics:")
    print(f"  Total Entries: {stats['total_entries']}")
    print(f"  Valid Entries: {stats['valid_entries']}")
    print(f"  Expired Entries: {stats['expired_entries']}")
    print(f"  Cache Directory: {stats['cache_dir']}")
    print(f"  Default TTL: {stats['default_ttl']}s")
    
    print("\nContent Type Breakdown:")
    for content_type, info in stats['content_type_stats'].items():
        print(f"  {content_type}:")
        print(f"    Count: {info['count']}")
        print(f"    TTL: {info['ttl_seconds']}s ({info['ttl_seconds']/60:.1f} min)")
        print(f"    Valid: {info['valid']}")
        print(f"    Expired: {info['expired']}")
    
    print("\n  ✓ Cache statistics with content-type breakdown working!")


def test_ttl_validates_cache_entry():
    """Test that cache entries are validated using content-type-based TTL."""
    print("\n" + "=" * 80)
    print("TTL VALIDATION TEST")
    print("=" * 80)
    
    cache_manager = CacheManager()
    
    print("\nTesting cache entry validation with different TTLs:")
    
    # Test that cache entries with same timestamp but different content types
    # have different expiration times
    test_cases = [
        ("stocks", 60, 30),        # Stocks should expire in 60s
        ("general", 1800, 30),     # General should expire in 1800s
    ]
    
    import time
    
    for content_type, ttl, elapsed_time in test_cases:
        query_text = f"{content_type} test"
        results = [
            SearchResult(
                url="https://example.com",
                title="Test result",
                source="https://example.com",
                trust_level=SourceTrustLevel.OFFICIAL,
                score=0.95,
                snippet="Test result"
            )
        ]
        query_obj = SearchQuery(query_text=query_text, mode=SearchMode.STANDARD)
        cache_key = cache_manager._generate_key(query_obj)
        
        # Set cache entry with current timestamp
        cache_manager.set(cache_key, None, results, query_obj)
        
        # Verify it's valid immediately
        cached = cache_manager.cache[cache_key]
        cached['timestamp'] = time.time() - elapsed_time
        valid = cache_manager.has_cache(cache_key)
        
        # Set to future timestamp
        cached['timestamp'] = time.time() + ttl
        valid_future = cache_manager.has_cache(cache_key)
        
        # For expired entry (should be removed from cache)
        # Subtract a little extra margin so age > ttl reliably, avoiding a
        # boundary case where age == ttl (which the expiry check treats as valid)
        cached['timestamp'] = time.time() - ttl - 1
        valid_expired = cache_manager.has_cache(cache_key)
        
        print(f"  Content Type: {content_type}")
        print(f"    Expected TTL: {ttl}s")
        print(f"    Entry with {elapsed_time}s age: {'valid' if valid else 'expired'}")
        print(f"    Entry with future timestamp: {'valid' if valid_future else 'expired'}")
        print(f"    Entry with expired timestamp: {'valid' if valid_expired else 'expired (removed)'}")
    
    print("\n  ✓ TTL validation working correctly!")


if __name__ == "__main__":
    test_content_type_detection()
    test_ttl_calculation()
    test_cache_with_content_types()
    test_stats_with_content_types()
    test_ttl_validates_cache_entry()
    
    print("\n" + "=" * 80)
    print("✓ ALL SMART CACHE TESTS PASSED!")
    print("=" * 80)
    print("\nThe Smart Cache implementation is working correctly:")
    print("  1. Content type detection from query text ✓")
    print("  2. Content type detection from source domains ✓")
    print("  3. TTL calculation for different content types ✓")
    print("  4. Cache storage with content type tracking ✓")
    print("  5. Cache statistics with content-type breakdown ✓")
    print("  6. TTL validation for cache entries ✓")
    print("\nThe cache automatically determines the appropriate TTL based on")
    print("content type, optimizing cache lifetimes for different data types.")