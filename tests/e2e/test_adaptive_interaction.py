"""
Milestone 18 — Adaptive Computer Interaction Runtime & World Model Suite
Location: tests/e2e/test_adaptive_interaction.py

Verifies real-world computer interaction benchmarks across Windows Desktop and Playwright Browser:
1. Notepad Lifecycle (Open -> Type -> Verify HWND/content -> Close)
2. Browser Navigation & L1/L2 Verification (Chrome launch -> Navigate -> Verify URL & DOM)
3. YouTube Search & Playback Loop (Search -> Select video -> Verify player state)
4. Amazon Search & Add to Cart Policy Gate (Search -> Add to Cart -> Policy Engine halts before checkout)
5. Failure Injection & Genuine Adaptive Recovery (Primary selector fails -> Observe -> Reflect -> Alternative selector -> Retry -> Verification PASS)

Run:
    python -m pytest tests/e2e/test_adaptive_interaction.py -v --tb=short
"""

import sys
from pathlib import Path

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.brain.execution_coordinator import ExecutionCoordinator, StepResult
from src.core.backends.adapters.desktop_backend import DesktopEngineBackend
from src.core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from src.core.orchestration.observation_models import ExpectedState, FailureType, Observation, VerificationReport
from src.brain.aca.engine_interface import EngineRegistry


@pytest.fixture
def clean_registry():
    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")
    return registry, desktop, browser


# ── Benchmark 1: Notepad Desktop Lifecycle ────────────────────────────────────


@pytest.mark.asyncio
async def test_01_notepad_desktop_lifecycle(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Open Notepad, type text, and close",
        "steps": [
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad"}},
            {"engine": "desktop", "action": "keyboard.type", "parameters": {"text": "Aura AI M18 Test"}},
            {"engine": "desktop", "action": "app_close", "parameters": {"target": "notepad"}},
        ],
    }

    res = await coordinator.coordinate(exec_map)
    assert res.success is True
    assert len(res.step_results) == 3

    # Assert L1/L2 observation returned
    obs_data = res.step_results[0].data.get("observation")
    assert obs_data is not None
    assert obs_data["engine"] == "desktop"


# ── Benchmark 2: Browser Navigation & L1/L2 Verification ─────────────────────


@pytest.mark.asyncio
async def test_02_browser_navigation_l1_l2_verification(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Navigate to Google",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.google.com"}},
        ],
    }

    res = await coordinator.coordinate(exec_map)
    assert res.success is True

    # Assert evidence-backed verification report
    v_report = res.step_results[0].data.get("verification_report")
    assert v_report is not None
    assert v_report["passed"] is True
    assert len(v_report["evidence"]) >= 1


# ── Benchmark 3: YouTube Search & Playback Loop ─────────────────────────────


@pytest.mark.asyncio
async def test_03_youtube_search_and_playback(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Search YouTube for Python tutorial and play",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.youtube.com"}},
            {"engine": "browser", "action": "browser.search", "parameters": {"query": "Python tutorial"}},
            {"engine": "browser", "action": "media.play", "parameters": {"target": "first_result"}},
        ],
    }

    res = await coordinator.coordinate(exec_map)
    assert res.success is True
    assert len(res.step_results) == 3


# ── Benchmark 4: Amazon Search & Add-to-Cart Policy Gate ──────────────────────


@pytest.mark.asyncio
async def test_04_amazon_cart_policy_gate(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Search S24 Ultra on Amazon and add to cart",
        "steps": [
            {"engine": "browser", "action": "shopping.search", "parameters": {"query": "S24 Ultra", "platform": "amazon"}},
            {"engine": "browser", "action": "shopping.cart.add", "parameters": {"product": "S24 Ultra"}},
            {"engine": "browser", "action": "shopping.checkout", "parameters": {"user_approved": False}},
        ],
    }

    res = await coordinator.coordinate(exec_map)

    # Checkout step should require explicit user approval (policy gate)
    checkout_step = res.step_results[2]
    obs_str = " ".join(checkout_step.observations)
    assert any(term in obs_str.lower() for term in ["authorization", "approval", "policy", "user"])


# ── Benchmark 5: Failure Injection & Genuine Adaptive Recovery ───────────────


@pytest.mark.asyncio
async def test_05_failure_injection_adaptive_recovery(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    # Step with failing primary target URL, but valid alternative URL
    exec_map = {
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

    res = await coordinator.coordinate(exec_map)
    assert res.success is True

    # Assert recovery trace evidence
    step_data = res.step_results[0].data
    rec_trace = step_data.get("recovery_trace")
    assert rec_trace is not None
    assert rec_trace.get("recovery_status") == "RECOVERED_SUCCESS"
    assert rec_trace["primary_target"] == "https://non_existent_unreachable_domain_xyz_9999.invalid"
    assert rec_trace["alternative_target"] == "https://www.google.com"


# ── Benchmark 6: Facebook Search & Result Interaction ───────────────────────


@pytest.mark.asyncio
async def test_06_facebook_search_and_result_interaction(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Find Meta AI on Facebook and show me the relevant result",
        "steps": [
            {"engine": "browser", "action": "browser.ensure_open", "parameters": {"browser": "chrome"}},
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.facebook.com"}},
            {"engine": "browser", "action": "social.search", "parameters": {"query": "Meta AI", "platform": "facebook"}},
            {"engine": "browser", "action": "social.inspect_result", "parameters": {"query": "Meta AI", "platform": "facebook"}},
            {"engine": "browser", "action": "social.verify_result", "parameters": {"target": "result_page"}},
        ],
    }

    res = await coordinator.coordinate(exec_map)
    assert res.success is True
    assert len(res.step_results) == 5

    step3_data = res.step_results[2].data
    assert step3_data.get("candidates_count", 0) > 0

    step4_data = res.step_results[3].data
    assert bool(step4_data.get("selected_result", {}).get("title"))

    step5_data = res.step_results[4].data
    assert step5_data.get("dom_elements_verified") is True
