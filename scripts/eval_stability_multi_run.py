"""
Multi-Target & Zero-Target Ambiguous Stability Evaluation Harness
Location: scripts/eval_stability_multi_run.py

Runs 5 independent iterations across both categories of ambiguous inputs:
1. Zero-target vague requests ("open it up", "run it now")
2. Multi-target ambiguous requests ("check the logs", "clear the cache", "show status", "restart it")
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from core.capabilities.capability_registry import CapabilityRegistry
from brain.intent_classifier import IntentClassifier, ClassificationOutcome


TEST_QUERIES = [
    # Category A: Zero-target vague requests
    ("run it now", "Zero-Target"),
    ("open it up", "Zero-Target"),
    ("can you check that thing?", "Zero-Target"),
    
    # Category B: Multi-target ambiguous requests (multiple valid capabilities exist)
    ("check the logs", "Multi-Target"),       # git log vs app log vs daemon log
    ("clear the cache", "Multi-Target"),      # pytest cache vs vector cache vs browser cache
    ("show the status", "Multi-Target"),      # git status vs battery status vs hud status
    ("restart it", "Multi-Target"),           # restart app vs restart machine vs restart agent
]

NUM_RUNS = 3


async def run_stability_eval():
    print("=" * 85)
    print(f"MULTI-RUN STABILITY BENCHMARK: {NUM_RUNS} iterations on {len(TEST_QUERIES)} Ambiguous Queries")
    print("=" * 85)

    registry = CapabilityRegistry.get_instance()
    classifier = IntentClassifier(registry=registry)

    # query -> list of samples
    history: dict[str, list[dict]] = {q: [] for q, _ in TEST_QUERIES}

    for run_idx in range(1, NUM_RUNS + 1):
        print(f"\n--- Iteration {run_idx}/{NUM_RUNS} ---")
        for query, category in TEST_QUERIES:
            try:
                res = await classifier.classify(query)
                outcome = res.outcome.value
                cap_name = res.intent.name if res.intent else (res.capability_name or "none")
                clarification = res.clarification_prompt or ""

                history[query].append({
                    "run": run_idx,
                    "category": category,
                    "outcome": outcome,
                    "capability": cap_name,
                    "clarification": clarification,
                    "is_clarification": (outcome == "needs_clarification"),
                })
                print(f"  [{run_idx}] [{category:<12}] '{query[:25]:<25}' -> outcome={outcome:<18} cap={cap_name:<16}")
            except Exception as e:
                history[query].append({
                    "run": run_idx,
                    "category": category,
                    "outcome": f"error:{e}",
                    "capability": "none",
                    "clarification": "",
                    "is_clarification": False,
                })
                print(f"  [{run_idx}] [{category:<12}] '{query[:25]:<25}' -> ERROR: {e}")
            await asyncio.sleep(1.0)

    print("\n" + "=" * 85)
    print("STABILITY SUMMARY ACROSS 5 RUNS (35 TOTAL SAMPLES)")
    print("=" * 85)
    print(f"{'QUERY':<28} | {'CATEGORY':<14} | {'CLARIFICATION %':<16} | {'STATUS'}")
    print("-" * 85)

    cat_totals: dict[str, list[int]] = {"Zero-Target": [0, 0], "Multi-Target": [0, 0]}

    for query, category in TEST_QUERIES:
        samples = history[query]
        clarifications = sum(1 for s in samples if s["is_clarification"])
        total = len(samples)
        pct = (clarifications / total) * 100
        cat_totals[category][0] += clarifications
        cat_totals[category][1] += total
        status = "PERFECT (100%)" if pct == 100.0 else f"VARIANCE ({pct:.0f}%)"
        print(f"{query[:26]:<28} | {category:<14} | {pct:>5.1f}% ({clarifications}/{total})     | {status}")

    print("-" * 85)
    for cat, (c_count, t_count) in cat_totals.items():
        cat_pct = (c_count / t_count) * 100 if t_count else 0
        print(f"  {cat:<14} Subtotal: {cat_pct:.1f}% ({c_count}/{t_count} samples triggered clarification)")
    print("=" * 85)


if __name__ == "__main__":
    asyncio.run(run_stability_eval())
