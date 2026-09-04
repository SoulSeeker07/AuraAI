"""
Unseen Out-Of-Distribution (OOD) Multi-Target Ambiguity Benchmark
Location: scripts/eval_unseen_ambiguous_queries.py

Tests whether the model generalizes to completely novel, multi-target ambiguous phrasings
that NEVER appeared verbatim in the prompt-engineering loop or prior tests.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from core.capabilities.capability_registry import CapabilityRegistry
from brain.intent_classifier import IntentClassifier, ClassificationOutcome


# Fresh, completely out-of-distribution queries with multiple plausible capability targets
OOD_MULTI_TARGET_QUERIES = [
    ("clean it up", "disk cleanup vs code formatting vs temp files vs memory cache"),
    ("turn it off", "wifi vs bluetooth vs display vs audio mute vs system power"),
    ("update it", "system update vs git pull vs file save vs app upgrade"),
    ("refresh it", "browser page reload vs memory index refresh vs hud status"),
    ("save it", "text document save vs clipboard copy vs state checkpoint"),
]

NUM_RUNS = 3


async def run_ood_eval():
    print("=" * 90)
    print(f"OUT-OF-DISTRIBUTION (OOD) GENERALIZATION BENCHMARK: {NUM_RUNS} iterations on {len(OOD_MULTI_TARGET_QUERIES)} Novel Queries")
    print("Zero prompt leakage: none of these phrases appear in the system prompt.")
    print("=" * 90)

    registry = CapabilityRegistry.get_instance()
    classifier = IntentClassifier(registry=registry)

    history: dict[str, list[dict]] = {q: [] for q, _ in OOD_MULTI_TARGET_QUERIES}

    for run_idx in range(1, NUM_RUNS + 1):
        print(f"\n--- Iteration {run_idx}/{NUM_RUNS} ---")
        for query, target_desc in OOD_MULTI_TARGET_QUERIES:
            try:
                res = await classifier.classify(query)
                outcome = res.outcome.value
                cap_name = res.intent.name if res.intent else (res.capability_name or "none")
                clarification = res.clarification_prompt or ""

                history[query].append({
                    "run": run_idx,
                    "outcome": outcome,
                    "capability": cap_name,
                    "clarification": clarification,
                    "is_clarification": (outcome == "needs_clarification"),
                })
                print(f"  [{run_idx}] '{query:<14}' -> outcome={outcome:<20} cap={cap_name:<18}")
                if outcome == "needs_clarification" and clarification:
                    print(f"       Clarification prompt: \"{clarification[:75]}...\"")
            except Exception as e:
                history[query].append({
                    "run": run_idx,
                    "outcome": f"error:{e}",
                    "capability": "none",
                    "clarification": "",
                    "is_clarification": False,
                })
                print(f"  [{run_idx}] '{query:<14}' -> ERROR: {e}")
            await asyncio.sleep(1.0)

    print("\n" + "=" * 90)
    print("OOD GENERALIZATION SUMMARY ACROSS 3 RUNS (15 TOTAL SAMPLES)")
    print("=" * 90)
    print(f"{'QUERY':<18} | {'MULTIPLE TARGET AMBIGUITY':<45} | {'CLARIFICATION %':<16}")
    print("-" * 90)

    total_samples = 0
    total_clarifications = 0

    for query, target_desc in OOD_MULTI_TARGET_QUERIES:
        samples = history[query]
        clarifications = sum(1 for s in samples if s["is_clarification"])
        total = len(samples)
        pct = (clarifications / total) * 100
        total_samples += total
        total_clarifications += clarifications
        status = "PERFECT (100%)" if pct == 100.0 else f"VARIANCE ({pct:.0f}%)"
        print(f"{query:<18} | {target_desc[:43]:<45} | {pct:>5.1f}% ({clarifications}/{total}) {status}")

    overall_pct = (total_clarifications / total_samples) * 100
    print("-" * 90)
    print(f"OVERALL OOD GENERALIZATION RATE: {overall_pct:.1f}% ({total_clarifications}/{total_samples} samples triggered clarification)")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(run_ood_eval())
