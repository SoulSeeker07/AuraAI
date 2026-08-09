"""
Target 3 Acceptance Contract Verification Script:
"Find Meta AI on Facebook and show me the relevant result."

Validates:
- General browser interaction adaptability under UI variation
- End-to-end Facebook navigation, search, result ranking, inspection, and verification
- 3-level CLI Activity Trace rendering
Location: scratch/test_facebook_adaptive_interaction.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.brain.execution_coordinator import ExecutionCoordinator
from src.core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from src.brain.aca.engine_interface import EngineRegistry


async def run_target_3_verification():
    print("==========================================================================")
    print("     AURA TARGET 3 — FACEBOOK GENERAL BROWSER ADAPTABILITY GATE")
    print("==========================================================================")

    registry = EngineRegistry.get_instance()
    browser = PlaywrightBrowserAdapter()
    registry.register(browser, "browser")

    coordinator = ExecutionCoordinator()

    # Target 3 Execution Map
    exec_map = {
        "goal": "Find Meta AI on Facebook and show me the relevant result",
        "steps": [
            # Step 1: Ensure Chrome browser is open
            {"engine": "browser", "action": "browser.ensure_open", "parameters": {"browser": "chrome"}},
            # Step 2: Open Facebook home page
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.facebook.com"}},
            # Step 3: Search Facebook for "Meta AI"
            {"engine": "browser", "action": "social.search", "parameters": {"query": "Meta AI", "platform": "facebook"}},
            # Step 4: Inspect top relevant result candidate
            {"engine": "browser", "action": "social.inspect_result", "parameters": {"query": "Meta AI", "platform": "facebook"}},
            # Step 5: Verify Facebook DOM elements & result identity match candidate
            {"engine": "browser", "action": "social.verify_result", "parameters": {"target": "result_page"}},
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
    step3_search = res.step_results[2].data.get("candidates_count", 0)
    step4_selected = res.step_results[3].data.get("selected_result", {})
    step5_verified = res.step_results[4].data.get("dom_elements_verified")

    print("\n\n=== ACCEPTANCE CONTRACT VERIFICATION FACTS ===")
    print(f"Total Steps Executed: {len(res.step_results)}")
    print(f"Overall Success     : {res.success}")
    print(f"Candidates Detected : {step3_search}")
    print(f"Inspected Result    : '{step4_selected.get('title')}' by {step4_selected.get('author')}")
    print(f"Facebook Verified   : {step5_verified}")

    passed_contract = (
        res.success
        and len(res.step_results) == 5
        and step3_search > 0
        and bool(step4_selected.get("title"))
        and step5_verified is True
    )

    print(f"\nTarget 3 Acceptance Contract Final Result: {'✅ PASS' if passed_contract else '❌ FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_target_3_verification())
