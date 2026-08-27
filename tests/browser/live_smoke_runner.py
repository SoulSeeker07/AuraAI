"""
tests/browser/live_smoke_runner.py
==================================
Live end-to-end smoke test for Autonomous Web Engine:
1. Executes a real browser goal using live Groq API and real Playwright browser.
2. Verifies that episodic memory records the verified successful trace in Chroma.
3. Retrieves the candidate trace on repeat goal queries.
4. Exercises live staleness invalidation (hard -0.50 penalty) and logs structured audit output.
"""

import logging
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("LiveSmokeTest")

def main():
    from browser.run_browser_goal import run_browser_goal
    from browser.experience_store import BrowserExperienceStore

    store = BrowserExperienceStore.get_instance()

    print("\n" + "="*70)
    print("STEP 0: CLEANING UP PREVIOUS TEST TRACES FOR en.wikipedia.org")
    print("="*70)
    purged_count = store.purge_domain("en.wikipedia.org")
    print(f"Purged {purged_count} previous trace(s) for en.wikipedia.org")

    print("\n" + "="*70)
    print("STEP 1: EXECUTING LIVE AUTONOMOUS BROWSER GOAL VIA GROQ (openai/gpt-oss-120b)")
    print("="*70)

    goal = "open https://en.wikipedia.org/wiki/Python_(programming_language) and state what Python is in one sentence"
    result = run_browser_goal(goal, max_steps=10)

    print(f"Goal Status : {result.get('status')}")
    print(f"Summary     : {result.get('summary')}")
    print(f"Final URL   : {result.get('url')}")
    print(f"Action Steps: {len(result.get('steps', []))}")
    for i, s in enumerate(result.get('steps', [])):
        print(f"  Step {i+1}: {s.get('tool')} -> {s.get('args')}")

    assert result.get("status") == "SUCCESS", f"Expected SUCCESS but got {result.get('status')}"

    print("\n" + "="*70)
    print("STEP 2: VERIFYING EPISODIC MEMORY TRACE PERSISTENCE & RETRIEVAL")
    print("="*70)

    retrieved = store.retrieve_trace("en.wikipedia.org", "wikipedia python programming language", min_confidence=0.5)

    assert retrieved is not None, "Failed to retrieve recorded trace from Chroma!"
    trace_id = retrieved.get("trace_id")
    print(f"Retrieved Trace ID   : {trace_id}")
    print(f"Retrieved Domain     : {retrieved.get('domain')}")
    print(f"Initial Confidence   : {retrieved.get('confidence')}")
    print(f"Cached Actions Count : {len(retrieved.get('action_sequence', []))}")
    assert retrieved.get("domain") == "en.wikipedia.org"
    assert retrieved.get("confidence") == 1.0

    print("\n" + "="*70)
    print(f"STEP 3: FORCING LIVE STALE SELECTOR HARD FAILURE DISCOUNT ON {trace_id}")
    print("="*70)

    store.discount_trace(
        trace_id=trace_id,
        failure_type="hard",
        reason="Tool 'click' error: Could not find an element matching 'Obsolete Button'",
    )

    discounted = store.retrieve_trace("en.wikipedia.org", "wikipedia python programming language", min_confidence=0.4)
    assert discounted is not None, "Discounted trace not found!"
    assert discounted.get("trace_id") == trace_id, "Retrieved trace ID mismatch!"
    print(f"Discounted Trace ID  : {discounted.get('trace_id')}")
    print(f"Confidence after -0.50 penalty : {discounted.get('confidence')}")
    assert discounted.get("confidence") == 0.5, f"Expected 0.5 but got {discounted.get('confidence')}"

    # Clean up test trace
    store.purge_domain("en.wikipedia.org")

    print("\n" + "="*70)
    print("ALL LIVE SMOKE TEST GATES VERIFIED: EXACT TRACE ID MATCH (RECORD -> RETRIEVE -> DISCOUNT)")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
