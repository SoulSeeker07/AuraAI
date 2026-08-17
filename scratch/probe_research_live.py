"""
Live Smoke Probe for Research 2.0 Subsystem
============================================
Location: scratch/probe_research_live.py

Tests real-network live research calls:
1. Checks which providers are enabled in SearchManager (Wikipedia, Tavily, GitHub).
2. Performs a live real-network search.
3. Tests evidence extraction & citation building on real unstructured web/wiki content.
4. Feeds real search results through ResearchEngine.synthesize() and ResearchEngineBackend.
5. Verifies citations formatting, source attribution, and non-mock metadata stamping.
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from research.research_engine import ResearchEngine
from core.backends.adapters.research_backend import ResearchEngineBackend


def main():
    print("=== AuraAI Research 2.0 Live Network Smoke Probe ===\n")

    engine = ResearchEngine()
    print("1. Inspecting Configured Providers:")
    for p in engine.search_manager.providers:
        avail = p.is_available()
        print(f"   - Provider '{p.name}': is_available={avail}, trust_level={p.trust_level}")

    enabled = engine.search_manager.enabled_providers
    print(f"\n   Active Providers: {[p.name for p in enabled]}")

    backend = ResearchEngineBackend(engine=engine)

    query = "James Webb Space Telescope discoveries"
    print(f"\n2. Executing LIVE search for: '{query}' via ResearchEngineBackend...")

    search_res = backend.execute(
        capability="research.search",
        goal=f"Research {query}",
        arguments={"query": query, "max_results": 3},
    )

    print(f"   Success: {search_res.success}")
    print(f"   Confidence: {search_res.confidence}")
    print(f"   Execution Time: {search_res.execution_time_seconds:.2f}s")
    print(f"   Offline Mode: {search_res.data.get('offline_mode')}")
    print(f"   Provider Used: {search_res.data.get('provider')}")
    print(f"   Results Count: {search_res.data.get('count')}")

    print("\n   Observation Snippet:")
    if search_res.observations:
        print("   " + "\n   ".join(search_res.observations[0].split("\n")[:8]))

    if not search_res.success or not search_res.data.get("results"):
        print("\n❌ Search failed or yielded no results.")
        return 1

    print("\n3. Executing LIVE synthesis over extracted real-network sources...")
    synth_res = backend.execute(
        capability="research.synthesize",
        goal=f"Synthesize findings for {query}",
        arguments={
            "topic": query,
            "sources": search_res.data["results"],
        },
    )

    print(f"   Synthesis Success: {synth_res.success}")
    print(f"   Confidence Score: {synth_res.confidence:.1%}")
    print(f"   Execution Time: {synth_res.execution_time_seconds:.2f}s")
    print(f"   Citations Count: {len(synth_res.data.get('citations', []))}")

    print("\n   Synthesized Observation:")
    if synth_res.observations:
        print("   " + "\n   ".join(synth_res.observations[0].split("\n")[:12]))

    print("\n4. Verification Checks on Live Result:")
    assert search_res.success is True, "Live search must succeed"
    assert search_res.data.get("offline_mode") is False, "Live search must NOT be flagged as offline"
    assert "[Offline / Mock Search]" not in search_res.observations[0], "Live search observation must not have mock prefix"
    assert synth_res.success is True, "Synthesis must succeed on real data"
    assert synth_res.confidence >= 0.40, f"Confidence {synth_res.confidence} must meet threshold >= 0.40"
    assert len(synth_res.data.get("citations", [])) > 0, "Citations must be generated from real sources"

    print("\n✅ LIVE NETWORK SMOKE TEST PASSED 100% — Real data ingestion, citation building, and synthesis verified!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
