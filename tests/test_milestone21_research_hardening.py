"""
Milestone 21: Research & Knowledge Engine Hardening Test Suite
============================================================
Location: tests/test_milestone21_research_hardening.py

Verifies the 8 Acceptance Gates for M21:
- G1: Live request path through MasterOrchestrator
- G2: Evidence grounding (claim_id <-> citation_key <-> source_url <-> evidence)
- G3: Citation preservation across Result Fusion (ResultMerger) into final response
- G4: Cognitive Memory consolidation with full provenance metadata
- G5: Zero-refetch invariant: related follow-up answered from memory with 0 provider calls
- G6: Per-provider resilience: timeout/rate-limit of Provider A with success of Provider B
- G7: Security: NetworkPolicy destination evaluation & SSRF prevention
- G8: Production deep_query capability verification
"""

import asyncio
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.backends.adapters.research_backend import ResearchEngineBackend
from core.backends.backend_registry import BackendRegistry
from core.orchestration.agent_session import AgentSession, ExecutionBudget
from core.orchestration.decision_engine import DecisionEngine, IntentType
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.result_merger import ResultMerger
from core.orchestration.task_decomposer import TaskDecomposer
from memory.cognitive_memory import CognitiveMemoryEngine
from memory.consolidation_engine import ConsolidationEngine
from memory.models import MemoryItem, MemoryType, ProvenanceSource
from research.models import Citation, Evidence, SearchQuery, SearchResult, SourceTrustLevel
from research.provider_interface import ResearchProvider
from research.research_engine import ResearchEngine
from research.search_manager import SearchManager


class DummyProvider(ResearchProvider):
    """Mock research provider for deterministic testing."""

    def __init__(self, name: str, results: list[SearchResult] | None = None, fail: bool = False, delay: float = 0.0):
        self._name_str = name
        self._results = results or []
        self._fail = fail
        self._delay = delay
        self.call_count = 0
        super().__init__(config={})

    def _get_name(self) -> str:
        return self._name_str

    def is_available(self) -> bool:
        return True

    def _get_trust_level(self) -> str:
        return SourceTrustLevel.OFFICIAL.value

    def search(self, query: str, max_results: int = 5, **kwargs) -> list[SearchResult]:
        self.call_count += 1
        if self._fail:
            raise RuntimeError(f"Provider {self._name_str} timed out or reached rate limit.")
        return self._results[:max_results]


@pytest.fixture
def temp_db():
    tmp = tempfile.mkdtemp(prefix="aura_m21_test_")
    db_path = os.path.join(tmp, "m21_memory.db")
    yield db_path
    shutil.rmtree(tmp, ignore_errors=True)


# ── G1 & G2: Live Request Path & Evidence Grounding ──────────────────────────


@pytest.mark.asyncio
async def test_g1_g2_live_research_pipeline_and_evidence_grounding(temp_db):
    """
    G1 & G2: Request reaches research through MasterOrchestrator and every
    factual claim binds to a resolvable citation key and URL.
    """
    sample_results = [
        SearchResult(
            url="https://python.org/news/314",
            title="Python 3.14 Official Release",
            snippet="Python 3.14 introduces JIT compilation and free-threaded execution by default.",
            source="python_org",
            score=95,
            trust_level=SourceTrustLevel.OFFICIAL,
        ),
        SearchResult(
            url="https://github.com/python/cpython",
            title="CPython Source Repository",
            snippet="CPython repository tracking core interpreter changes and performance improvements.",
            source="github",
            score=90,
            trust_level=SourceTrustLevel.GITHUB,
        ),
    ]

    mock_provider = DummyProvider("mock_python_provider", results=sample_results)
    engine = ResearchEngine()
    engine.search_manager = SearchManager([mock_provider])
    backend = ResearchEngineBackend(engine=engine)

    backend_registry = BackendRegistry()
    backend_registry.register(backend)

    orchestrator = MasterOrchestrator(
        backend_registry=backend_registry,
        memory_db_path=temp_db,
    )

    result = await orchestrator.process_request_async("Research the latest features in Python 3.14")

    assert result.success is True, f"Orchestrator execution failed: {result.observations}"
    assert mock_provider.call_count >= 1, "Provider should have been called on live path."

    # Verify G2: Evidence Grounding (claim_id <-> citation_key <-> source_url)
    res_data = result.data
    citations = res_data.get("citations", [])
    claims = res_data.get("claims", [])

    assert len(citations) >= 2, f"Expected at least 2 citations, got: {citations}"
    assert len(claims) >= 2, f"Expected claims extracted, got: {claims}"

    # Verify each claim references a resolvable citation key and URL
    citation_keys = {c.get("key"): c for c in citations if isinstance(c, dict)}
    for claim in claims:
        assert "claim_id" in claim
        assert "citations" in claim
        for cit_key in claim["citations"]:
            assert cit_key in citation_keys, f"Claim key {cit_key} not in {citation_keys.keys()}"
            matched_cit = citation_keys[cit_key]
            assert matched_cit.get("url") in [
                "https://python.org/news/314",
                "https://github.com/python/cpython",
            ]


