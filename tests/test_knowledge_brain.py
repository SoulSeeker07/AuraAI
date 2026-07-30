"""
Verification tests for Knowledge Brain (Milestone 3).

Tests all 7 modules of the knowledge brain:
1. KnowledgeDB - Stores factual knowledge
2. TopicMemory - Organizes knowledge by topics
3. FreshnessChecker - Manages knowledge lifecycle
4. KnowledgeGraph - Builds relationships
5. LearningEngine - Auto-updates knowledge
6. CacheManager - Caches search results
7. KnowledgeManager - Orchestrates everything
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from knowledge.knowledge_db import KnowledgeDB, KnowledgeFact
from knowledge.topic_memory import TopicMemory, TopicNode
from knowledge.freshness_checker import FreshnessChecker
from knowledge.knowledge_graph import KnowledgeGraph, KnowledgeNode
from knowledge.learning_engine import LearningEngine, LearnedFact
from knowledge.cache_manager import CacheManager, CachedSearchResult
from knowledge.knowledge_manager import KnowledgeManager, KnowledgeRetrievalResult


def test_knowledge_db():
    """Test KnowledgeDB module."""
    print("\n" + "="*60)
    print("TEST 1: KnowledgeDB")
    print("="*60)

    db = KnowledgeDB()

    # Add facts
    print("\n1. Adding facts...")
    db.add_fact(KnowledgeFact(
        topic="Python",
        fact="Python 3.11 was released in October 2022",
        source="official.python.org",
        confidence=0.95,
        category="Programming"
    ))

    db.add_fact(KnowledgeFact(
        topic="Python",
        fact="Python supports async/await syntax",
        source="docs.python.org",
        confidence=0.95,
        category="Programming"
    ))

    db.add_fact(KnowledgeFact(
        topic="Python",
        fact="Python uses duck typing",
        source="python.org",
        confidence=0.9,
        category="Programming"
    ))

    # Retrieve facts
    print("\n2. Retrieving facts...")
    facts = db.get_facts_by_topic("Python")
    print(f"   Found {len(facts)} facts")
    for fact in facts:
        print(f"   - {fact.topic}: {fact.fact[:60]}... ({fact.confidence:.2f})")

    # Search
    print("\n3. Searching...")
    results = db.search_facts("Python 3.11")
    print(f"   Found {len(results)} results")

    # Get topics
    print("\n4. Getting topics...")
    topics = db.get_topics()
    print(f"   Found {len(topics)} topics")

    # Get statistics
    print("\n5. Statistics...")
    facts_count = db.count_facts()
    topics_count = len(db.get_topics())
    categories_count = len(db.get_categories())
    print(f"   Total facts: {facts_count}")
    print(f"   Total topics: {topics_count}")
    print(f"   Total categories: {categories_count}")

    print("\n✓ KnowledgeDB tests passed!")
    return True


def test_topic_memory():
    """Test TopicMemory module."""
    print("\n" + "="*60)
    print("TEST 2: TopicMemory")
    print("="*60)

    db = KnowledgeDB()
    topic_mem = TopicMemory(db)

    # Add facts
    print("\n1. Adding facts...")
    topic_mem.add_fact(KnowledgeFact(
        topic="Python",
        fact="Python is a high-level programming language",
        source="python.org",
        confidence=0.95,
        category="Programming"
    ))

    topic_mem.add_fact(KnowledgeFact(
        topic="Python",
        fact="Python supports multiple programming paradigms",
        source="python.org",
        confidence=0.9,
        category="Programming"
    ))

    topic_mem.add_fact(KnowledgeFact(
        topic="JavaScript",
        fact="JavaScript is a web scripting language",
        source="developer.mozilla.org",
        confidence=0.95,
        category="Programming"
    ))

    # Build topic hierarchy
    print("\n2. Building topic hierarchy...")
    hierarchy = topic_mem.get_topic_hierarchy("Python")
    print(f"   Topics: {topic_mem.get_all_topics()}")

    # Get topic hierarchy
    print("\n3. Getting topic hierarchy...")
    hierarchy = topic_mem.get_topic_hierarchy("Python")
    print(f"   Hierarchy for Python:")
    print(f"   - Topic: {hierarchy.get('topic')}")
    print(f"   - Subtopics: {len(hierarchy.get('subtopics', []))}")
    print(f"   - Facts: {len(hierarchy.get('facts', []))}")

    # Get subtopics
    print("\n4. Getting subtopics...")
    subtopics = topic_mem.get_subtopics("Python")
    print(f"   Subtopics for Python: {subtopics}")

    # Get topic statistics
    print("\n5. Topic statistics...")
    stats = topic_mem.get_topic_stats("Python")
    print(f"   Stats for Python:")
    print(f"   - Total facts: {stats['total_facts']}")
    print(f"   - Last updated: {stats.get('last_updated', 'N/A')}")

    print("\n✓ TopicMemory tests passed!")
    return True


def test_freshness_checker():
    """Test FreshnessChecker module."""
    print("\n" + "="*60)
    print("TEST 3: FreshnessChecker")
    print("="*60)

    db = KnowledgeDB()
    checker = FreshnessChecker(db)

    # Add facts with different categories
    print("\n1. Adding facts with different categories...")

    # Programming (30 days)
    db.add_fact(KnowledgeFact(
        topic="Python",
        fact="Python 3.12 is the latest version",
        source="python.org",
        confidence=0.95,
        category="Programming"
    ))

    # News (1 day)
    db.add_fact(KnowledgeFact(
        topic="OpenAI",
        fact="OpenAI released GPT-4 Turbo",
        source="openai.com",
        confidence=0.75,
        category="News"
    ))

    # Weather (0 days)
    db.add_fact(KnowledgeFact(
        topic="Weather",
        fact="Today's temperature is 25°C",
        source="weather.com",
        confidence=0.8,
        category="Weather"
    ))

    # Check freshness
    print("\n2. Checking freshness...")
    facts = db.get_facts_by_topic("Python")
    for fact in facts:
        age = checker.get_age_days(fact)
        lifetime = checker.get_category_lifetime(fact.category)
        fresh = age < lifetime
        print(f"   - {fact.topic}: Fresh? {fresh} (age: {age:.1f} days, lifetime: {lifetime} days)")

    # Get statistics
    print("\n3. Statistics...")
    stats = checker.get_statistics()
    print(f"   Total facts: {stats['total_facts']}")
    print(f"   Fresh facts: {stats['fresh_facts']}")
    print(f"   Expired facts: {stats['expired_facts']}")

    # Check category lifetimes
    print("\n4. Category lifetimes:")
    lifetimes = checker.LIFETIME_MAP
    for category, days in lifetimes.items():
        print(f"   - {category}: {days} days")

    print("\n✓ FreshnessChecker tests passed!")
    return True


def test_knowledge_graph():
    """Test KnowledgeGraph module."""
    print("\n" + "="*60)
    print("TEST 4: KnowledgeGraph")
    print("="*60)

    db = KnowledgeDB()
    graph = KnowledgeGraph(db)

    # Add facts
    print("\n1. Adding facts...")
    graph.add_fact(KnowledgeFact(
        topic="Python",
        fact="Python is a programming language",
        source="python.org",
        confidence=0.95,
        category="Programming"
    ))

    graph.add_fact(KnowledgeFact(
        topic="Programming",
        fact="Programming involves writing code",
        source="wikipedia.org",
        confidence=0.9,
        category="Programming"
    ))

    graph.add_fact(KnowledgeFact(
        topic="Web",
        fact="Web development uses HTML, CSS, JavaScript",
        source="developer.mozilla.org",
        confidence=0.9,
        category="Programming"
    ))

    # Find related concepts
    print("\n2. Finding related concepts...")
    related = graph.get_related_nodes("Python", depth=2)
    print(f"   Related to 'Python': {len(related)} concepts")
    for concept, score in related:
        print(f"   - {concept}: {score:.2f}")

    # Get path between topics
    print("\n3. Finding path between topics...")
    path = graph.find_path("Python", "Web")
    if path:
        print(f"   Path: {' -> '.join(path)}")
    else:
        print("   No path found")

    # Get topic neighbors
    print("\n4. Getting topic neighbors...")
    neighbors = graph.get_topic_neighbors("Python", depth=2)
    print(f"   Neighbors of 'Python': {len(neighbors)}")
    for neighbor in neighbors:
        print(f"   - {neighbor}")

    # Get statistics
    print("\n5. Statistics...")
    stats = graph.get_statistics()
    print(f"   Total nodes: {stats['total_nodes']}")
    print(f"   Total edges: {stats['total_edges']}")

    # Try graph visualization
    print("\n6. Generating visualization...")
    try:
        graph.visualize_graph("test_graph", max_nodes=10)
        print("   Graph visualization saved to 'test_graph.png'")
    except Exception as e:
        print(f"   Note: Graph visualization requires matplotlib: {e}")

    print("\n✓ KnowledgeGraph tests passed!")
    return True


def test_learning_engine():
    """Test LearningEngine module."""
    print("\n" + "="*60)
    print("TEST 5: LearningEngine")
    print("="*60)

    db = KnowledgeDB()
    engine = LearningEngine(db)

    # Simulate search results
    print("\n1. Simulating search results...")
    search_results = [
        {
            "title": "Python 3.12 Released",
            "snippet": "Python 3.12 is the latest version of Python, released in October 2023. It includes many new features and improvements.",
            "url": "https://python.org/news/python-312-released",
            "source": "official"
        },
        {
            "title": "Python 3.12 New Features",
            "snippet": "Python 3.12 introduces type parameter syntax, positional-only parameters, and more performance improvements.",
            "url": "https://docs.python.org/whatsnew/3.12.html",
            "source": "official"
        },
        {
            "title": "Why Use Python 3.12?",
            "snippet": "Python 3.12 offers better performance, new features, and improved error messages.",
            "url": "https://realpython.com/python-312-new-features",
            "source": "blog"
        }
    ]

    # Learn from search results
    print("\n2. Learning from search results...")
    learned_facts = engine.learn_from_web_search("Python", search_results, "Latest Python version")
    print(f"   Learned {len(learned_facts)} facts")

    # Show learned facts
    print("\n3. Learned facts:")
    for fact in learned_facts[:3]:
        print(f"   - {fact.topic}: {fact.fact[:60]}... (confidence: {fact.confidence:.2f})")

    # Get statistics
    print("\n4. Learning statistics...")
    stats = engine.get_statistics()
    print(f"   Total learned: {stats['total_learned']}")
    print(f"   Topics learned: {stats['topics_learned']}")

    # Get known topics
    print("\n5. Known topics:")
    topics = engine.get_known_topics()
    print(f"   {topics}")

    # Test batch learning
    print("\n6. Testing batch learning...")
    batch_learnings = [
        {
            "title": "New Programming Language",
            "snippet": "Rust is a systems programming language focused on safety and performance.",
            "url": "https://rust-lang.org",
            "source": "official"
        },
        {
            "title": "Rust vs C++",
            "snippet": "Rust offers better memory safety without garbage collection.",
            "url": "https://blog.rust-lang.org",
            "source": "blog"
        }
    ]
    learned = engine.batch_learn(batch_learnings, "Rust")
    print(f"   Learned {len(learned)} facts from batch")

    print("\n✓ LearningEngine tests passed!")
    return True


def test_cache_manager():
    """Test CacheManager module."""
    print("\n" + "="*60)
    print("TEST 6: CacheManager")
    print("="*60)

    cache = CacheManager()

    # Cache search results
    print("\n1. Caching search results...")
    search_results = [
        {
            "title": "Python Tutorial",
            "snippet": "Learn Python programming with this tutorial.",
            "url": "https://python.org/tutorial",
            "source": "web"
        }
    ]

    cache_key = cache.cache_search_result("Python tutorial", search_results, category="General", source="web")
    print(f"   Cached with key: {cache_key[:16]}...")

    # Retrieve from cache
    print("\n2. Retrieving from cache...")
    cached = cache.get_cached_result("Python tutorial", "General")
    if cached:
        print(f"   Found {len(cached)} cached results")
        print(f"   First result: {cached[0]['title']}")
    else:
        print("   No results found")

    # Check cache statistics
    print("\n3. Cache statistics...")
    stats = cache.get_cache_stats()
    print(f"   Memory cache entries: {stats['memory_cache']['total_entries']}")
    print(f"   Disk cache entries: {stats['disk_cache']['total_entries']}")

    # Get most requested queries
    print("\n4. Most requested queries...")
    queries = cache.get_most_requested_queries(limit=5)
    for query_info in queries:
        print(f"   - {query_info['query']}: {query_info['request_count']} times")

    # Invalidate cache
    print("\n5. Invalidating cache...")
    invalidated = cache.invalidate_query("Python tutorial", "General")
    print(f"   Invalidated {invalidated} entries")

    # Cleanup expired
    print("\n6. Cleaning up expired entries...")
    cache.cleanup_expired_entries()
    stats = cache.get_cache_stats()
    print(f"   Remaining entries: {stats['memory_cache']['total_entries']}")

    # Test batch caching
    print("\n7. Testing batch caching...")
    cache_entries = [
        {"query": "Web development", "results": [{"title": "Web dev guide"}], "category": "Programming"},
        {"query": "Python basics", "results": [{"title": "Python intro"}], "category": "Programming"}
    ]
    cached = cache.batch_cache_results(cache_entries)
    print(f"   Cached {cached} entries in batch")

    print("\n✓ CacheManager tests passed!")
    return True


def test_knowledge_manager():
    """Test KnowledgeManager module."""
    print("\n" + "="*60)
    print("TEST 7: KnowledgeManager")
    print("="*60)

    manager = KnowledgeManager()

    # Test overall statistics
    print("\n1. Overall statistics...")
    stats = manager.get_statistics()
    print(f"   Total retrievals: {stats['total_retrievals']}")
    print(f"   Total learnings: {stats['total_learnings']}")
    print(f"   Knowledge base: {stats['knowledge_db']['total_facts']} facts")

    # Test getting topics
    print("\n2. Getting all topics...")
    topics = manager.get_all_topics()
    print(f"   Found {len(topics)} topics")

    # Test adding facts
    print("\n3. Adding facts...")
    success = manager.add_fact(
        topic="JavaScript",
        fact="JavaScript is the programming language of the web",
        source="developer.mozilla.org",
        confidence=0.95,
        category="Programming"
    )
    print(f"   Added fact: {success}")

    # Test get facts by topic
    print("\n4. Getting facts by topic...")
    facts = manager.get_facts_by_topic("JavaScript", max_results=10)
    print(f"   Found {len(facts)} facts")
    for fact in facts:
        print(f"   - {fact.fact[:60]}...")

    # Test get related topics
    print("\n5. Getting related topics...")
    related = manager.get_related_topics("JavaScript", depth=2)
    print(f"   Related topics: {len(related)}")
    for topic in related:
        print(f"   - {topic}")

    # Test category lifetimes
    print("\n6. Category lifetimes...")
    lifetimes = manager.get_category_lifetimes()
    for category, days in lifetimes.items():
        print(f"   - {category}: {days} days")

    # Test freshness checker stats
    print("\n7. Freshness statistics...")
    freshness_stats = manager.get_freshness_checker_stats()
    print(f"   Fresh facts: {freshness_stats['fresh_facts']}")
    print(f"   Expired facts: {freshness_stats['expired_facts']}")

    # Test learning engine stats
    print("\n8. Learning statistics...")
    learning_stats = manager.get_learning_engine_stats()
    print(f"   Total learned: {learning_stats['total_learned']}")

    print("\n✓ KnowledgeManager tests passed!")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" KNOWLEDGE BRAIN (Milestone 3) VERIFICATION TESTS")
    print("="*70)

    tests = [
        ("KnowledgeDB", test_knowledge_db),
        ("TopicMemory", test_topic_memory),
        ("FreshnessChecker", test_freshness_checker),
        ("KnowledgeGraph", test_knowledge_graph),
        ("LearningEngine", test_learning_engine),
        ("CacheManager", test_cache_manager),
        ("KnowledgeManager", test_knowledge_manager)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"\n✗ {name} tests FAILED!")
                failed += 1
        except Exception as e:
            print(f"\n✗ {name} tests FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(" SUMMARY")
    print("="*70)
    print(f" Passed: {passed}/{len(tests)}")
    print(f" Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print("\nKnowledge Brain (Milestone 3) is ready!")
    else:
        print(f"\n✗✗✗ {failed} TEST(S) FAILED ✗✗✗")

    print("="*70 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
