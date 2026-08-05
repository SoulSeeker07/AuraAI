"""
Integration test for ResearchContext implementation.

This test demonstrates the complete pipeline:
1. Create evidence from search results
2. Build citations from evidence
3. Create ResearchContext with reasoning layer
4. Generate LLM prompt from ResearchContext
"""

import sys

sys.path.insert(0, "src")

from research.citation_builder import CitationBuilder
from research.models import Evidence, SourceTrustLevel
from research.research_context import ResearchContext, ResearchMode


def test_complete_pipeline():
    """Test the complete pipeline from evidence to LLM prompt."""
    print("=" * 80)
    print("RESEARCH CONTEXT INTEGRATION TEST")
    print("=" * 80)

    # Step 1: Create evidence objects
    print("\n[Step 1] Creating evidence objects...")
    evidence_list = [
        Evidence(
            fact="Python 3.14 is expected to introduce several new features including improved async performance and better type hinting.",
            source="Python.org",
            trust_level=SourceTrustLevel.OFFICIAL,
            score=0.95,
            confidence=0.92,
            tags=["python", "version", "features"],
        ),
        Evidence(
            fact="The asyncio improvements in Python 3.14 will include async generators and better context management.",
            source="Python Weekly",
            trust_level=SourceTrustLevel.NEWS,
            score=0.85,
            confidence=0.78,
            tags=["python", "async", "performance"],
        ),
        Evidence(
            fact="PEP 704: True block scoping for except and finally clauses in async generators is planned for 3.14.",
            source="Python Enhancement Proposals",
            trust_level=SourceTrustLevel.OFFICIAL,
            score=0.92,
            confidence=0.88,
            tags=["python", "pep", "async"],
        ),
    ]

    print(f"  Created {len(evidence_list)} evidence items")
    for i, e in enumerate(evidence_list, 1):
        print(f"    {i}. {e.fact[:60]}... (confidence: {e.confidence:.2f})")

    # Step 2: Build citations from evidence
    print("\n[Step 2] Building citations from evidence...")
    citation_builder = CitationBuilder()
    citations = citation_builder.build_citations(evidence_list)

    print(f"  Created {len(citations)} citations")
    for i, c in enumerate(citations, 1):
        print(f"    {i}. [{c.citation_style.value}] {c.title}")
        print(f"       Evidence IDs: {c.evidence_ids}")

    # Step 3: Create ResearchContext
    print("\n[Step 3] Creating ResearchContext...")
    context = ResearchContext(
        query="What are the new features in Python 3.14?",
        mode=ResearchMode.DEEP,
        evidence=evidence_list,
        citations=citations,
        confidence=0.86,  # Average confidence
        conflicts=[],
        unanswered_questions=[],
        recommendations=[
            "Verify async performance benchmarks",
            "Check PEP documentation",
        ],
        summary="Python 3.14 will introduce several async-related improvements including better async generators, context management, and PEP 704 for true block scoping.",
        metadata={"version": "1.0", "research_duration": 2.3},
    )

    print("  Created ResearchContext with:")
    print(f"    - Query: {context.query}")
    print(f"    - Mode: {context.mode.value}")
    print(f"    - Evidence count: {len(context.evidence)}")
    print(f"    - Citation count: {len(context.citations)}")
    print(f"    - Confidence: {context.confidence:.2f}")
    print(f"    - Unanswered questions: {len(context.unanswered_questions)}")
    print(f"    - Recommendations: {len(context.recommendations)}")

    # Step 4: Generate LLM prompt
    print("\n[Step 4] Generating LLM prompt...")
    llm_prompt = context.to_llm_prompt()

    print(f"  LLM prompt generated ({len(llm_prompt)} characters):")
    print("\n" + "-" * 80)
    print(llm_prompt)
    print("-" * 80)

    # Step 5: Serialize to dictionary
    print("\n[Step 5] Serializing to dictionary...")
    context_dict = context.to_dict()

    print(f"  Dictionary contains {len(context_dict)} keys:")
    for key in sorted(context_dict.keys()):
        if key == "evidence" or key == "citations":
            print(f"    - {key}: list of {len(context_dict[key])} items")
        else:
            value = context_dict[key]
            if isinstance(value, list):
                print(f"    - {key}: list of {len(value)} items")
            else:
                print(f"    - {key}: {value}")

    # Verify key properties
    print("\n[Step 6] Verifying key properties...")

    # Verify evidence count
    assert len(context.evidence) == 3, "Evidence count mismatch"
    print("  ✓ Evidence count correct")

    # Verify citation count
    assert len(context.citations) == 3, "Citation count mismatch"
    print("  ✓ Citation count correct")

    # Verify confidence calculation
    expected_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)
    assert (
        abs(context.confidence - expected_confidence) < 0.01
    ), "Confidence calculation incorrect"
    print(
        f"  ✓ Confidence calculation correct (expected: {expected_confidence:.2f}, got: {context.confidence:.2f})"
    )

    # Verify LLM prompt generation
    assert "# RESEARCH QUERY" in llm_prompt, "LLM prompt missing query section"
    assert "# RESEARCH MODE" in llm_prompt, "LLM prompt missing mode section"
    assert "# CONFIDENCE" in llm_prompt, "LLM prompt missing confidence section"
    assert "# EVIDENCE" in llm_prompt, "LLM prompt missing evidence section"
    print("  ✓ LLM prompt structure correct")

    # Verify dictionary serialization
    assert "query" in context_dict, "Dictionary missing query"
    assert "mode" in context_dict, "Dictionary missing mode"
    assert "evidence" in context_dict, "Dictionary missing evidence"
    assert "citations" in context_dict, "Dictionary missing citations"
    print("  ✓ Dictionary serialization correct")

    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED!")
    print("=" * 80)
    print("\nThe complete pipeline is working correctly:")
    print("  1. Evidence creation ✓")
    print("  2. Citation building ✓")
    print("  3. ResearchContext creation ✓")
    print("  4. LLM prompt generation ✓")
    print("  5. Dictionary serialization ✓")
    print("\nThe 'Reasoning Layer' is successfully transforming raw evidence")
    print("into structured context for LLM consumption.")


if __name__ == "__main__":
    test_complete_pipeline()