# ── G3: Citation Preservation Invariant Across Result Fusion ─────────────────


def test_g3_citation_preservation_through_result_merger():
    """
    G3: Citations survive search -> synthesis -> ResultMerger -> final response without loss.
    """
    merger = ResultMerger()
    session = AgentSession(goal="Research Quantum Computing Advances")

    citations_payload = [
        {
            "key": "[1]",
            "url": "https://nature.com/articles/quantum-2026",
            "domain": "nature.com",
            "title": "Quantum Supremacy in 2026",
            "snippet": "Fault-tolerant qubits demonstrate exponential speedup.",
            "score": 98,
        },
        {
            "key": "[2]",
            "url": "https://arxiv.org/abs/2601.12345",
            "domain": "arxiv.org",
            "title": "Topological Qubits Architecture",
            "snippet": "Braiding non-Abelian anyons for noise resilience.",
            "score": 92,
        },
    ]

    claims_payload = [
        {
            "claim_id": "c1",
            "text": "Fault-tolerant qubits demonstrate exponential speedup.",
            "citations": ["[1]"],
            "source_url": "https://nature.com/articles/quantum-2026",
            "domain": "nature.com",
        }
    ]

    # Add research artifact to session
    from core.orchestration.artifact import Artifact

    art = Artifact(
        artifact_id="art_research_synthesis",
        artifact_type="research",
        content={
            "topic": "Quantum Computing Advances",
            "summary": "Recent advances in fault-tolerant qubits [1] and topological braiding [2].",
            "claims": claims_payload,
            "citations": citations_payload,
            "confidence_score": 0.95,
        },
    )
    session.add_artifact(art)

    # Add observation with inline citations
    from core.orchestration.observation import Observation

    session.add_observation(
        Observation(
            obs_type="research",
            source="research_engine",
            confidence=0.95,
            content=(
                "✓ Synthesized findings for 'Quantum Computing Advances':\n\n"
                "Recent advances in fault-tolerant qubits [1].\n\n"
                "Sources & Citations:\n"
                "[1] [Quantum Supremacy in 2026](https://nature.com/articles/quantum-2026)\n"
                "[2] [Topological Qubits Architecture](https://arxiv.org/abs/2601.12345)"
            ),
        )
    )

    merged = merger.merge_session(session, success=True)

    # Verify G3 invariant
    assert merged.success is True
    assert "citations" in merged.data, "Citations missing from merged.data"
    assert len(merged.data["citations"]) == 2
    assert merged.data["citations"][0]["key"] == "[1]"
    assert merged.data["citations"][0]["url"] == "https://nature.com/articles/quantum-2026"
    assert "[1]" in merged.observations[0]
    assert "https://nature.com/articles/quantum-2026" in merged.observations[0]


# ── G4: Cognitive Memory Consolidation with Provenance ───────────────────────


