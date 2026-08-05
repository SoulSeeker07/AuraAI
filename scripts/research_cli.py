"""
Research CLI

Command-line interface for testing the Research Engine.
"""

import logging
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from research import ResearchConfig, ResearchEngine, SearchMode

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI function."""
    print("=" * 60)
    print("AuraAI Research Engine - CLI Test")
    print("=" * 60)
    print()

    # Check if research is needed for given queries
    research_queries = [
        "latest NVIDIA driver",
        "best AI coding assistant",
        "how to configure Palo Alto VPN",
        "what is OSPF routing",
    ]

    engine = ResearchEngine(
        config=ResearchConfig(enabled=True, default_mode=SearchMode.STANDARD)
    )

    for query in research_queries:
        print(f"\n{'─' * 60}")
        print(f"Query: {query}")
        print(f"{'─' * 60}")

        # Check if research is needed
        if engine.is_research_needed(query):
            print(f"✓ Research needed for: {query}")

            try:
                # Perform research
                report = engine.research(query, mode=SearchMode.STANDARD)

                # Display results
                print("\n📊 Research Results:")
                print(f"  Total sources: {len(report.results)}")
                print(f"  Confidence score: {report.get_confidence_score():.1f}/100")
                print(f"  Duration: {report.duration:.2f}s")
                print(f"  Summary: {report.summary}")

                if report.citations:
                    print(f"\n📚 Sources ({len(report.citations)}):")
                    for i, citation in enumerate(report.citations[:5], 1):
                        print(
                            f"  {i}. [{citation.trust_level.value.upper()}] {citation.title}"
                        )
                        print(f"     URL: {citation.url}")
                        print(f"     Score: {citation.score}")

                if report.conflicts:
                    print("\n⚠️  Conflicts detected:")
                    for conflict in report.conflicts:
                        print(
                            f"  - {conflict['word']} appears in {conflict['sources']} sources"
                        )

            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print(f"✗ No research needed: {query}")

    print(f"\n{'=' * 60}")
    print("Research CLI Test Complete")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
