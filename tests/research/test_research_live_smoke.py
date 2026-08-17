"""
Live Network Smoke Test for Research 2.0 Subsystem
==================================================
Location: tests/research/test_research_live_smoke.py

Verifies:
1. Active search providers are properly detected.
2. Real live network search call executes successfully against online providers (Wikipedia).
3. Non-mock metadata stamping (offline_mode=False, no mock prefix).
4. Evidence synthesis, confidence evaluation, and citation generation over live, un-curated web articles.
"""

import pytest

from core.backends.adapters.research_backend import ResearchEngineBackend
from research.models import MIN_SYNTHESIS_CONFIDENCE_THRESHOLD
from research.research_engine import ResearchEngine


@pytest.mark.live
def test_research_live_network_search_and_synthesis_smoke():
    """Execute end-to-end live network research search and synthesis against available online providers."""
    engine = ResearchEngine()
    enabled = engine.search_manager.enabled_providers

    # If no online providers are available in the test runner environment, skip
    if not enabled:
        pytest.skip("No live research provider available in environment.")

    backend = ResearchEngineBackend(engine=engine)
    query = "James Webb Space Telescope"

    # 1. Live Search
    search_res = backend.execute(
        capability="research.search",
        goal=f"Research {query}",
        arguments={"query": query, "max_results": 2},
    )

    assert search_res.success is True
    assert search_res.confidence == 1.0
    assert search_res.data.get("offline_mode") is False
    assert search_res.data.get("is_mock") is False
    assert search_res.data.get("count") > 0
    assert "[Offline / Mock Search]" not in search_res.observations[0]

    # Verify real URLs and titles
    results = search_res.data.get("results", [])
    assert len(results) > 0
    assert any("wikipedia.org" in r.get("url", "") or "http" in r.get("url", "") for r in results)

    # 2. Live Synthesis over un-curated live articles
    synth_res = backend.execute(
        capability="research.synthesize",
        goal=f"Synthesize {query}",
        arguments={"topic": query, "sources": results},
    )

    assert synth_res.success is True
    assert synth_res.confidence >= MIN_SYNTHESIS_CONFIDENCE_THRESHOLD
    assert len(synth_res.data.get("citations", [])) > 0
    assert any("http" in c.get("url", "") for c in synth_res.data["citations"])
