"""
Aura CLI Execution Trace / Activity Trace Verification Script
Location: scratch/test_cli_activity_trace.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from brain.execution_coordinator import ExecutionCoordinator
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from brain.aca.engine_interface import EngineRegistry
from core.orchestration.activity_trace_renderer import ActivityTraceRenderer


async def run_activity_trace_demo():
    print("==========================================================================")
    print("      AURA CLI ACTIVITY TRACE / OBSERVABILITY RENDERER DEMO")
    print("==========================================================================")

    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")

    coordinator = ExecutionCoordinator()

    # Scenario 1: YouTube Search & Playback Trace
    print("\n\n=== SCENARIO 1: YouTube Search & Playback ===")
    yt_map = {
        "goal": "Open Chrome and search YouTube for Python tutorial",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.youtube.com"}},
            {"engine": "browser", "action": "browser.search", "parameters": {"query": "Python tutorial"}},
            {"engine": "browser", "action": "media.play", "parameters": {"target": "first_result"}},
        ],
    }
    yt_res = await coordinator.coordinate(yt_map)

    print("\n--- LEVEL 1: COMPACT VIEW ---")
    print(yt_res.render_trace(level=1))

    print("\n--- LEVEL 2: SUMMARY VIEW ---")
    print(yt_res.render_trace(level=2))

    print("\n--- LEVEL 3: FULL DIAGNOSTIC TRACE ---")
    print(yt_res.render_trace(level=3))

    # Scenario 2: Adaptive Recovery Trace
    print("\n\n=== SCENARIO 2: Primary Failure & Adaptive Recovery Trace ===")
    rec_map = {
        "goal": "Navigate with primary URL failure and alternative URL recovery",
        "steps": [
            {
                "engine": "browser",
                "action": "browser.navigate",
                "parameters": {
                    "url": "https://unreachable_domain_xyz_9999.invalid",
                    "alternative_url": "https://www.google.com",
                },
            },
        ],
    }
    rec_res = await coordinator.coordinate(rec_map)

    print("\n--- LEVEL 3: FULL DIAGNOSTIC TRACE (WITH RECOVERY) ---")
    print(rec_res.render_trace(level=3))

    print("\n==========================================================================")
    print("                 ACTIVITY TRACE RENDERER DEMO COMPLETE")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_activity_trace_demo())
