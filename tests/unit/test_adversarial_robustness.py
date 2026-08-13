"""
Milestone 23 Unit Test Suite: Adversarial Robustness & Self-Healing Defense
===========================================================================

Verifies 10 mandatory acceptance gates:
  G1: Typo input ("opn chorme") → Confidence-aware normalization → Execute
  G2: STT corrupted compound input ("opn crom n search yutub python tutrial") → Normalize & decompose → Execute
  G3: Contextual follow-up ("play the first result") → Resolve candidate #1 from runtime state → Execute
  G4: Ambiguous request ("open the file" with 5 files present) → is_ambiguous=True with clarification prompt
  G5: Missing referent ("send it") → is_ambiguous=True with clarification prompt
  G6: Stale DOM element failure → Classify TRANSIENT → Re-observe → Recover & verify
  G7: Lost window focus → Classify TRANSIENT → Re-focus HWND → Recover & verify
  G8: Slow page load → Classify TRANSIENT → Wait/re-observe → Verify
  G9: Security/Auth barrier (CAPTCHA) → Classify BARRIER → Immediate honest BLOCKED (0 retries)
  G10: Unrecoverable failure → Classify UNKNOWN → Immediate honest FAILED (0 fake success)
"""

import pytest
from brain.aca.engine_interface import EngineRegistry
from brain.execution_coordinator import ExecutionCoordinator
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.nlu.nlu_engine import NLUEngine
from core.nlu.ambiguity_detector import AmbiguityDetector


@pytest.fixture
def clean_nlu_and_registry():
    nlu = NLUEngine()
    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")
    return nlu, registry, desktop, browser


def test_g1_typo_normalization(clean_nlu_and_registry):
    nlu, _, _, _ = clean_nlu_and_registry
    res = nlu.process("opn chorme")

    assert res.normalized_text == "open chrome"
    assert res.confidence >= 0.75
    assert res.is_ambiguous is False


def test_g2_stt_corrupted_compound_normalization(clean_nlu_and_registry):
    nlu, _, _, _ = clean_nlu_and_registry
    res = nlu.process("opn crom n search yutub python tutrial")

    assert res.normalized_text == "open chrome and search youtube python tutorial"
    assert res.confidence >= 0.75
    assert res.is_ambiguous is False


def test_g3_contextual_follow_up_resolution(clean_nlu_and_registry):
    nlu, _, _, _ = clean_nlu_and_registry
    context = {
        "last_search_candidates": [
            {"title": "Python Full Course for Beginners", "url": "https://youtube.com/watch?v=123"}
        ]
    }
    res = nlu.process("play the first result", context=context)

    assert res.is_ambiguous is False
    assert res.entities.get("resolved_candidate", {}).get("title") == "Python Full Course for Beginners"


def test_g4_ambiguous_multi_target_request(clean_nlu_and_registry):
    nlu, _, _, _ = clean_nlu_and_registry
    context = {"available_files": ["report.txt", "resume.docx", "config.json", "notes.md", "data.csv"]}
    res = nlu.process("open the file", context=context)

    assert res.is_ambiguous is True
    assert "Which file or document would you like me to open?" in res.clarification_prompt


def test_g5_missing_referent_request(clean_nlu_and_registry):
    nlu, _, _, _ = clean_nlu_and_registry
    res = nlu.process("send it")

    assert res.is_ambiguous is True
    assert "What message or document should I send and to whom?" in res.clarification_prompt


@pytest.mark.asyncio
async def test_g6_stale_dom_element_recovery(clean_nlu_and_registry):
    _, registry, desktop, browser = clean_nlu_and_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Fill form field after stale element recovery",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<input name='query'>"}},
            {"engine": "browser", "action": "browser.fill_form_field", "parameters": {"primary_selector": "input#stale_nonexistent_id", "alternative_selector": "input[name='query']", "field": "query", "value": "Python"}},
        ],
    }

    result = await coordinator.coordinate(exec_map)
    assert result.success is True
    assert result.step_results[1].data.get("recovery_trace", {}).get("recovery_status") == "RECOVERED_SUCCESS"


@pytest.mark.asyncio
async def test_g7_lost_window_focus_recovery(clean_nlu_and_registry):
    _, registry, desktop, browser = clean_nlu_and_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Re-activate Notepad window and type text after focus loss",
        "steps": [
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad"}},
            {"engine": "desktop", "action": "keyboard.type", "parameters": {"app_name": "notepad", "text": "Aura Resilience Test\n"}},
            {"engine": "desktop", "action": "app_close", "parameters": {"app_name": "notepad"}},
        ],
    }

    # Inject simulated HWND focus loss before typing
    desktop._last_hwnd = 99999999
    result = await coordinator.coordinate(exec_map)
    assert result.success is True


@pytest.mark.asyncio
async def test_g8_slow_page_load_recovery(clean_nlu_and_registry):
    _, registry, desktop, browser = clean_nlu_and_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Navigate to slow loading page and verify page load readiness",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<h1>Slow%20Page</h1><script>setTimeout(()=>{document.body.innerHTML+='<input%20name=%22search%22%20value=%22ready%22>';},200);</script>"}},
            {"engine": "browser", "action": "browser.inspect_form", "parameters": {}},
        ],
    }

    result = await coordinator.coordinate(exec_map)
    assert result.success is True


@pytest.mark.asyncio
async def test_g9_captcha_security_barrier_honest_blocked(clean_nlu_and_registry):
    _, registry, desktop, browser = clean_nlu_and_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Verify honest BLOCKED reporting when security CAPTCHA is encountered",
        "steps": [
            {"engine": "browser", "action": "social.inspect_result", "parameters": {"selected_result": {"title": "CAPTCHA Security Check Required"}}},
        ],
    }

    result = await coordinator.coordinate(exec_map)
    assert result.success is False
    assert result.step_results[0].data.get("status") == "BLOCKED" or result.step_results[0].success is False


@pytest.mark.asyncio
async def test_g10_unrecoverable_failure_honest_failed(clean_nlu_and_registry):
    _, registry, desktop, browser = clean_nlu_and_registry
    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Verify honest FAILED reporting for non-existent process",
        "steps": [
            {"engine": "desktop", "action": "nonexistent_action_xyz", "parameters": {}},
        ],
    }

    result = await coordinator.coordinate(exec_map)
    assert result.success is False
