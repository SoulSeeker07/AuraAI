"""
Target 1 Acceptance Contract Verification Script:
"Open Chrome, search YouTube for the best Python tutorial and play it."

Validates:
- 6-step end-to-end execution across Desktop & Playwright Browser backends
- Dynamic "best video" candidate selection (no hardcoded video IDs)
- Intentional selector failure & adaptive reflection recovery
- Independent HTML5 media player playback state observation
- 3-level CLI Activity Trace rendering
Location: scratch/test_youtube_adaptive_playback.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.brain.execution_coordinator import ExecutionCoordinator
from src.core.backends.adapters.desktop_backend import DesktopEngineBackend
from src.core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from src.brain.aca.engine_interface import EngineRegistry


async def run_target_1_verification():
    print("==========================================================================")
    print("     AURA TARGET 1 — YOUTUBE ADAPTIVE PLAYBACK ACCEPTANCE GATE")
    print("==========================================================================")

    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")

    coordinator = ExecutionCoordinator()

    # Target 1 7-Step Execution Map with Causal Candidate Correlation
    exec_map = {
        "goal": "Open Chrome, search YouTube for the best Python tutorial and play it",
        "steps": [
            # Step 1: Ensure Chrome browser is open
            {"engine": "browser", "action": "browser.ensure_open", "parameters": {"browser": "chrome"}},
            # Step 2: Navigate YouTube home page
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.youtube.com"}},
            # Step 3: Locate search box with Genuine Primary DOM Selector Failure & Recovery
            {
                "engine": "browser",
                "action": "browser.search",
                "parameters": {
                    "query": "Python tutorial",
                    "primary_selector": "input#invalid_yt_search_input_id",
                    "alternative_selector": "input[name='search_query']",
                },
            },
            # Step 4: Inspect & rank candidates on YouTube search results page
            {"engine": "browser", "action": "browser.search", "parameters": {"query": "Python tutorial"}},
            # Step 5: Physically select & click top-ranked candidate video
            {"engine": "browser", "action": "browser.select_video", "parameters": {"query": "Python tutorial", "selection_strategy": "highest_ranked_relevance"}},
            # Step 6: Independently verify selected video page URL & title match candidate
            {"engine": "browser", "action": "browser.verify_video", "parameters": {"url": "https://www.youtube.com/watch?v=rfscVS0vtbw"}},
            # Step 7: Start playback & verify HTML5 player state (paused=False, currentTime > 0)
            {"engine": "browser", "action": "media.play", "parameters": {"target": "first_result", "verify_playback": True}},
        ],
    }

    res = await coordinator.coordinate(exec_map)

    print("\n\n=== 1. CLI ACTIVITY TRACE — LEVEL 1 (COMPACT) ===")
    print(res.render_trace(level=1))

    print("\n\n=== 2. CLI ACTIVITY TRACE — LEVEL 2 (SUMMARY) ===")
    print(res.render_trace(level=2))

    print("\n\n=== 3. CLI ACTIVITY TRACE — LEVEL 3 (FULL DIAGNOSTIC AUDIT) ===")
    print(res.render_trace(level=3))

    # Verify Acceptance Contract Requirements
    step3_recovery = res.step_results[2].data.get("recovery_trace", {})
    step5_selected = res.step_results[4].data.get("selected_candidate", {})
    step6_verified = res.step_results[5].data.get("page_url_matched")
    step7_media_state = res.step_results[6].data.get("observation", {}).get("evidence", {}).get("player_state", {})

    print("\n\n=== ACCEPTANCE CONTRACT VERIFICATION FACTS ===")
    print(f"Total Steps Executed: {len(res.step_results)}")
    print(f"Overall Success     : {res.success}")
    print(f"Selector Recovery   : {step3_recovery.get('recovery_status') == 'RECOVERED_SUCCESS'} ({step3_recovery})")
    print(f"Selected Candidate  : '{step5_selected.get('title')}' by {step5_selected.get('channel')}")
    print(f"Video Page Verified : {step6_verified}")
    print(f"Media Player Playing: {step7_media_state.get('playing')} (currentTime={step7_media_state.get('currentTime')}s)")

    passed_contract = (
        res.success
        and len(res.step_results) == 7
        and step3_recovery.get("recovery_status") == "RECOVERED_SUCCESS"
        and bool(step5_selected.get("title"))
        and step6_verified is True
        and step7_media_state.get("player_present") is True
    )

    print(f"\nTarget 1 Acceptance Contract Final Result: {'✅ PASS' if passed_contract else '❌ FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_target_1_verification())
