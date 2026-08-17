"""
Tests for Research Capability Provider and ResearchEngineBackend (Milestone 21)
================================================================================
Location: tests/research/test_research_capabilities.py

Verifies:
1. ResearchCapabilityProvider descriptor schemas, liveness, and DAG semantics.
2. ResearchEngineBackend dispatch for search, synthesize, and deep_query.
3. Explicit offline / mock mode stamping and [Offline / Mock Search] observation prefix.
4. Fail-closed guardrails on empty search query, zero sources, and low confidence.
"""

from unittest.mock import MagicMock

import pytest

from core.backends.adapters.research_backend import ResearchEngineBackend
from core.capabilities.models import ActionRisk
from core.capabilities.providers.research_provider import ResearchCapabilityProvider
from research.models import MIN_SYNTHESIS_CONFIDENCE_THRESHOLD, SearchResult, SourceTrustLevel
from research.research_engine import ResearchEngine


def test_research_capability_provider_descriptors():
    """Verify research capability descriptors have correct live, risk, and DAG requirements."""
    provider = ResearchCapabilityProvider()
    caps = {c.name: c for c in provider.list_capabilities()}

    assert "research.search" in caps
    assert "research.synthesize" in caps
    assert "research.deep_query" in caps

    # 1. research.search: read-only producer (requires=[], verifies=[])
    search_cap = caps["research.search"]
    assert search_cap.is_live is True
    assert search_cap.availability == "online"
    assert search_cap.risk_level == ActionRisk.LOW
    assert search_cap.requires == []
    assert search_cap.verifies == []

    # 2. research.synthesize: consumer of search results (requires=["research.search"], verifies=[])
    synth_cap = caps["research.synthesize"]
    assert synth_cap.is_live is True
    assert synth_cap.availability == "online"
    assert synth_cap.risk_level == ActionRisk.LOW
    assert synth_cap.requires == ["research.search"]
    assert synth_cap.verifies == []

    # 3. research.deep_query: multi-round research loop
    deep_cap = caps["research.deep_query"]
    assert deep_cap.is_live is True
    assert deep_cap.availability == "online"
    assert deep_cap.risk_level == ActionRisk.MEDIUM
    assert deep_cap.requires == ["research.search", "research.synthesize"]
    assert deep_cap.verifies == []


def test_research_backend_search_with_offline_mock_stamping():
    """Verify research.search in offline mode stamps metadata and uses [Offline / Mock Search] prefix."""
    engine = ResearchEngine()
    engine.search_manager.enabled_providers = []  # Force offline mock path
    backend = ResearchEngineBackend(engine=engine)

    result = backend.execute(
        capability="research.search",
        goal="Search for latest developments in transformer architectures",
        arguments={"query": "transformer architectures", "max_results": 3},
    )

    assert result.success is True
    assert len(result.observations) > 0
    assert "[Offline / Mock Search]" in result.observations[0]
    assert result.data.get("offline_mode") is True
    assert result.data.get("is_mock") is True
    assert result.data.get("provider") == "mock"
    assert result.data.get("count") == 3
    assert len(result.data.get("results")) == 3


def test_research_backend_search_fails_closed_on_empty_query():
    """Verify research.search fails closed on blank or empty query."""
    backend = ResearchEngineBackend()

    result = backend.execute(
        capability="research.search",
        goal="",
        arguments={"query": "   "},
    )

    assert result.success is False
    assert "Empty query" in result.data.get("error", "") or "Empty query" in result.observations[0]


def test_research_backend_synthesize_fails_closed_on_zero_sources():
    """Verify research.synthesize fails closed when no sources are passed."""
    backend = ResearchEngineBackend()

    result = backend.execute(
        capability="research.synthesize",
        goal="Synthesize quantum findings",
        arguments={"topic": "Quantum Computing", "sources": []},
    )

    assert result.success is False
    assert "Zero sources provided" in result.data.get("error", "") or "Zero sources" in result.observations[0]


def test_research_backend_synthesize_fails_closed_on_low_confidence():
    """Verify research.synthesize fails closed when evidence score is below MIN_SYNTHESIS_CONFIDENCE_THRESHOLD."""
    backend = ResearchEngineBackend()

    # Create low-quality ungrounded sources (score = 10.0 -> normalized to 0.10 < 0.40)
    low_quality_sources = [
        SearchResult(
            url="https://unverified-blog.internal/post1",
            title="Speculative Post",
            snippet="Uncorroborated rumor.",
            source="unknown",
            score=15.0,
            trust_level=SourceTrustLevel.BLOG,
        )
    ]

    result = backend.execute(
        capability="research.synthesize",
        goal="Synthesize unverified rumor",
        arguments={"topic": "Rumor Topic", "sources": low_quality_sources},
    )

    assert result.success is False
    assert result.data.get("low_confidence") is True
    assert f"below minimum threshold ({MIN_SYNTHESIS_CONFIDENCE_THRESHOLD:.2f})" in result.data.get("error", "")


def test_research_backend_synthesize_succeeds_on_credible_sources():
    """Verify research.synthesize successfully merges credible sources into a cited summary."""
    backend = ResearchEngineBackend()

    sources = [
        SearchResult(
            url="https://docs.python.org/3.14/whatsnew/3.14.html",
            title="What's New in Python 3.14",
            snippet="Python 3.14 introduces substantial performance improvements and cleaner typing.",
            source="official_docs",
            score=95.0,
            trust_level=SourceTrustLevel.OFFICIAL,
        ),
        SearchResult(
            url="https://peps.python.org/pep-0700/",
            title="PEP 700 - Type System Refinement",
            snippet="PEP 700 standardizes advanced type checking behaviors across static analyzers.",
            source="python_pep",
            score=90.0,
            trust_level=SourceTrustLevel.OFFICIAL,
        ),
    ]

    result = backend.execute(
        capability="research.synthesize",
        goal="Synthesize Python 3.14 features",
        arguments={"topic": "Python 3.14 Key Features", "sources": sources},
    )

    assert result.success is True
    assert result.confidence >= MIN_SYNTHESIS_CONFIDENCE_THRESHOLD
    assert "Synthesized findings for 'Python 3.14 Key Features'" in result.observations[0]
    assert len(result.data.get("citations", [])) >= 2
    assert "What's New in Python 3.14" in result.observations[0]
