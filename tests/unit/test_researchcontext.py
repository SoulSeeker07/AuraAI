"""
Test ResearchContext implementation
"""

from src.research.citation_builder import CitationBuilder, CitationStyle
from src.research.models import Evidence, SourceTrustLevel
from src.research.research_context import ResearchContext, ResearchMode

print("=" * 60)
print("RESEARCHCONTEXT TEST")
print("=" * 60)

# Create evidence
evidence1 = Evidence(
    fact="Python 3.14 released on December 15, 2025",
    source="python.org",
    trust_level=SourceTrustLevel.OFFICIAL,
    score=5,
    url="https://www.python.org/downloads/release/python-3140/",
)
evidence2 = Evidence(
    fact="Python 3.14 introduces new async features",
    source="realpython.com",
    trust_level=SourceTrustLevel.GITHUB,
    score=4,
    url="https://realpython.com/python-314-new-features/",
)
evidence3 = Evidence(
    fact="Python 3.14 performance improvements over 3.13",
    source="github.com/python/cpython",
    trust_level=SourceTrustLevel.OFFICIAL,
    score=5,
    url="https://github.com/python/cpython/compare/3.13...3.14",
)

print(f"\n[+] Evidence created: {evidence1.fact}")
print(f"[+] Evidence created: {evidence2.fact}")
print(f"[+] Evidence created: {evidence3.fact}")

# Create citations
builder = CitationBuilder(config={"style": "apa"})
citations = builder.build_citations([evidence1, evidence2, evidence3])
print(f"\n[+] Citations created: {len(citations)}")

# Create ResearchContext
context = ResearchContext(
    query="What are the new features in Python 3.14?",
    mode=ResearchMode.DEEP,
    evidence=[evidence1, evidence2, evidence3],
    citations=citations,
    confidence=0.95,
    conflicts=[],
    unanswered_questions=[],
    recommendations=[],
)

print("\n[+] ResearchContext created:")
print(f"    - Query: {context.query}")
print(f"    - Mode: {context.mode.name}")
print(f"    - Evidence count: {len(context.evidence)}")
print(f"    - Citation count: {len(context.citations)}")
print(f"    - Confidence: {context.confidence:.2f}")

# Test LLM prompt generation
prompt = context.to_llm_prompt()
print(f"\n[+] LLM Prompt generated ({len(prompt)} characters):")
print("\n--- PROMPT START ---")
print(prompt[:500] + "...")
print("--- PROMPT END ---")

# Test to_dict()
dict_repr = context.to_dict()
print("\n[+] Dictionary serialization successful:")
print(f"    - Keys: {list(dict_repr.keys())}")
print(f'    - Evidence count: {len(dict_repr["evidence"])}')
print(f'    - Citation count: {len(dict_repr["citations"])}')

print("\n" + "=" * 60)
print("RESEARCHCONTEXT WORKING PERFECTLY!")
print("=" * 60)