def test_g4_cognitive_memory_provenance():
    """
    G4: Verified research facts persist through CognitiveMemory with full provenance metadata.
    """
    consolidation = ConsolidationEngine()
    session_id = "session_research_test_101"
    goal = "Research AI Safety Benchmarks"
    citations = [
        {
            "key": "[1]",
            "url": "https://safety.ai/benchmarks",
            "domain": "safety.ai",
            "title": "Standard AI Safety Benchmarks 2026",
            "snippet": "New red-teaming benchmarks evaluate agent containment.",
            "score": 90,
        }
    ]
    claims = [
        {
            "claim_id": "c1",
            "text": "New red-teaming benchmarks evaluate agent containment.",
            "citations": ["[1]"],
            "source_url": "https://safety.ai/benchmarks",
        }
    ]

    data = {
        "backend": "research_engine",
        "topic": "AI Safety Benchmarks",
        "summary": "Agent containment benchmarks established across major frontier models.",
        "citations": citations,
        "claims": claims,
        "confidence_score": 0.94,
    }
    observations = ["✓ Synthesized findings for 'AI Safety Benchmarks'"]

    consolidated = consolidation.consolidate_session(
        session_id=session_id,
        goal=goal,
        execution_success=True,
        observations=observations,
        data=data,
        project_id="security_lab",
    )

    # Filter semantic memory
    sem_items = [m for m in consolidated if m.type == MemoryType.SEMANTIC]
    assert len(sem_items) >= 1, "Semantic memory item was not created from research outcome"

    sem = sem_items[0]
    assert sem.topic == "research:AI Safety Benchmarks"
    assert "Agent containment benchmarks established" in sem.content
    assert sem.provenance.source_type == ProvenanceSource.EXECUTION_RESULT
    assert sem.provenance.source_id == session_id
    assert sem.provenance.verified is True
    assert sem.metadata["citations"][0]["url"] == "https://safety.ai/benchmarks"
    assert sem.metadata["sources_count"] == 1


# ── G5: Zero-Refetch Memory Invariant ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_g5_subsequent_request_recalls_research_with_zero_refetch(temp_db):
    """
    G5: First request performs live retrieval and persists research to memory.
    Second related request answers directly from memory with zero new provider calls.
    """
    sample_results = [
        SearchResult(
            url="https://astro.org/discoveries/exoplanet-k2",
            title="Exoplanet K2-18b Water Vapor Discovery",
            snippet="Spectroscopic analysis reveals significant atmospheric water vapor and methane.",
            source="astro_org",
            score=96,
            trust_level=SourceTrustLevel.OFFICIAL,
        )
    ]

    mock_provider = DummyProvider("mock_astro_provider", results=sample_results)
    engine = ResearchEngine()
    engine.search_manager = SearchManager([mock_provider])
    backend = ResearchEngineBackend(engine=engine)

    backend_registry = BackendRegistry()
    backend_registry.register(backend)

    orchestrator = MasterOrchestrator(
        backend_registry=backend_registry,
        memory_db_path=temp_db,
    )

    # 1. First Request: Live retrieval
    res1 = await orchestrator.process_request_async("Research the atmosphere of exoplanet K2-18b")
    assert res1.success is True
    assert mock_provider.call_count == 1, "Provider should be called once on first request"

    # Reset call count
    mock_provider.call_count = 0

    # 2. Second Request: Follow-up question on same topic
    res2 = await orchestrator.process_request_async("What did we find earlier about exoplanet K2-18b atmosphere?")
    assert res2.success is True
    assert res2.data.get("answered_from_memory") is True or res2.data.get("zero_refetch") is True

    # Critical Assertion: Zero new provider calls!
    assert mock_provider.call_count == 0, (
        f"G5 Violation: Research provider was invoked {mock_provider.call_count} times "
        f"on follow-up request instead of fulfilling from memory!"
    )
    assert any("K2-18b" in obs or "water vapor" in obs.lower() for obs in res2.observations)


