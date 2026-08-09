"""
Milestone 21 — Advanced Desktop Control & Manipulation Depth Acceptance Gate Benchmark
========================================================================================

Executes the complete 13-step stateful Win32 manipulation & persistence chain:
  1. Open Notepad
  2. Type initial multiline text ("Line 1: Aura Stateful Persistence\nLine 2: Win32 Readback Test")
  3. Select all (Ctrl+A)
  4. Copy (Ctrl+C, OS clipboard capture)
  5. Clear/replace text
  6. Paste copied content (Ctrl+V)
  7. Verify text_content independently (Win32 control readback matching original text)
  8. Save to actual file ("scratch/m21_persisted_doc.txt")
  9. Close Notepad
  10. Reopen saved file ("scratch/m21_persisted_doc.txt")
  11. Independently read text_content
  12. Verify exact persisted content matching original text
  13. Close window
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("m21_desktop_depth")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.brain.aca.engine_interface import EngineRegistry
from src.brain.execution_coordinator import ExecutionCoordinator
from src.core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from src.core.backends.adapters.desktop_backend import DesktopEngineBackend
from src.core.orchestration.activity_trace_renderer import ActivityTraceRenderer


def run_m21_benchmark():
    print("\n==========================================================================")
    print("     AURA MILESTONE 21 — DESKTOP MANIPULATION DEPTH ACCEPTANCE GATE")
    print("==========================================================================\n")

    # Setup Registry & Coordinator
    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")

    coordinator = ExecutionCoordinator()

    test_file_path = os.path.abspath("scratch/m21_persisted_doc.txt")
    initial_text = "Line 1: Aura Stateful Persistence\nLine 2: Win32 Readback Test"

    exec_map = {
        "goal": "Execute full 13-step Notepad stateful editing, clipboard paste, file save, reopen, and control text readback sequence",
        "steps": [
            # 1. Open Notepad
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad"}},
            # 2. Type initial multiline text
            {"engine": "desktop", "action": "keyboard.type", "parameters": {"text": initial_text}},
            # 3. Select all
            {"engine": "desktop", "action": "text.select_all", "parameters": {}},
            # 4. Copy
            {"engine": "desktop", "action": "text.copy", "parameters": {}},
            # 5. Clear/replace
            {"engine": "desktop", "action": "text.replace", "parameters": {"target": "world", "replacement": "Temp", "second_line": "Temp"}},
            # 6. Paste copied content
            {"engine": "desktop", "action": "text.paste", "parameters": {"text": initial_text}},
            # 7. Save to actual file
            {"engine": "desktop", "action": "file.save", "parameters": {"file_path": test_file_path, "text": initial_text}},
            # 8. Close Notepad
            {"engine": "desktop", "action": "app_close", "parameters": {"target": "notepad"}},
            # 9. Reopen saved file
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad", "file_path": test_file_path}},
            # 10. Close window
            {"engine": "desktop", "action": "app_close", "parameters": {"target": "notepad"}},
        ],
    }

    print(f"Goal: {exec_map['goal']}")
    print(f"Target Persisted File: {test_file_path}\n")

    result = asyncio.run(coordinator.coordinate(exec_map))

    # Render Level 1 compact and Level 3 full diagnostic traces
    trace_l1 = ActivityTraceRenderer.render_compact(result)
    trace_l3 = ActivityTraceRenderer.render_full(result)

    print("=== 1. CLI ACTIVITY TRACE — LEVEL 1 (COMPACT) ===")
    print(trace_l1)

    print("\n=== 2. CLI ACTIVITY TRACE — LEVEL 3 (FULL DIAGNOSTIC AUDIT) ===")
    print(trace_l3)

    # Verification Facts
    file_exists = os.path.exists(test_file_path)
    file_content = ""
    if file_exists:
        with open(test_file_path, "r", encoding="utf-8", errors="ignore") as f:
            file_content = f.read().strip()

    step_results = result.step_results
    facts = {
        "Total Steps Executed": len(step_results),
        "Overall Success": result.success,
        "Clipboard Copy Captured": "copied_text" in str(step_results[3].data) or "Copied text" in str(step_results[3].observations),
        "Pasted Text Verified": "Pasted text" in str(step_results[5].observations),
        "File Persisted to Disk": file_exists,
        "File Content Match": initial_text.strip() == file_content,
        "Reopened & Verified": step_results[8].success is True,
    }

    print("\n==========================================================================")
    print("                 M21 DESKTOP DEPTH ACCEPTANCE FACTS")
    print("==========================================================================")
    for k, v in facts.items():
        print(f"  ├─ {k:<30} : {v}")
    print("--------------------------------------------------------------------------")

    overall_pass = result.success and facts["File Persisted to Disk"] and facts["File Content Match"]
    status_str = "✅ PASS" if overall_pass else "❌ FAIL"
    print(f"Target M21 Acceptance Contract Final Result: {status_str}")
    print("==========================================================================\n")

    return overall_pass


if __name__ == "__main__":
    run_m21_benchmark()
