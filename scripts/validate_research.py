"""
Research Architecture Validation Script

Tests the research engine with specific queries to verify:
1. Research Diagnostics work correctly
2. Planner Validation - queries decompose properly
3. Provider Selection - correct providers are used
4. Confidence Loop - confidence evolves properly
5. Research Trace - comprehensive summary is logged

Usage:
    python scripts/validate_research.py
"""

import logging
import sys
import time
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from research import ResearchConfig, ResearchEngine, SearchMode

# Configure logging - show everything
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_query(query: str, mode: SearchMode = SearchMode.STANDARD):
    """
    Test a single query with the research engine.

    Args:
        query: The query to test
        mode: Research mode (quick, standard, deep)

    Returns:
        Dictionary with results
    """
    print_section(f"Testing: {query}")
    print(f"Mode: {mode.value.upper()}")

    # Start timing
    start_time = time.time()

    # Enable debug mode to see all diagnostics
    engine = ResearchEngine(
        config=ResearchConfig(
            enabled=True, default_mode=mode, debug=True  # Enable detailed diagnostics
        )
    )

    try:
        # Perform research
        result = engine.research(query, mode=mode)
        duration = time.time() - start_time

        # Print summary
        print("\n📊 RESULTS")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Strong Evidence: {len(result.strong_evidence)}")
        print(f"  Duration: {duration:.2f}s")

        if result.citations:
            print("\n📚 Sources:")
            for i, citation in enumerate(result.citations[:5], 1):
                trust = (
                    citation.trust_level.value.upper()
                    if hasattr(citation.trust_level, "value")
                    else citation.trust_level
                )
                print(f"  {i}. [{trust}] {citation.title[:50]}...")

        if result.conflicts:
            print(f"\n⚠️  Conflicts: {len(result.conflicts)}")

        if result.recommendations:
            print("\n💡 Recommendations:")
            for rec in result.recommendations[:3]:
                print(f"  - {rec}")

        return {
            "success": True,
            "query": query,
            "mode": mode.value,
            "confidence": result.confidence,
            "iterations": getattr(result, "iterations", 1),
            "duration": duration,
            "strong_evidence": len(result.strong_evidence),
            "weak_evidence": len(result.weak_evidence),
            "conflicts": len(result.conflicts),
        }

    except Exception as e:
        duration = time.time() - start_time
        print(f"\n❌ ERROR: {e}")
        print(f"Duration: {duration:.2f}s")
        return {
            "success": False,
            "query": query,
            "mode": mode.value,
            "error": str(e),
            "duration": duration,
        }


def validate_planner_refinement():
    """Test that planner refinement works correctly."""
    print_section("PLANNER VALIDATION")

    # Test queries that should trigger refinement
    queries = ["latest Python release", "latest Nvidia drivers"]

    for query in queries:
        print(f"\nQuery: {query}")
        result = test_query(query, mode=SearchMode.STANDARD)
        print(f"Confidence: {result.get('confidence', 0):.2f}")


def validate_provider_selection():
    """Test that the correct providers are selected for different query types."""
    print_section("PROVIDER SELECTION VALIDATION")

    queries = [
        ("Explain OSPF", SearchMode.QUICK),
        ("Latest BEL quarterly results", SearchMode.STANDARD),
        ("Review this repository", SearchMode.QUICK),
        ("Explain asyncio", SearchMode.QUICK),
        ("Python 3.14 changes", SearchMode.STANDARD),
    ]

    for query, mode in queries:
        print(f"\nQuery: {query}")
        result = test_query(query, mode=mode)
        print(f"Confidence: {result.get('confidence', 0):.2f}")


def validate_confidence_loop():
    """Test that confidence evolves properly across iterations."""
    print_section("CONFIDENCE LOOP VALIDATION")

    queries = [
        "latest Python release",
        "latest Nvidia drivers",
        "BEL quarterly results",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        result = test_query(query, mode=SearchMode.STANDARD)
        print(f"Final Confidence: {result.get('confidence', 0):.2f}")

        # Expected: Confidence should increase naturally, not stay at 0.50
        if result.get("confidence", 0) < 0.5:
            print(
                f"  ⚠️  WARNING: Confidence is suspiciously low ({result.get('confidence', 0):.2f})"
            )
            print("  Check the detailed logs above for evidence scoring issues")


def validate_performance():
    """Test and measure performance components."""
    print_section("PERFORMANCE VALIDATION")

    queries = ["latest Python release"]

    for query in queries:
        print(f"\nQuery: {query}")

        start_time = time.time()
        result = engine.research(query, mode=SearchMode.STANDARD)
        duration = time.time() - start_time

        print(f"Total Time: {duration:.2f}s")

        # Note: Detailed timing for each component would require
        # more sophisticated instrumentation in a production system


def main():
    """Run all validation tests."""
    print_section("AuraAI Research Architecture Validation")
    print("Testing Milestone 14 research infrastructure")

    print("\nThis script will test:")
    print("  1. Research Diagnostics (evidence scoring, trust bonuses, etc.)")
    print("  2. Planner Validation (query decomposition)")
    print("  3. Provider Selection (correct providers for query types)")
    print("  4. Confidence Loop (confidence evolution)")
    print("  5. Research Trace (comprehensive summary)")

    input("\nPress Enter to start validation...")

    # Run validation tests
    try:
        validate_planner_refinement()
        validate_provider_selection()
        validate_confidence_loop()
        validate_performance()

        print_section("VALIDATION COMPLETE")
        print("Review the output above to verify:")
        print("  ✓ Evidence scores look reasonable (0.7-1.0)")
        print("  ✓ Trust bonuses are applied correctly")
        print("  ✓ Planner decomposes queries properly")
        print("  ✓ Confidence increases across iterations")
        print("  ✓ Research Trace shows all components")
        print("\nIf any issues are found, check the detailed logs above.")

    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Validation failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
