"""
Test file for Aura AI v2 Web Search System

This demonstrates how to use the new Aura search components:
- Intent analysis
- Live search with Tavily
- Caching
- Source ranking
- Citations
- Research planning
"""

from __future__ import annotations

import os
from pathlib import Path
from ai.provider_manager import ProviderManager
from brain.aura_search_system import AuraSearchSystem
from brain.models_extended import WebSearchResult


def test_intent_analysis():
    """Test intent analysis with various queries."""
    print("\n" + "="*60)
    print("Testing Intent Analysis")
    print("="*60)
    
    # Initialize search system
    search_system = AuraSearchSystem(
        provider_manager=ProviderManager(),
    )
    
    # Test queries
    test_queries = [
        ("What is the weather in Tokyo?", "live_information"),
        ("Compare React and Vue", "KNOWLEDGE_REQUEST"),
        ("How to write Python decorators", "PROGRAMMING"),
        ("Latest stock prices", "LIVE_INFORMATION"),
        ("Who won yesterday's IPL match?", "LIVE_INFORMATION"),
    ]
    
    for query, expected_intent in test_queries:
        print(f"\nQuery: {query}")
        intent_analysis = search_system.analyze_intent(query)
        
        print(f"  Intent: {intent_analysis.intent}")
        print(f"  Confidence: {intent_analysis.confidence:.2f}")
        print(f"  Needs Web Search: {intent_analysis.needs_web_search}")
        print(f"  Category: {intent_analysis.category}")
        
        if intent_analysis.specialized_sources:
            print(f"  Specialized Sources: {intent_analysis.specialized_sources}")


def test_web_search():
    """Test web search functionality."""
    print("\n" + "="*60)
    print("Testing Web Search")
    print("="*60)
    
    # Initialize search system
    # Note: Tavily API key is required
    tavily_key = os.environ.get("TAVILY_API_KEY")
    
    if not tavily_key:
        print("\n⚠️  TAVILY_API_KEY environment variable not set.")
        print("   Install it with: pip install tavily-python")
        print("   Or set TAVILY_API_KEY environment variable.")
        return
    
    search_system = AuraSearchSystem(
        provider_manager=ProviderManager(),
        tavily_api_key=tavily_key,
    )
    
    # Test search
    query = "What is Python 3.15 new features?"
    
    print(f"\nQuery: {query}")
    results = search_system.search(
        query=query,
        intent_analysis=None,
        use_cache=False,  # Don't use cache for testing
    )
    
    print(f"\nFound {len(results)} results:")
    
    for i, result in enumerate(results[:5], 1):
        print(f"\n{i}. {result.title}")
        print(f"   URL: {result.url}")
        print(f"   Score: {result.score:.2f}")
        print(f"   Snippet: {result.snippet[:100]}...")


def test_caching():
    """Test search caching."""
    print("\n" + "="*60)
    print("Testing Search Caching")
    print("="*60)
    
    tavily_key = os.environ.get("TAVILY_API_KEY")
    
    if not tavily_key:
        print("\n⚠️  TAVILY_API_KEY not set. Skipping cache tests.")
        return
    
    # Initialize with cache directory
    cache_dir = Path("Data/test_search_cache")
    search_system = AuraSearchSystem(
        provider_manager=ProviderManager(),
        tavily_api_key=tavily_key,
        cache_dir=str(cache_dir),
    )
    
    query = "What is machine learning?"
    
    print(f"\nFirst search (no cache):")
    results1 = search_system.search(query=query, use_cache=True)
    print(f"  Results: {len(results1)}")
    print(f"  Cache stats: {search_system.cache.get_stats()}")
    
    print(f"\nSecond search (with cache):")
    results2 = search_system.search(query=query, use_cache=True)
    print(f"  Results: {len(results2)}")
    print(f"  Cache stats: {search_system.cache.get_stats()}")
    
    # Clear cache
    search_system.clear_cache()
    print(f"\nCache cleared. Stats: {search_system.cache.get_stats()}")


