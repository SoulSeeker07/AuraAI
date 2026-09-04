"""
Search Domain Disambiguation Benchmark
Location: scripts/eval_search_disambiguation.py

Tests whether bare search queries with multiple plausible domains
(local files vs memory vs web/research) are arbitrarily guessed or properly clarified.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from core.capabilities.capability_registry import CapabilityRegistry
from brain.intent_classifier import IntentClassifier


QUERIES = [
    "search for notes",
    "search for project discussions",
    "search for python tutorials",
    "search for my credentials",
    "search for recent updates",
]


async def main():
    reg = CapabilityRegistry.get_instance()
    clf = IntentClassifier(registry=reg)
    print("=" * 80)
    print("EVALUATING BARE 'SEARCH FOR <X>' QUERIES ACROSS DOMAINS")
    print("=" * 80)

    for q in QUERIES:
        print(f"\nQuery: '{q}'")
        picks = []
        for i in range(3):
            res = await clf.classify(q)
            out = res.outcome.value
            cap = res.intent.name if res.intent else (res.capability_name or "none")
            picks.append((out, cap, res.clarification_prompt))
            print(f"  Run {i+1}: outcome={out:<20} cap={cap:<24}")
            if out == "needs_clarification" and res.clarification_prompt:
                print(f"         prompt: \"{res.clarification_prompt[:70]}...\"")
            await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(main())
