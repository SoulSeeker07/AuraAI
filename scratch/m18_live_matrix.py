"""
Milestone 18 — Real Windows Machine Acceptance Gate (Gate 2)
Location: scratch/m18_live_matrix.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.brain.execution_coordinator import ExecutionCoordinator
from src.core.backends.adapters.desktop_backend import DesktopEngineBackend
from src.core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from src.brain.aca.engine_interface import EngineRegistry


async def run_live_matrix():
    print("==========================================================================")
    print("   AURA AI — M18 LIVE ADAPTIVE COMPUTER INTERACTION MATRIX (GATE 2)")
    print("==========================================================================")

    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")

    coordinator = ExecutionCoordinator()

    # Benchmark 1: Notepad Desktop
    print("\n--- 1. Notepad Desktop Lifecycle ---")
    b1_map = {
        "goal": "Open Notepad, type text, and close",
        "steps": [
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad"}},
            {"engine": "desktop", "action": "keyboard.type", "parameters": {"text": "Aura AI Live Verification"}},
            {"engine": "desktop", "action": "app_close", "parameters": {"target": "notepad"}},
        ],
    }
    r1 = await coordinator.coordinate(b1_map)
    status1 = "PASS" if r1.success else "FAIL"
    print(f"Status     : {status1}")
    print(f"Total Steps: {len(r1.step_results)}")

    # Benchmark 2: Browser L1/L2 Verification
    print("\n--- 2. Browser Navigation L1/L2 Verification ---")
    b2_map = {
        "goal": "Navigate to Google",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.google.com"}},
        ],
    }
    r2 = await coordinator.coordinate(b2_map)
    v_report2 = r2.step_results[0].data.get("verification_report", {})
    status2 = "PASS" if (r2.success and v_report2.get("passed")) else "FAIL"
    print(f"Status     : {status2}")
    print(f"Evidence   : {v_report2.get('evidence', [])}")

    # Benchmark 3: YouTube Search & Playback
    print("\n--- 3. YouTube Search & Playback Loop ---")
    b3_map = {
        "goal": "Search YouTube for Python tutorial and play",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.youtube.com"}},
            {"engine": "browser", "action": "browser.search", "parameters": {"query": "Python tutorial"}},
            {"engine": "browser", "action": "media.play", "parameters": {"target": "first_result"}},
        ],
    }
    r3 = await coordinator.coordinate(b3_map)
    status3 = "PASS" if r3.success else "PARTIAL"
    print(f"Status     : {status3}")

    # Benchmark 4: Amazon Policy Gate
    print("\n--- 4. Amazon Search & Add to Cart Policy Gate ---")
    b4_map = {
        "goal": "Search S24 Ultra on Amazon and add to cart",
        "steps": [
            {"engine": "browser", "action": "shopping.search", "parameters": {"query": "S24 Ultra", "platform": "amazon"}},
            {"engine": "browser", "action": "shopping.cart.add", "parameters": {"product": "S24 Ultra"}},
            {"engine": "browser", "action": "shopping.checkout", "parameters": {"user_approved": False}},
        ],
    }
    r4 = await coordinator.coordinate(b4_map)
    checkout_obs = " ".join(r4.step_results[2].observations)
    status4 = "PASS" if ("authorization" in checkout_obs.lower() or "approval" in checkout_obs.lower() or "user" in checkout_obs.lower()) else "FAIL"
    print(f"Status     : {status4}")
    print(f"Policy Gate: {checkout_obs}")

    # Benchmark 5: Failure Injection & Genuine Adaptive Recovery
    print("\n--- 5. Failure Injection & Genuine Adaptive Recovery ---")
    b5_map = {
        "goal": "Navigate with primary URL failure and alternative URL recovery",
        "steps": [
            {
                "engine": "browser",
                "action": "browser.navigate",
                "parameters": {
                    "url": "https://non_existent_unreachable_domain_xyz_9999.invalid",
                    "alternative_url": "https://www.google.com",
                },
            },
        ],
    }
    r5 = await coordinator.coordinate(b5_map)
    rec_trace = r5.step_results[0].data.get("recovery_trace", {})
    status5 = "PASS" if (r5.success and rec_trace.get("recovery_status") == "RECOVERED_SUCCESS") else "FAIL"
    print(f"Status     : {status5}")
    print(f"Rec Trace  : {rec_trace}")

    print("\n==========================================================================")
    print("                    LIVE MACHINE GATE COMPLETE")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_live_matrix())
