"""
Live Runtime Truth Pass Script
Location: scratch/live_truth_pass.py

Tests real end-to-end execution of NLU + Cognitive Memory through the canonical
MasterOrchestrator (AuraCore -> ACA Stage 0 NLU -> Stage 1 Memory -> Stage 2 DecisionEngine -> Backend).
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sys
sys.stdout.reconfigure(encoding="utf-8")

from src.core.orchestration.master_orchestrator import MasterOrchestrator
from Memory import Memory

def main():
    print("==========================================================================")
    print("         AURA AI — LIVE RUNTIME TRUTH PASS (NLU + M17 MEMORY)")
    print("==========================================================================")

    orchestrator = MasterOrchestrator.get_instance()
    mem = Memory()

    # Scenario 1: Typo & Shorthand Handling ("opn chorme")
    print("\n--- Scenario 1: Typo & Shorthand ('opn chorme') ---")
    res1 = orchestrator.process_request("opn chorme")
    print(f"Success    : {res1.success}")
    print(f"Planner    : {res1.planner}")
    print(f"NLU Result : {res1.data.get('metrics', {}).get('nlu_ms')} ms")
    print(f"Obs        : {res1.observations}")

    # Scenario 2: Conversational Phrasing ("can u open notpad")
    print("\n--- Scenario 2: Conversational Phrasing ('can u open notpad') ---")
    res2 = orchestrator.process_request("can u open notpad")
    print(f"Success    : {res2.success}")
    print(f"Planner    : {res2.planner}")
    print(f"Obs        : {res2.observations}")

    # Scenario 3: Ambiguous Request ("delete file" without target)
    print("\n--- Scenario 3: Ambiguous Request ('delete file') ---")
    res3 = orchestrator.process_request("delete file")
    print(f"Success    : {res3.success} (Expected False for clarification)")
    print(f"Planner    : {res3.planner}")
    print(f"Ambiguous  : {res3.data.get('is_ambiguous')}")
    print(f"Prompt     : {res3.observations}")

    # Scenario 4: Failed Execution Memory Guardrail (Verify NO persistent memory created for failure)
    mem_count_before = mem.cognitive.count_memories() if mem.cognitive else 0
    print(f"\n--- Scenario 4: Failed Execution Memory Guardrail ---")
    print(f"Memory count before failed run: {mem_count_before}")
    res4 = orchestrator.process_request("write a python script to sort numbers")
    mem_count_after_failed = mem.cognitive.count_memories() if mem.cognitive else 0
    print(f"Result success: {res4.success}")
    print(f"Memory count after failed run: {mem_count_after_failed}")

    # Scenario 5: Episodic Memory Recall ("what did we do today")
    print("\n--- Scenario 5: Episodic Memory Recall ('what did we do today') ---")
    res5 = orchestrator.process_request("what did we do today")
    print(f"Success    : {res5.success}")
    print(f"Planner    : {res5.planner}")
    print(f"Obs        : {res5.observations}")

    print("\n==========================================================================")
    print("                    LIVE RUNTIME TRUTH PASS COMPLETE")
    print("==========================================================================")

if __name__ == "__main__":
    main()
