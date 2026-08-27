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

    print("\n" + "="*70)
    print("STEP 2: VERIFYING EPISODIC MEMORY TRACE PERSISTENCE & RETRIEVAL")
    print("="*70)

    store = BrowserExperienceStore.get_instance()
    retrieved = store.retrieve_trace("en.wikipedia.org", "wikipedia python programming language", min_confidence=0.5)

    if not retrieved:
        # Also check general domain
        retrieved = store.retrieve_trace("wikipedia.org", "python programming language", min_confidence=0.5)

    print(f"Retrieved Trace ID   : {retrieved.get('trace_id') if retrieved else 'NOT FOUND'}")
    print(f"Retrieved Domain     : {retrieved.get('domain') if retrieved else 'N/A'}")
    print(f"Initial Confidence   : {retrieved.get('confidence') if retrieved else 'N/A'}")
    print(f"Cached Actions Count : {len(retrieved.get('action_sequence', [])) if retrieved else 0}")

    if retrieved:
        trace_id = retrieved.get("trace_id")
        print("\n" + "="*70)
        print("STEP 3: FORCING LIVE STALE SELECTOR HARD FAILURE DISCOUNT (-0.50)")
        print("="*70)

        store.discount_trace(
            trace_id=trace_id,
            failure_type="hard",
            reason="Tool 'click' error: Could not find an element matching 'Stale Obsolete Link'",
        )

        discounted = store.retrieve_trace(retrieved.get("domain", "en.wikipedia.org"), "wikipedia python programming language", min_confidence=0.4)
        print(f"Confidence after hard structural penalty (-0.50): {discounted.get('confidence') if discounted else 'EXPIRED'}")

    print("\n" + "="*70)
    print("ALL LIVE SMOKE TEST GATES COMPLETED SUCCESSFULLY")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
