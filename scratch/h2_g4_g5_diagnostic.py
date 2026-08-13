"""
H2 — G4 (Browser Lifecycle) & G5 (Voice/STT) focused diagnostic.
================================================================
Reproduces the exact per-cycle operations from scratch/test_phase6_endurance.py
INDEPENDENTLY (outside the 715-cycle loop) to surface the REAL exception/error
returned by each operation, and traces the failure into the existing components:

  G4 : runtime.execute_goal("navigate browser to data:text/html,<h1>Endurance</h1>", "text")
       + direct PlaywrightBrowserAdapter().execute("browser.navigate", ...)
  G5 : runtime.execute_goal("open browser and search google", "voice")
       + VoiceManager / TTS component probe

No production code is modified. G4/G5 acceptance is NOT weakened.
Output: artifacts/phase6/h2_g4_g5_diagnostic.{json,log}
"""
# ruff: noqa: E402  (scratch bootstrap)
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.abspath(str(ROOT / "src")))

from brain.aca.engine_interface import EngineRegistry  # noqa: E402
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter  # noqa: E402
from core.backends.adapters.desktop_backend import DesktopEngineBackend  # noqa: E402
from core.orchestration.execution_policy import ExecutionPolicy  # noqa: E402
from core.orchestration.personal_os_runtime import PersonalOSRuntime  # noqa: E402
from experts import DomainExpertRegistry  # noqa: E402
from experts.security_expert import CybersecurityAuditExpert  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "phase6"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def _setup_logging(log_path: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path, mode="w", encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )


def _exc() -> dict:
    return {
        "exc_type": sys.exc_info()[0].__name__ if sys.exc_info()[0] else None,
        "exc": str(sys.exc_info()[1]) if sys.exc_info()[1] else None,
        "traceback": traceback.format_exc(),
    }


def _report_dict(res) -> dict | None:
    if res is None:
        return None
    return {
        "goal": getattr(res, "goal", None),
        "input_type": getattr(res, "input_type", None),
        "success": getattr(res, "success", None),
        "status": getattr(res, "status", None),
        "verification_passed": getattr(res, "verification_passed", None),
        "steps_executed": getattr(res, "steps_executed", None),
        "domain_expert_used": getattr(res, "domain_expert_used", None),
        "intent_type": getattr(res, "intent_type", None),
        "evidence": getattr(res, "evidence", None),
        "activity_trace_l1": getattr(res, "activity_trace_l1", None),
        "activity_trace_l2": getattr(res, "activity_trace_l2", None),
        "spoken_summary": getattr(res, "spoken_summary", None),
    }


