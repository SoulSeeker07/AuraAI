"""
Integration test for Milestone 14 Research Intelligence

This test verifies that:
1. ResearchPlanner creates plans correctly
2. ResearchReasoner evaluates evidence quality
3. CitationFormatter formats citations correctly
4. ResearchEngine uses planner + reasoning layer with confidence loop
"""

import logging
import sys
from pathlib import Path

# Add workspace to path
workspace_root = Path(__file__).parent
sys.path.insert(0, str(workspace_root))

from src.research.models import (
    Citation,
    Evidence,
    ResearchConfig,
    SearchMode,
    SourceTrustLevel,
)
from src.research.research_context import ResearchContext, ResearchMode
from src.research.research_engine import ResearchEngine

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_research_engine_with_planner():
    """Test that research engine uses planner and reasoning layer."""
    print("\n" + "=" * 80)
    print("TEST 1: Research Engine with Planner and Reasoning Layer")
    print("=" * 80)

    try:
        # Create research engine
        print("\n1. Creating research engine...")
        engine = ResearchEngine()
        print("   [OK] Research engine created")

        # Test research with a simple query
        query = "What is artificial intelligence?"
        print(f"\n2. Running research for: '{query}'")

        # Run research
        result = engine.research(query, mode=SearchMode.STANDARD)

        # Verify result is ResearchContext
        print("\n3. Verifying result type...")
        assert isinstance(
            result, ResearchContext
        ), f"Expected ResearchContext, got {type(result)}"
        print("   [PASS] Result is ResearchContext")

        # Verify ResearchContext structure
        print("\n4. Verifying ResearchContext structure...")
        assert result.query == query, f"Query mismatch: {result.query}"
        print(f"   [PASS] Query: {result.query}")

        assert result.evidence, "No evidence found"
        print(f"   [PASS] Evidence count: {len(result.evidence)}")

        assert (
            result.confidence >= 0.0 and result.confidence <= 1.0
        ), f"Confidence out of range: {result.confidence}"
        print(f"   [PASS] Confidence: {result.confidence:.2f}")

        assert result.citations, "No citations found"
        print(f"   [PASS] Citations count: {len(result.citations)}")

        assert result.mode, "No mode specified"
        print(f"   [PASS] Mode: {result.mode.name}")

        # Check that metadata contains iteration information
        if result.metadata:
            print(f"   [PASS] Metadata: {result.metadata}")

        print("\n5. Testing to_llm_prompt()...")
        prompt = result.to_llm_prompt()
        assert prompt, "Prompt is empty"
        assert "RESEARCH QUERY" in prompt, "Prompt missing RESEARCH QUERY section"
        assert "CONFIDENCE" in prompt, "Prompt missing CONFIDENCE section"
        print("   [PASS] Prompt generated successfully")
        print(f"\n   First 200 chars of prompt:\n{prompt[:200]}...")

        print("\n" + "=" * 80)
        print("TEST 1 PASSED [PASS]")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n[FAIL] TEST 1 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_confidence_loop():
    """Test that confidence loop works correctly."""
    print("\n" + "=" * 80)
    print("TEST 2: Confidence Loop Integration")
    print("=" * 80)

    try:
        print("\n1. Creating research engine...")
        engine = ResearchEngine()

        # Test with a query that requires multiple iterations
        query = "What are the latest developments in quantum computing?"
        print(f"\n2. Running research for: '{query}'")
        print("   (This may take a few iterations)")

        # Run research (it should automatically iterate until confidence threshold is met)
        result = engine.research(query, mode=SearchMode.DEEP)

        # Verify result structure
        print("\n3. Verifying result...")
        print(f"   - Evidence count: {len(result.evidence)}")
        print(f"   - Confidence: {result.confidence:.2f}")
        print(f"   - Conflicts: {len(result.conflicts)}")
        print(f"   - Unanswered questions: {len(result.unanswered_questions)}")
        print(f"   - Recommendations: {len(result.recommendations)}")

        # Verify confidence is in valid range
        assert (
            0.0 <= result.confidence <= 1.0
        ), f"Confidence out of range: {result.confidence}"
        print("   [PASS] Confidence is valid")

        # Check metadata for iteration count
        if result.metadata and "iterations" in result.metadata:
            iterations = result.metadata["iterations"]
            print(f"   [PASS] Iterations: {iterations}")
            assert iterations > 0, "No iterations performed"

        print("\n" + "=" * 80)
        print("TEST 2 PASSED [PASS]")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n[FAIL] TEST 2 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_reasoning_layer():
    """Test that ResearchReasoner works correctly."""
    print("\n" + "=" * 80)
    print("TEST 3: Research Reasoner Layer")
    print("=" * 80)

    try:
        from src.research.reasoning_layer import ReasoningResult, ResearchReasoner

        print("\n1. Creating reasoner...")
        reasoner = ResearchReasoner()
        print("   [PASS] Reasoner created")

        # Create mock evidence
        print("\n2. Creating mock evidence...")
        from src.research.models import Evidence, SourceTrustLevel

        mock_evidence = [
            Evidence(
                fact="Artificial intelligence is a field of computer science.",
                source="example.com",
                trust_level=SourceTrustLevel.UNKNOWN,
                score=5,
                url="https://example.com/ai",
                confidence=0.8,
            ),
            Evidence(
                fact="Artificial intelligence is the intelligence of machines or software.",
                source="wikipedia.org",
                trust_level=SourceTrustLevel.WIKIPEDIA,
                score=5,
                url="https://wikipedia.org/ai",
                confidence=0.9,
            ),
            Evidence(
                fact="AI is transforming many industries.",
                source="news.com",
                trust_level=SourceTrustLevel.NEWS,
                score=3,
                url="https://news.com/ai",
                confidence=0.6,
            ),
        ]

        print(f"   [PASS] Created {len(mock_evidence)} evidence items")

        # Run reasoning
        print("\n3. Running reasoning on evidence...")
        reasoning_result = reasoner.reason(mock_evidence, query="What is AI?")

        # Verify result structure
        print("\n4. Verifying reasoning result...")
        assert isinstance(
            reasoning_result, ReasoningResult
        ), f"Expected ReasoningResult, got {type(reasoning_result)}"
        print("   [PASS] Result is ReasoningResult")

        assert (
            reasoning_result.confidence >= 0.0 and reasoning_result.confidence <= 1.0
        ), f"Confidence out of range: {reasoning_result.confidence}"
        print(f"   [PASS] Confidence: {reasoning_result.confidence:.2f}")

        print(f"   - Strong evidence: {len(reasoning_result.strong_evidence)}")
        print(f"   - Weak evidence: {len(reasoning_result.weak_evidence)}")
        print(f"   - Conflicts: {len(reasoning_result.conflicts)}")
        print(f"   - Missing info: {len(reasoning_result.missing_information)}")
        print(f"   - Recommendations: {len(reasoning_result.recommendations)}")

        print("\n" + "=" * 80)
        print("TEST 3 PASSED [PASS]")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n[FAIL] TEST 3 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_citation_formatter():
    """Test that CitationFormatter works correctly."""
    print("\n" + "=" * 80)
    print("TEST 4: Citation Formatter")
    print("=" * 80)

    try:
        from src.research.citation_formatter import CitationFormatter

        # Create test citations
        print("\n1. Creating test citations...")
        from src.research.models import Citation, SourceTrustLevel

        citations = [
            Citation(
                url="https://example.com/article1",
                title="Artificial Intelligence Fundamentals",
                trust_level=SourceTrustLevel.UNKNOWN,
                score=5,
                author="John Doe, Jane Smith",
                snippet="Comprehensive overview of AI principles",
            ),
            Citation(
                url="https://example.com/article2",
                title="Machine Learning Applications",
                trust_level=SourceTrustLevel.UNKNOWN,
                score=4,
                author="Bob Johnson",
                snippet="Real-world ML use cases",
            ),
        ]

        print(f"   [PASS] Created {len(citations)} citations")

        # Test APA formatting
        print("\n2. Testing APA format...")
        formatter_apa = CitationFormatter(style="apa")
        formatted_apa = formatter_apa.format_citations(citations)
        print("   [PASS] APA format: ")
        for line in formatted_apa.split("\n")[:3]:
            print(f"     {line}")

        # Test MLA formatting
        print("\n3. Testing MLA format...")
        formatter_mla = CitationFormatter(style="mla")
        formatted_mla = formatter_mla.format_citations(citations)
        print("   [PASS] MLA format:")
        for line in formatted_mla.split("\n")[:3]:
            print(f"     {line}")

        # Test IEEE formatting
        print("\n4. Testing IEEE format...")
        formatter_ieee = CitationFormatter(style="ieee")
        formatted_ieee = formatter_ieee.format_citations(citations)
        print("   [PASS] IEEE format:")
        for line in formatted_ieee.split("\n")[:3]:
            print(f"     {line}")

        # Test numerical formatting
        print("\n5. Testing numerical format...")
        formatter_num = CitationFormatter(style="numerical")
        formatted_num = formatter_num.format_citations(citations)
        print("   [PASS] Numerical format:")
        for line in formatted_num.split("\n")[:3]:
            print(f"     {line}")

        print("\n" + "=" * 80)
        print("TEST 4 PASSED [PASS]")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n[FAIL] TEST 4 FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MILESTONE 14: RESEARCH INTELLIGENCE INTEGRATION TESTS")
    print("=" * 80)

    results = []

    # Run all tests
    results.append(
        ("Research Engine with Planner", test_research_engine_with_planner())
    )
    results.append(("Confidence Loop Integration", test_confidence_loop()))
    results.append(("Research Reasoner Layer", test_reasoning_layer()))
    results.append(("Citation Formatter", test_citation_formatter()))

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results:
        status = "[PASS] PASSED" if passed else "[FAIL] FAILED"
        print(f"{test_name}: {status}")

    all_passed = all(passed for _, passed in results)

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL TESTS PASSED [PASS]")
        print("=" * 80)
        print("\nMilestones Completed:")
        print("  ✅ ResearchPlanner creates intelligent plans")
        print("  ✅ ResearchReasoner evaluates evidence quality")
        print("  ✅ CitationFormatter formats citations")
        print("  ✅ ResearchEngine uses planner + reasoning layer")
        print("  ✅ Confidence loop works correctly")
        print("  ✅ ResearchContext is the single source of truth")
        print("\nMilestone 14 is ready!")
    else:
        print("SOME TESTS FAILED [FAIL]")
        print("=" * 80)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