# ── G6: Per-Provider Resilience & Graceful Partial Degradation ────────────────


def test_g6_per_provider_resilience_and_partial_success():
    """
    G6: Provider A fails/times out, but Provider B succeeds -> search_all returns
    valid ranked results from Provider B rather than collapsing the entire search.
    """
    provider_a_failing = DummyProvider("failing_provider_a", fail=True)
    provider_b_healthy = DummyProvider(
        "healthy_provider_b",
        results=[
            SearchResult(
                url="https://resilience.org/data",
                title="Resilient Systems Research",
                snippet="Multi-provider fallback ensures operational continuity.",
                source="healthy_provider_b",
                score=88,
                trust_level=SourceTrustLevel.OFFICIAL,
            )
        ],
        fail=False,
    )

    search_mgr = SearchManager([provider_a_failing, provider_b_healthy])
    results = search_mgr.search_all("resilient distributed systems")

    assert len(results) >= 1, "Search should succeed partially when at least one provider succeeds"
    assert results[0].url == "https://resilience.org/data"
    assert results[0].source == "healthy_provider_b"


# ── G7: Security — Network Policy Evaluation & Destination Filtering ─────────


def test_g7_security_destination_evaluation():
    """
    G7: Search results pointing to prohibited destinations (SSRF, cloud metadata, RFC1918)
    are filtered out before synthesis.
    """
    dangerous_results = [
        SearchResult(
            url="http://169.254.169.254/latest/meta-data/",
            title="AWS Cloud Metadata",
            snippet="IAM credentials and instance identity document.",
            source="cloud_metadata",
            score=99,
            trust_level=SourceTrustLevel.UNKNOWN,
        ),
        SearchResult(
            url="https://trusted-research.edu/paper.pdf",
            title="Legitimate Academic Paper",
            snippet="Groundbreaking study on machine cognition.",
            source="academic_edu",
            score=95,
            trust_level=SourceTrustLevel.OFFICIAL,
        ),
    ]

    mock_provider = DummyProvider("security_test_provider", results=dangerous_results)
    engine = ResearchEngine()
    engine.search_manager = SearchManager([mock_provider])
    backend = ResearchEngineBackend(engine=engine)

    exec_res = backend.execute(
        capability="research.search",
        goal="Search Academic Papers",
        arguments={"query": "machine cognition"},
    )

    assert exec_res.success is True
    results = exec_res.data.get("results", [])

    # The cloud metadata result must have been filtered out by NetworkPolicyEngine!
    assert len(results) == 1
    assert results[0]["url"] == "https://trusted-research.edu/paper.pdf"
    assert not any("169.254" in r["url"] for r in results)


# ── G8: Deep Research Loop Capability Verification ───────────────────────────


@pytest.mark.asyncio
async def test_g8_deep_research_loop_capability(temp_db):
    """
    G8: Verifies research.deep_query executes multi-round reasoning and produces
    structured findings with verifiable citations and claims.
    """
    sample_results = [
        SearchResult(
            url="https://fusion.energy/iter-2026",
            title="ITER Tokamak Net Energy Progress",
            snippet="Magnetic confinement achieves Q >= 10 burning plasma regime.",
            source="fusion_energy",
            score=94,
            trust_level=SourceTrustLevel.OFFICIAL,
        )
    ]

    mock_provider = DummyProvider("fusion_provider", results=sample_results)
    engine = ResearchEngine()
    engine.search_manager = SearchManager([mock_provider])
    backend = ResearchEngineBackend(engine=engine)

    exec_res = backend.execute(
        capability="research.deep_query",
        goal="Conduct deep research on magnetic confinement fusion milestones",
        arguments={"question": "magnetic confinement fusion milestones", "rounds": 2},
    )

    assert exec_res.success is True
    assert "citations" in exec_res.data
    assert "claims" in exec_res.data
    assert len(exec_res.data["citations"]) >= 1
    assert "fusion.energy" in exec_res.data["citations"][0]["url"]
