"""
Milestone 16 — Cognitive Orchestration Layer Demo

Demonstrates the full 7-stage cognitive pipeline with OS Session & Budget management:
1. Memory Recall (Context pre-fetch)
2. Executive Decision & Reasoning (DecisionEngine + Risk + ExecutionBudget)
3. Task Graph Decomposition (TaskDecomposer)
4. Supervisor Delegation (SupervisorAgent -> PlannerRegistry)
5. Backend Selection & Parallel Execution (BackendRegistry -> Antigravity CLI, Gemini, Native Desktop)
6. Result Fusion & Observation Merging (ResultMerger)
7. Unified Memory Write (Persist outcomes)
"""

import sys
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.backends.backend_registry import BackendRegistry
from core.orchestration.agent_session import ExecutionBudget
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.planner_registry import PlannerRegistry


def main():
    print("=" * 80)
    print("     AURA AI OPERATING SYSTEM - COGNITIVE ORCHESTRATION LAYER DEMO")
    print("=" * 80)

    user_goal = (
        "Research Python 3.14 changes, summarize them, open my VS Code project, "
        "create a markdown report, and ask Antigravity to update the affected files."
    )

    budget = ExecutionBudget(
        max_time_seconds=30.0,
        max_cost_usd=0.05,
        max_backends=4,
        allow_parallel=True,
        local_only=False,
    )

    print(f"\n[USER GOAL]: '{user_goal}'")
    print(
        f"[EXECUTION BUDGET]: MaxTime={budget.max_time_seconds}s, MaxCost=${budget.max_cost_usd}, AllowParallel={budget.allow_parallel}\n"
    )

    MasterOrchestrator.reset_instance()
    PlannerRegistry.reset_instance()
    BackendRegistry.reset_instance()

    orchestrator = MasterOrchestrator.get_instance()
    result = orchestrator.process_request(user_goal, budget=budget)

    print("-" * 80)
    print(f"EXECUTION STATUS: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"CONFIDENCE SCORE: {result.confidence:.2f}")
    print(f"TOTAL EXECUTION TIME: {result.execution_time_seconds * 1000:.2f} ms")
    print(f"AGENT SESSION ID: {result.data.get('session_id', 'N/A')}")
    print("-" * 80)

    print("\n--- STAGE 2: EXECUTIVE DECISION ENGINE SUMMARY ---")
    budget_dict = result.data.get("budget", {})
    print(f"  Enforced Budget: {budget_dict}")

    print("\n--- STAGE 5 & 6: STRUCTURED OBSERVATIONS ---")
    for obs in result.observations:
        print(f"  + {obs}")

    if result.artifacts:
        print("\n--- UNIFIED ARTIFACT STORE ---")
        for artifact in result.artifacts:
            print(
                f"  [ARTIFACT] {artifact.get('artifact_id')} ({artifact.get('artifact_type')}): {artifact.get('location')} [Creator: {artifact.get('creator')}]"
            )

    metrics = result.data.get("metrics", {})
    print("\n--- STAGE 7: AGENT SESSION METRICS ---")
    print(
        f"Subtasks Completed: {metrics.get('subtasks_completed', 0)}/{metrics.get('subtasks_total', 0)}"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