async def main() -> None:
    t0 = time.time()
    results = {"meta": {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "script": "h2_g4_g5_diagnostic"}}
    log = logging.getLogger("h2_g4_g5_diagnostic")

    # Reuse the exact H2 runtime wiring (no modifications)
    PersonalOSRuntime.reset_instance()
    DomainExpertRegistry.reset_instance()
    ExecutionPolicy.reset_instance()
    reg = EngineRegistry.get_instance()
    reg.register(DesktopEngineBackend(), name="desktop")
    reg.register(PlaywrightBrowserAdapter(), name="browser")
    DomainExpertRegistry.get_instance().register(CybersecurityAuditExpert())
    runtime = PersonalOSRuntime.get_instance()
    boot = runtime.boot()
    results["runtime_boot"] = boot.get("status")
    log.info("Runtime booted: %s", boot.get("status"))

    browser_adapter = PlaywrightBrowserAdapter()

    # ── G4: Browser Lifecycle probes ─────────────────────────────────────────
    log.info("=== G4 BROWSER LIFECYCLE PROBES ===")
    g4 = {"through_runtime": [], "direct_engine": []}
    g4_goal = "navigate browser to data:text/html,<h1>Endurance</h1>"
    for i in range(1, 7):
        entry = {"probe": i}
        try:
            res = await runtime.execute_goal(g4_goal, input_type="text")
            entry["report"] = _report_dict(res)
            log.info("G4-run#%s success=%s status=%s verify=%s",
                     i, getattr(res, "success", None), getattr(res, "status", None),
                     getattr(res, "verification_passed", None))
        except Exception:
            entry["error"] = _exc()
            log.info("G4-run#%s raised exception", i)
        g4["through_runtime"].append(entry)

    for i in range(1, 4):
        entry = {"probe": i}
        try:
            r = browser_adapter.execute(
                "browser.navigate",
                g4_goal,
                {"url": "data:text/html,<h1>Endurance</h1>"},
            )
            entry["engine_result"] = {
                "success": getattr(r, "success", None),
                "error": getattr(r, "error", None),
                "observations": getattr(r, "observations", None),
                "data": getattr(r, "data", None),
                "verification": getattr(r, "verification", None),
            }
            log.info("G4-direct#%s success=%s error=%s",
                     i, getattr(r, "success", None), str(getattr(r, "error", None))[:120])
        except Exception:
            entry["error"] = _exc()
            log.info("G4-direct#%s raised exception", i)
        g4["direct_engine"].append(entry)

    results["g4_browser"] = g4

    # ── G5: Voice/STT probes ────────────────────────────────────────────────
    log.info("=== G5 VOICE/STT PROBES ===")
    g5 = {"through_runtime": [], "voice_component": {}}
    g5_goal = "open browser and search google"
    for i in range(1, 7):
        entry = {"probe": i}
        try:
            res = await runtime.execute_goal(g5_goal, input_type="voice")
            entry["report"] = _report_dict(res)
            log.info("G5-run#%s success=%s input_type=%s status=%s",
                     i, getattr(res, "success", None), getattr(res, "input_type", None),
                     getattr(res, "status", None))
        except Exception:
            entry["error"] = _exc()
            log.info("G5-run#%s raised exception", i)
        g5["through_runtime"].append(entry)

    vm = getattr(getattr(runtime, "voice_loop", None), "voice_manager", None)
    g5["voice_component"]["voice_manager_present"] = vm is not None
    if vm is not None:
        tts = getattr(vm, "tts_manager", None)
        g5["voice_component"]["tts_manager_engine"] = (type(getattr(tts, "engine", None)).__name__
                                                       if getattr(tts, "engine", None) else None)
        try:
            speak_ok = vm.speak("Endurance cycle verification")
            g5["voice_component"]["vm_speak_return"] = speak_ok
            log.info("G5 vm.speak returned %s", speak_ok)
        except Exception:
            g5["voice_component"]["vm_speak_error"] = _exc()
            log.info("G5 vm.speak raised exception")
        if tts is not None:
            try:
                g5["voice_component"]["tts_initialize_return"] = tts.initialize()
            except Exception:
                g5["voice_component"]["tts_initialize_error"] = _exc()

    results["g5_voice"] = g5

    # ── Classification summary ───────────────────────────────────────────────
    g4_rt = results["g4_browser"]["through_runtime"]
    g5_rt = results["g5_voice"]["through_runtime"]
    results["classification"] = {
        "g4_browser_overall_pass": all(
            d.get("report") and d["report"]["success"] and d["report"]["verification_passed"] for d in g4_rt
        ),
        "g5_voice_overall_pass": all(
            d.get("report") and d["report"]["success"] and d["report"]["input_type"] == "voice" for d in g5_rt
        ),
        "g4_common_error": [d.get("engine_result", {}).get("error") for d in results["g4_browser"]["direct_engine"]],
        "tts_engine_initialized": results["g5_voice"]["voice_component"].get("tts_manager_engine") is not None,
        "vm_speak_return": results["g5_voice"]["voice_component"].get("vm_speak_return"),
    }

    results["meta"]["duration_s"] = round(time.time() - t0, 2)

    json_path = ARTIFACTS / "h2_g4_g5_diagnostic.json"
    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    log.info("Wrote %s", json_path)
    try:
        PersonalOSRuntime.reset_instance()
    except Exception as e:  # noqa: BLE001
        log.info("Reset note: %s", e)
    print("DIAGNOSTIC_DONE json=%s" % json_path)


if __name__ == "__main__":
    _setup_logging(ARTIFACTS / "h2_g4_g5_diagnostic.log")
    asyncio.run(main())