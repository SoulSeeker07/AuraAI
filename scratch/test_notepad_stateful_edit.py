"""
Real Interactive Stateful Desktop Benchmark:
"Open Notepad, type hello world, then change world to Aura, add a second line saying M18 is working, and close Notepad."
Location: scratch/test_notepad_stateful_edit.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from brain.execution_coordinator import ExecutionCoordinator
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from brain.aca.engine_interface import EngineRegistry


async def run_stateful_desktop_benchmark():
    print("==========================================================================")
    print("  REAL WINDOWS DESKTOP INTERACTIVE BENCHMARK: STATEFUL TEXT EDITING")
    print("==========================================================================")

    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    registry.register(desktop, "desktop")

    coordinator = ExecutionCoordinator()

    exec_map = {
        "goal": "Open Notepad, type hello world, edit world to Aura, add second line, and close",
        "steps": [
            {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad"}},
            {"engine": "desktop", "action": "keyboard.type", "parameters": {"text": "hello world"}},
            {"engine": "desktop", "action": "text.replace", "parameters": {"target": "world", "replacement": "Aura", "second_line": "M18 is working", "selector": "hello Aura"}},
            {"engine": "desktop", "action": "app_close", "parameters": {"target": "notepad"}},
        ],
    }

    res = await coordinator.coordinate(exec_map)

    print(f"\nOverall Result Success: {res.success}")
    print(f"Total Steps Executed: {len(res.step_results)}")

    for i, step in enumerate(res.step_results, 1):
        print(f"\nStep {i} [{step.engine}] {step.action}:")
        print(f"  Success     : {step.success}")
        print(f"  Observations: {step.observations}")
        obs = step.data.get("observation")
        if obs:
            print(f"  State       : {obs.get('state')}")
            print(f"  Evidence    : {obs.get('evidence')}")
        v_rep = step.data.get("verification_report")
        if v_rep:
            print(f"  Verification: Passed={v_rep.get('passed')}, Evidence={v_rep.get('evidence')}")

    print("\n==========================================================================")
    print("                STATEFUL DESKTOP BENCHMARK COMPLETE")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_stateful_desktop_benchmark())
