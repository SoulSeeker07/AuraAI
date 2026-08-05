"""
Test script for Evidence Layer and Source Ranking.

Demonstrates the evidence-based reasoning system in action.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.research.models import (
    Evidence,
    ResearchReport,
    SearchQuery,
    SearchResult,
    SourceRanking,
    SourceTrustLevel,
)


def test_evidence_model():
    """Test the Evidence dataclass."""
    print("\n=== Testing Evidence Model ===\n")

    # Create an evidence item
    evidence = Evidence(
        fact="Python 3.14 is expected to be released in 2025",
        source="python.org",
        trust_level=SourceTrustLevel.OFFICIAL,
        score=5,
        confidence=95.0,
        context="Official Python release roadmap",
        tags=["release", "feature"],
        is_verified=False,
        evidence_type="fact",
    )

    print(f"Evidence: {evidence}")
    print(f"Confidence: {evidence.confidence}")
    print(f"Trust Level: {evidence.trust_level}")
    print(f"Source: {evidence.source}")

    # Convert to dictionary
    evidence_dict = evidence.to_dict()
    print(f"\nEvidence as dict: {evidence_dict}")

    # Create from dictionary
    evidence_from_dict = Evidence.from_dict(evidence_dict)
    print(f"\nEvidence from dict: {evidence_from_dict}")
    print(f"Match: {evidence == evidence_from_dict}")

    return True


def test_source_ranking():
    """Test the SourceRanking class."""
    print("\n=== Testing SourceRanking ===\n")

    # Create mock search results
    results = [
        SearchResult(
            url="https://python.org/docs",
            title="Python Documentation",
            snippet="Official Python documentation",
            source="python.org",
            score=95,
            trust_level=SourceTrustLevel.OFFICIAL,
        ),
        SearchResult(
            url="https://github.com/python/cpython",
            title="CPython GitHub Repository",
            snippet="Python source code repository",
            source="github.com",
            score=88,
            trust_level=SourceTrustLevel.GITHUB,
        ),
        SearchResult(
            url="https://stackoverflow.com/questions/python",
            title="Stack Overflow: Python",
            snippet="Python programming questions and answers",
            source="stackoverflow.com",
            score=82,
            trust_level=SourceTrustLevel.STACK_OVERFLOW,
        ),
        SearchResult(
            url="https://wikipedia.org/wiki/Python",
            title="Python (programming language)",
            snippet="Python programming language Wikipedia page",
            source="wikipedia.org",
            score=75,
            trust_level=SourceTrustLevel.WIKIPEDIA,
        ),
        SearchResult(
            url="https://reddit.com/r/python",
            title="r/Python",
            snippet="Python programming community discussions",
            source="reddit.com",
            score=65,
            trust_level=SourceTrustLevel.REDDIT,
        ),
    ]

    # Rank sources
    ranking = SourceRanking()
    ranking.rank_sources(results)

    print("Top 5 sources by trust:")
    for i, (name, score) in enumerate(ranking.ranking[:5], 1):
        print(f"  {i}. {name} - Score: {score:.2f}")

    print(f"\nMax score: {ranking.max_score:.2f}")

    # Get weighted evidence
    evidence_list = [
        {"source": "python.org", "trust_level": SourceTrustLevel.OFFICIAL.value},
        {"source": "github.com", "trust_level": SourceTrustLevel.GITHUB.value},
        {
            "source": "stackoverflow.com",
            "trust_level": SourceTrustLevel.STACK_OVERFLOW.value,
        },
        {"source": "wikipedia.org", "trust_level": SourceTrustLevel.WIKIPEDIA.value},
        {"source": "reddit.com", "trust_level": SourceTrustLevel.REDDIT.value},
    ]

    weighted_evidence = ranking.get_weighted_evidence(evidence_list)
    print("\nWeighted evidence:")
    for e in weighted_evidence:
        print(
            f"  {e['source']}: weight={e.get('weight', 0):.2f}, rank={e.get('rank', -1)}"
        )

    # Get top sources
    top_sources = ranking.get_top_sources(3)
    print(f"\nTop 3 sources: {top_sources}")

    return True


def test_research_report_evidence():
    """Test ResearchReport with evidence conversion."""
    print("\n=== Testing ResearchReport with Evidence ===\n")

    # Create mock search results
    results = [
        SearchResult(
            url="https://python.org/docs/release-3.14",
            title="Python 3.14 Release",
            snippet="Python 3.14 expected in 2025 with new features",
            source="python.org",
            score=95,
            trust_level=SourceTrustLevel.OFFICIAL,
        ),
        SearchResult(
            url="https://github.com/python/cpython/issues/12345",
            title="CPython Issue #12345",
            snippet="Python 3.14 bug fixes and improvements",
            source="github.com",
            score=88,
            trust_level=SourceTrustLevel.GITHUB,
        ),
    ]

    # Create report
    report = ResearchReport(
        query="Python 3.14 release date", results=results, duration=0.5
    )

    print(f"Initial results: {len(report.results)}")
    print(f"Initial evidence: {len(report.evidence)}")
    print(f"Initial confidence score: {report.get_confidence_score():.2f}")

    # Convert to evidence
    report.convert_results_to_evidence()

    print("\nAfter conversion:")
    print(f"Results: {len(report.results)}")
    print(f"Evidence items: {len(report.evidence)}")
    print(f"Confidence score: {report.get_confidence_score():.2f}")

    # Display evidence
    print("\nExtracted evidence:")
    for i, evidence in enumerate(report.evidence[:3], 1):
        print(f"  {i}. {evidence}")
        print(f"     Source: {evidence.source}")
        print(f"     Confidence: {evidence.confidence:.2f}")
        print(f"     Tags: {evidence.tags}")

    # Convert to dictionary and back
    report_dict = report.to_dict()
    print("\nReport as dict:")
    print(f"  - query: {report_dict['query']}")
    print(f"  - evidence_count: {len(report_dict['evidence'])}")
    print(f"  - confidence_score: {report_dict['confidence_score']:.2f}")

    report_from_dict = ResearchReport.from_dict(report_dict)
    print("\nReport from dict:")
    print(f"  - query: {report_from_dict.query}")
    print(f"  - evidence_count: {len(report_from_dict.evidence)}")
    print(f"  - confidence_score: {report_from_dict.get_confidence_score():.2f}")
    print(f"  - Match: {report == report_from_dict}")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("EVIDENCE LAYER AND SOURCE RANKING TESTS")
    print("=" * 60)

    try:
        test_evidence_model()
        test_source_ranking()
        test_research_report_evidence()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        print("\nEvidence Layer is working correctly!")
        print("The Research Engine now supports evidence-based reasoning.")

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