def test_source_ranking():
    """Test source ranking."""
    print("\n" + "="*60)
    print("Testing Source Ranking")
    print("="*60)
    
    tavily_key = os.environ.get("TAVILY_API_KEY")
    
    if not tavily_key:
        print("\n⚠️  TAVILY_API_KEY not set. Skipping ranking tests.")
        return
    
    search_system = AuraSearchSystem(
        provider_manager=ProviderManager(),
        tavily_api_key=tavily_key,
    )
    
    # Create some test results
    test_results = [
        {
            "title": "Python 3.15 Release Notes",
            "url": "https://docs.python.org/release/3.15.0/",
        },
        {
            "title": "Python 3.15 New Features",
            "url": "https://blog.python.org/2024/python-3-15",
        },
        {
            "title": "A Blog About Python 3.15",
            "url": "https://example.com/python-3-15",
        },
        {
            "title": "Python 3.15 Guide",
            "url": "https://tutorial.com/python-3-15",
        },
    ]
    
    print("\nOriginal results:")
    for i, r in enumerate(test_results, 1):
        print(f"  {i}. {r['title']}")
    
    # Rank results
    ranked_results = search_system.rank_results(
        results=test_results,
        query="Python 3.15 new features",
    )
    
    print("\nRanked results:")
    for i, r in enumerate(ranked_results, 1):
        print(f"  {i}. {r.result['title']} (score: {r.score:.2f})")
        print(f"     Reasoning: {', '.join(r.reasons)}")


def test_citations():
    """Test citation generation."""
    print("\n" + "="*60)
    print("Testing Citation Generation")
    print("="*60)
    
    tavily_key = os.environ.get("TAVILY_API_KEY")
    
    if not tavily_key:
        print("\n⚠️  TAVILY_API_KEY not set. Skipping citation tests.")
        return
    
    search_system = AuraSearchSystem(
        provider_manager=ProviderManager(),
        tavily_api_key=tavily_key,
    )
    
    # Get search results
    query = "What is artificial intelligence?"
    results = search_system.search(query=query, intent_analysis=None, use_cache=False)
    
    print(f"\nQuery: {query}")
    print(f"\nCitations:")
    
    citations = search_system.get_citations(results, max_citations=3)
    
    for i, citation in enumerate(citations, 1):
        print(f"\n{i}. {citation.title}")
        print(f"   Source: {citation.url}")


def test_research_agent():
    """Test research agent for complex queries."""
    print("\n" + "="*60)
    print("Testing Research Agent")
    print("="*60)
    
    search_system = AuraSearchSystem(
        provider_manager=ProviderManager(),
    )
    
    # Test complex query
    query = "Compare React and Vue.js frameworks"
    
    print(f"\nQuery: {query}")
    print(f"\nIs complex query: {search_system.research_agent.is_complex_query(query)}")
    
    plan = search_system.create_research_plan(query)
    
    print(f"\nResearch Plan:")
    print(f"  Total Steps: {plan.total_steps}")
    print(f"  Estimated Duration: {plan.estimated_duration}")
    print(f"  Reasoning: {plan.reasoning}")
    
    for step in plan.steps:
        print(f"\n  Step {step.step_number}: {step.description}")
        print(f"    Query: {step.query}")
        if step.substeps:
            print(f"    Substeps: {', '.join(step.substeps)}")
        if step.sources:
            print(f"    Sources: {', '.join(step.sources)}")


def test_page_reading():
    """Test page reading functionality."""
    print("\n" + "="*60)
    print("Testing Page Reading")
    print("="*60)
    
    tavily_key = os.environ.get("TAVILY_API_KEY")
    
    if not tavily_key:
        print("\n⚠️  TAVILY_API_KEY not set. Skipping page reading tests.")
        return
    
    search_system = AuraSearchSystem(
        provider_manager=ProviderManager(),
        tavily_api_key=tavily_key,
    )
    
    # Get a search result URL
    query = "Python programming"
    results = search_system.search(query=query, intent_analysis=None, use_cache=False)
    
    if results:
        url = results[0].url
        print(f"\nReading page: {url}")
        
        try:
            content = search_system.read_page(url)
            
            print(f"\nTitle: {content.title}")
            print(f"\nMain text (first 500 chars):")
            print(f"  {content.main_text[:500]}...")
            
            print(f"\nHeadings:")
            for level, text in content.headings[:5]:
                print(f"  {level}. {text}")
            
            print(f"\nCode blocks found: {len(content.code_blocks)}")
            print(f"Tables found: {len(content.tables)}")
            
        except Exception as e:
            print(f"Error reading page: {e}")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Aura AI v2 Web Search System - Test Suite")
    print("="*60)
    
    try:
        test_intent_analysis()
        test_source_ranking()
        test_research_agent()
        test_citations()
        test_caching()
        
        # These require Tavily API key
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if tavily_key:
            test_web_search()
            test_page_reading()
        else:
            print("\n⚠️  Skipping web search and page reading tests.")
            print("   Set TAVILY_API_KEY environment variable to run them.")
        
        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
