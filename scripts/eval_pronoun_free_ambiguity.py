"""
Pronoun-Free Multi-Target Ambiguity Benchmark
Location: scripts/eval_pronoun_free_ambiguity.py

Evaluates multi-target ambiguity queries that contain ZERO pronouns (no 'it', 'that', 'this', 'them')
to verify whether the model catches ambiguity based on multiple plausible capabilities alone.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from core.capabilities.capability_registry import CapabilityRegistry
from brain.intent_classifier import IntentClassifier, ClassificationOutcome


PRONOUN_FREE_QUERIES = [
    ("search for notes", "memory.search vs research.search vs desktop file search"),
    ("analyze the contents", "code.analyze vs research.synthesize vs vision.describe"),
    ("compress the files", "zip archiving vs desktop file tools vs workspace packaging"),
    ("back up the project", "git commit/push vs workspace archive vs memory store"),
    ("monitor the system", "daemon.status vs daemon.list vs system performance"),
]

NUM_RUNS = 3


async def run_pronoun_free_eval():
    print("=" * 90)
    print(f"PRONOUN-FREE MULTI-TARGET AMBIGUITY BENCHMARK: {NUM_RUNS} iterations on {len(PRONOUN_FREE_QUERIES)} Queries")
    print("Zero pronouns: none of these queries contain 'it', 'that', 'this', or 'them'.")
    print("=" * 90)

    registry = CapabilityRegistry.get_instance()
    classifier = IntentClassifier(registry=registry)

    history: dict[str, list[dict]] = {q: [] for q, _ in PRONOUN_FREE_QUERIES}

    for run_idx in range(1, NUM_RUNS + 1):
        print(f"\n--- Iteration {run_idx}/{NUM_RUNS} ---")
        for query, target_desc in PRONOUN_FREE_QUERIES:
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
                print(f"  [{run_idx}] '{query:<22}' -> outcome={outcome:<20} cap={cap_name:<18}")
                if outcome == "needs_clarification" and clarification:
                    print(f"       Clarification: \"{clarification[:75]}...\"")
            except Exception as e:
                history[query].append({
                    "run": run_idx,
                    "outcome": f"error:{e}",
                    "capability": "none",
                    "clarification": "",
                    "is_clarification": False,
                })
                print(f"  [{run_idx}] '{query:<22}' -> ERROR: {e}")
            await asyncio.sleep(1.0)

    print("\n" + "=" * 90)
    print("PRONOUN-FREE AMBIGUITY SUMMARY ACROSS 3 RUNS (15 TOTAL SAMPLES)")
    print("=" * 90)
    print(f"{'QUERY':<24} | {'MULTIPLE TARGET AMBIGUITY':<42} | {'CLARIFICATION %':<16}")
    print("-" * 90)

    total_samples = 0
    total_clarifications = 0

    for query, target_desc in PRONOUN_FREE_QUERIES:
        samples = history[query]
        clarifications = sum(1 for s in samples if s["is_clarification"])
        total = len(samples)
        pct = (clarifications / total) * 100
        total_samples += total
        total_clarifications += clarifications
        status = "PERFECT (100%)" if pct == 100.0 else f"VARIANCE ({pct:.0f}%)"
        print(f"{query:<24} | {target_desc[:40]:<42} | {pct:>5.1f}% ({clarifications}/{total}) {status}")

    overall_pct = (total_clarifications / total_samples) * 100
    print("-" * 90)
    print(f"OVERALL PRONOUN-FREE CLARIFICATION RATE: {overall_pct:.1f}% ({total_clarifications}/{total_samples} samples triggered clarification)")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(run_pronoun_free_eval())
