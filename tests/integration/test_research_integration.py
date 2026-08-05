"""
Test script for Research Engine Integration with Aura Core

This script tests that the Research Engine is properly integrated
with Aura's Brain system.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add paths before any imports (same as main.py)
project_root = Path(__file__).parent
SRC_DIR = project_root / "src"

sys.path.insert(0, str(project_root))  # project root first
sys.path.insert(1, str(SRC_DIR))  # src second

from core.aura_core import AuraCore

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_research_integration():
    """Test Research Engine integration with Aura Core."""

    # Create config
    config = {
        "project_root": str(Path(__file__).parent),
        "workspace": str(Path(__file__).parent),
        "groq_model": "llama-3.3-70b-versatile",
    }

    logger.info("Initializing Aura Core...")
    core = AuraCore(config=config)

    logger.info("=" * 60)
    logger.info("Aura Core Status")
    logger.info("=" * 60)

    # Print status of all components
    print("\nResearch Engine Status:")
    print(f"  - Enabled: {core.research_enabled}")
    if core.research_enabled:
        stats = core.get_research_stats()
        print(f"  - Initialized: {stats.get('research_engine_initialized', False)}")
        if stats.get("cache_stats"):
            cache_stats = stats["cache_stats"]
            print(f"  - Cache Stats: {cache_stats}")

    logger.info("=" * 60)

    # Test research capability detection
    test_queries = [
        "What is the latest version of Python?",
        "How to configure Palo Alto VPN?",
        "Best AI coding assistant 2024",
        "Recent NVIDIA driver issues",
    ]

    logger.info("\nTesting Research Capability Detection:")
    logger.info("-" * 60)

    for query in test_queries:
        is_needed = core.is_research_needed(query)
        print(f"Query: {query}")
        print(f"  Research needed: {is_needed}")
        print()

    # Test research on a query
    if core.research_enabled:
        logger.info("\nTesting Research Execution:")
        logger.info("-" * 60)

        test_query = "latest NVIDIA driver issues"
        print(f"Query: {test_query}")
        print()

        results = core.perform_research(test_query, mode="quick")
        if results:
            print(f"  Results found: {results.get('has_results', False)}")
            print(f"  Confidence score: {results.get('confidence_score', 0):.1f}/100")
            print(f"  Primary sources: {results.get('primary_sources', [])}")
            print(f"  Number of citations: {len(results.get('citations', []))}")
        else:
            print("  No results returned")

    logger.info("\n" + "=" * 60)
    logger.info("Research Integration Test Complete!")
    logger.info("=" * 60)


def test_response_enhancement():
    """Test response enhancement with research."""

    logger.info("\nTesting Response Enhancement:")
    logger.info("-" * 60)

    # Create config
    config = {
        "project_root": str(Path(__file__).parent),
        "workspace": str(Path(__file__).parent),
        "groq_model": "llama-3.3-70b-versatile",
    }

    core = AuraCore(config=config)

    # Test queries that need research
    test_queries = [
        "What is the latest version of Python?",
        "How to configure Palo Alto VPN?",
        "Best AI coding assistant 2024",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 60)

        result = core.enhance_response_with_research(query, query)
        print(f"  Research used: {result.get('research_used', False)}")

        if result.get("research_used"):
            if "enhanced_message" in result:
                print(
                    f"  Enhanced message length: {len(result['enhanced_message'])} chars"
                )
                print(f"  Sample: {result['enhanced_message'][:100]}...")
            if "research_results" in result:
                research = result["research_results"]
                print(f"  Confidence: {research.get('confidence_score', 0):.1f}/100")
                print(f"  Sources: {research.get('primary_sources', [])}")
        else:
            message = result.get("message", "")
            print(f"  Reason: {message}")

    logger.info("\n" + "=" * 60)
    logger.info("Response Enhancement Test Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    logger.info("Research Engine Integration Tests")
    logger.info("=" * 60)

    # Run tests
    test_research_integration()
    test_response_enhancement()

    logger.info("\n✓ All tests completed successfully!")
