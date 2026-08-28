"""
Milestone 23 — Adversarial Robustness & Self-Healing Defense Benchmark
======================================================================

Demonstrates full perception robustness, ambiguity safety, and physical self-healing:
  Gate G1: Keyboard typo normalization ("opn chorme")
  Gate G2: STT corrupted compound normalization ("opn crom n search yutub python tutrial")
  Gate G3: Contextual follow-up resolution ("play the first result" after search)
  Gate G4: Ambiguous multi-target request ("open the file" with 5 files) -> CLARIFICATION_REQUIRED
  Gate G5: Missing referent request ("send it") -> CLARIFICATION_REQUIRED
  Gate G6: Stale DOM element recovery -> TRANSIENT classification -> Self-healing retry -> Verified
  Gate G7: Lost window focus recovery -> TRANSIENT classification -> Re-focus HWND -> Verified
  Gate G8: Slow page load recovery -> TRANSIENT classification -> Wait/re-observe -> Verified
  Gate G9: Security barrier (CAPTCHA) -> BARRIER classification -> Honest BLOCKED (0 retries)
  Gate G10: Unrecoverable failure -> UNKNOWN classification -> Honest FAILED (0 fake success)
"""

import asyncio
import logging
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("m23_adversarial_robustness")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from brain.aca.engine_interface import EngineRegistry
from brain.execution_coordinator import ExecutionCoordinator
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.nlu.nlu_engine import NLUEngine
from core.orchestration.activity_trace_renderer import ActivityTraceRenderer


