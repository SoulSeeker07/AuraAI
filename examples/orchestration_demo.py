"""
Milestone 16 — End-to-End Multi-Agent Orchestration Demo

Demonstrates the 6-phase pipeline:
1. Intent & Task Decomposition (Task Graph)
2. Role Planner Selection (Research + Desktop + Coding)
3. Dynamic Backend Selection (Gemini/Groq + Native Engine + Antigravity CLI)
4. Concurrent Task Execution
5. Result Fusion & Response Synthesis
6. Unified Memory Update
"""

import json
import sys
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.execution.orchestration_engine import MasterOrchestrator


def main():
    print("=" * 80)
    print("      AURA AI OPERATING SYSTEM — MILESTONE 16 ORCHESTRATION DEMO")
    print("=" * 80)

    user_goal = (
        "Research Python 3.14 changes, summarize them, open my VS Code project, "
        "create a markdown report, and ask Antigravity to update the affected files."
    )

    print(f"\n[USER GOAL]: '{user_goal}'\n")

    orchestrator = MasterOrchestrator()
    result = orchestrator.execute_goal(user_goal)

    print("-" * 80)
    print(f"EXECUTION STATUS: {result.status.upper()}")
    print(f"TOTAL EXECUTION TIME: {result.execution_time_ms:.2f} ms")
    print("-" * 80)

    print("\n--- PHASE 1-4: UNIFIED EXECUTION TRACE ---")
    for step in result.execution_trace:
        print(f"  * [{step['task_id']}] {step['title']}")
        print(f"    - Role Planner : {step['role']}")
        print(f"    - Selected Backend : {step['backend']}")
        print(f"    - Result Status: {step['status']}")

    print("\n--- PHASE 5: RESULT FUSION ---")
    print("Observations:")
    for obs in result.observations:
        print(f"  + {obs}")

    if result.modified_files:
        print("\nModified Files:")
        for f in result.modified_files:
            print(f"  [FILE] {f}")

    if result.citations:
        print("\nCitations:")
        for c in result.citations:
            print(f"  [CITE] {c}")

    print("\n--- SUMMARY ---")
    print(result.execution_summary)
    print("=" * 80)


if __name__ == "__main__":
    main()

