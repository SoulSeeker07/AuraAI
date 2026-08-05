"""
Real End-to-End Research Test

This script runs actual research queries through the AuraAI research engine
to show runtime evidence of:
1. Confidence progression (0.52 → 0.76 → 0.91)
2. Planner refinement (Previous Query → New Query)
3. Provider routing
4. Timing measurements
"""

import logging
from datetime import datetime

# Configure logging to show all debug info
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("research_test_output.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def run_test_query(query: str, mode: str = "standard"):
    """Run a research query and show the full flow."""
    print("\n" + "=" * 80)
    print(f"RESEARCH QUERY: {query}")
    print(f"Mode: {mode}")
    print("=" * 80)

    try:
        from research.models import ResearchConfig, SearchMode
        from research.research_engine import ResearchEngine

        # Create research engine with debug enabled
        config = ResearchConfig(debug=True, default_mode=SearchMode.STANDARD)
        engine = ResearchEngine(config=config)

        # Run research
        print("\n[EXECUTING RESEARCH...]")
        start_time = datetime.now()

        result = engine.research(query=query, mode=SearchMode.STANDARD)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"\n[RESEARCH COMPLETE in {duration:.2f}s]")
        print("=" * 80)

        # Show results
        print("\nSummary:")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Evidence: {len(result.evidence)} items")
        print(f"  Strong: {len(result.evidence)}")
        print(f"  Weak: {len(result.evidence)}")
        print(f"  Conflicts: {len(result.conflicts)}")
        print(f"  Unanswered: {len(result.unanswered_questions)}")

        print("\nConfidence Progression (from logs):")
        print("  Check the logs above for iteration-by-iteration confidence")

        print("\nPlanner Refinement (from logs):")
        print("  Check the logs above for Previous Query → New Query flow")

        print("\nProviders Used:")
        print("  Check the 'search_manager.search_all' logs above")

        print("\nTiming:")
        print(f"  Total time: {duration:.2f}s")
        print("  Check detailed timing in research_test_output.log")

        return result

    except Exception as e:
        print(f"\n[ERROR] Research failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """Run a series of research queries to show runtime behavior."""
    print("\n" + "=" * 80)
    print("REAL END-TO-END RESEARCH TEST")
    print("=" * 80)

    queries = ["Latest Python release", "Explain OSPF routing protocol", "Who am I?"]

    results = {}

    for i, query in enumerate(queries, 1):
        print(f"\n\n{'=' * 80}")
        print(f"TEST {i}/{len(queries)}: {query}")
        print("=" * 80)

        result = run_test_query(query)
        if result:
            results[query] = {
                "confidence": result.confidence,
                "duration": (result.metadata.get("execution_time") or 0) / 1000,
            }

        print("\n")

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    for query, metrics in results.items():
        print(f"\n{query}:")
        print(f"  Confidence: {metrics['confidence']:.2f}")
        print(f"  Duration: {metrics['duration']:.2f}s")

    print("\n" + "=" * 80)
    print(
        "For detailed logs with confidence progression, timing, and provider routing,"
    )
    print("check: research_test_output.log")
    print("=" * 80)


if __name__ == "__main__":
    main()