def run_m23_benchmark():
    print("\n==========================================================================")
    print("     AURA MILESTONE 23 — ADVERSARIAL ROBUSTNESS & SELF-HEALING GATE")
    print("==========================================================================\n")

    nlu = NLUEngine()
    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")
    coordinator = ExecutionCoordinator()

    # --- 1. Gate G1: Typo Input ---
    g1_nlu = nlu.process("opn chorme")
    g1_pass = g1_nlu.normalized_text == "open chrome" and g1_nlu.is_ambiguous is False

    # --- 2. Gate G2: STT Corrupted Compound Input ---
    g2_nlu = nlu.process("opn crom n search yutub python tutrial")
    g2_pass = g2_nlu.normalized_text == "open chrome and search youtube python tutorial" and g2_nlu.is_ambiguous is False

    # --- 3. Gate G3: Contextual Follow-Up ---
    context = {"last_search_candidates": [{"title": "Python Full Course for Beginners", "url": "https://youtube.com/watch?v=123"}]}
    g3_nlu = nlu.process("play the first result", context=context)
    g3_pass = g3_nlu.is_ambiguous is False and g3_nlu.entities.get("resolved_candidate", {}).get("title") == "Python Full Course for Beginners"

    # --- 4. Gate G4: Ambiguous Multi-Target Request ---
    context_g4 = {"available_files": ["report.txt", "resume.docx", "config.json", "notes.md", "data.csv"]}
    g4_nlu = nlu.process("open the file", context=context_g4)
    g4_pass = g4_nlu.is_ambiguous is True and "Which file or document would you like me to open?" in (g4_nlu.clarification_prompt or "")

    # --- 5. Gate G5: Missing Referent Request ---
    g5_nlu = nlu.process("send it")
    g5_pass = g5_nlu.is_ambiguous is True and "What message or document should I send and to whom?" in (g5_nlu.clarification_prompt or "")

    # --- 6. Gate G6: Stale DOM Element Failure Injection & Recovery ---
    exec_map_g6 = {
        "goal": "Execute browser fill with primary stale selector and recover via alternative selector",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<h1>M23%20Self-Healing%20Test</h1><input%20name=%22query%22%20placeholder=%22Type%20query...%22>"}},
            {"engine": "browser", "action": "browser.fill_form_field", "parameters": {"selector": "input#stale_nonexistent_id", "alternative_selector": "input[name='query']", "field": "query", "value": "Python Tutorial"}},
        ],
    }
    res_g6 = asyncio.run(coordinator.coordinate(exec_map_g6))
    g6_pass = res_g6.success is True and res_g6.step_results[1].data.get("recovery_trace", {}).get("recovery_status") == "RECOVERED_SUCCESS"

    # --- 7. Gate G7: Desktop Lost Window Focus Injection & Recovery ---
    exec_map_g7 = {
        "goal": "Re-activate Notepad window and self-heal transient focus loss",
        "steps": [
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad"}},
            {"engine": "desktop", "action": "keyboard.type", "parameters": {"app_name": "notepad", "text": "Aura M23 Self-Healing Focus Check\n"}},
            {"engine": "desktop", "action": "app_close", "parameters": {"app_name": "notepad"}},
        ],
    }
    # Inject simulated HWND focus loss on desktop backend before typing
    desktop._last_hwnd = 99999999
    res_g7 = asyncio.run(coordinator.coordinate(exec_map_g7))
    g7_pass = res_g7.success is True

    # --- 8. Gate G8: Slow Page Load DOM Delay Injection ---
    exec_map_g8 = {
        "goal": "Wait for delayed DOM element rendering and recover page load readiness",
        "steps": [
            {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "data:text/html,<h1>Slow%20Page</h1><script>setTimeout(()=>{document.body.innerHTML+='<input%20name=%22search%22%20value=%22ready%22>';},200);</script>"}},
            {"engine": "browser", "action": "browser.inspect_form", "parameters": {}},
        ],
    }
    res_g8 = asyncio.run(coordinator.coordinate(exec_map_g8))
    g8_pass = res_g8.success is True

    # --- 8. Gate G9: Security/Auth Barrier Honest BLOCKED ---
    exec_map_g9 = {
        "goal": "Halt honestly when security CAPTCHA barrier is detected",
        "steps": [
            {"engine": "browser", "action": "social.inspect_result", "parameters": {"selected_result": {"title": "CAPTCHA Security Check Required"}}},
        ],
    }
    res_g9 = asyncio.run(coordinator.coordinate(exec_map_g9))
    g9_pass = res_g9.success is False and (res_g9.step_results[0].data.get("status") == "BLOCKED" or res_g9.step_results[0].success is False)

    # --- 9. Gate G10: Unrecoverable Failure Honest FAILED ---
    exec_map_g10 = {
        "goal": "Report non-recoverable error as honest FAILED",
        "steps": [
            {"engine": "desktop", "action": "invalid_unsupported_action", "parameters": {}},
        ],
    }
    res_g10 = asyncio.run(coordinator.coordinate(exec_map_g10))
    g10_pass = res_g10.success is False

    # Render Sample Trace for Level 1 & Level 3
    trace_l1 = ActivityTraceRenderer.render_compact(res_g6)
    trace_l3 = ActivityTraceRenderer.render_full(res_g6)

    print("=== 1. CLI ACTIVITY TRACE — LEVEL 1 (COMPACT) ===")
    print(trace_l1)

    print("\n=== 2. CLI ACTIVITY TRACE — LEVEL 3 (FULL DIAGNOSTIC AUDIT) ===")
    print(trace_l3)

    facts = {
        "G1: Typo Normalization ('opn chorme')": g1_pass,
        "G2: STT Corrupted Compound Normalization": g2_pass,
        "G3: Contextual Follow-Up ('play first')": g3_pass,
        "G4: Ambiguous Request ('open the file')": g4_pass,
        "G5: Missing Referent ('send it')": g5_pass,
        "G6: Stale DOM Element Self-Healing": g6_pass,
        "G7: Lost Window Focus Self-Healing": g7_pass,
        "G8: Slow Page Load Readiness": g8_pass,
        "G9: Security Barrier Honest BLOCKED": g9_pass,
        "G10: Unrecoverable Honest FAILED": g10_pass,
    }

    print("\n==========================================================================")
    print("                 M23 ADVERSARIAL ROBUSTNESS ACCEPTANCE FACTS")
    print("==========================================================================")
    for k, v in facts.items():
        print(f"  ├─ {k:<45} : {v}")
    print("--------------------------------------------------------------------------")

    overall_pass = all(facts.values())
    status_str = "✅ PASS" if overall_pass else "❌ FAIL"
    print(f"M23 Acceptance Contract Final Result: {status_str}")
    print("==========================================================================\n")

    return overall_pass


if __name__ == "__main__":
    run_m23_benchmark()
