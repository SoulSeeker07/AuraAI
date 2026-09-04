"""
Ambiguous Intent Routing & Confidence Evaluation Harness
Location: scripts/eval_ambiguous_intent_routing.py

Empirical benchmark testing how IntentClassifier handles:
1. Clear capability requests (e.g. 'run git status', 'open notepad')
2. Genuinely ambiguous / underspecified requests (e.g. 'do the thing', 'check it')
3. General chat / QA queries (e.g. 'who founded linux', 'tell me a joke')
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from core.capabilities.capability_registry import CapabilityRegistry
from brain.intent_classifier import IntentClassifier, ClassificationOutcome


TEST_CORPUS = [
    # 1. Clear-cut capability queries
    ("run git status", "system.shell", "Clear Capability"),
    ("open notepad", "desktop.window.open", "Clear Capability"),
    ("implement a binary search function in python", "coding.generate_code", "Clear Capability"),
    
    # 2. Genuinely ambiguous queries (should trigger system.clarification or clarification prompt)
    ("can you check that thing?", "needs_clarification", "Ambiguous"),
    ("run it now", "needs_clarification", "Ambiguous"),
    ("do what we talked about yesterday", "needs_clarification", "Ambiguous"),
    ("start the process", "needs_clarification", "Ambiguous"),
    ("open it up", "needs_clarification", "Ambiguous"),

    # 3. General conversation queries (should resolve to provider_chat)
    ("what is the capital of Japan?", "provider_chat", "General Chat"),
    ("tell me a programming joke", "provider_chat", "General Chat"),
    ("how do black holes work?", "provider_chat", "General Chat"),
]


async def run_eval():
    print("=" * 80)
    print("EMPIRICAL EVALUATION: IntentClassifier on Clear vs Ambiguous vs Chat Queries")
    print("=" * 80)

    registry = CapabilityRegistry.get_instance()
    classifier = IntentClassifier(registry=registry)

    results = []

    for query, expected_category, query_type in TEST_CORPUS:
        try:
            res = await classifier.classify(query)
            
            if res.outcome == ClassificationOutcome.RESOLVED:
                actual = res.intent.name if res.intent else "none"
            elif res.outcome == ClassificationOutcome.NEEDS_CLARIFICATION:
                actual = "needs_clarification"
            else:
                actual = "failed_closed"

            matched = (actual == expected_category) or (
                query_type == "Clear Capability" and res.outcome == ClassificationOutcome.RESOLVED
            )

            status = "PASS" if matched else "REVIEW"
            results.append((query, query_type, expected_category, actual, res.confidence, res.outcome.value, status, res.clarification_prompt))

            print(f"\nQuery: '{query}' [{query_type}]")
            print(f"  Outcome:      {res.outcome.value}")
            print(f"  Capability:   {actual}")
            print(f"  Confidence:   {res.confidence}")
            if res.clarification_prompt:
                print(f"  Clarification: {res.clarification_prompt}")
            print(f"  Eval Result:  {status}")

        except Exception as e:
            print(f"\nQuery: '{query}' -> ERROR: {e}")
            results.append((query, query_type, expected_category, f"error:{e}", 0.0, "error", "FAIL", None))

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'QUERY':<40} | {'TYPE':<16} | {'ACTUAL':<20} | {'STATUS'}")
    print("-" * 80)
    for q, qtype, expected, actual, conf, outcome, status, _ in results:
        print(f"{q[:38]:<40} | {qtype:<16} | {actual[:18]:<20} | {status}")


if __name__ == "__main__":
    asyncio.run(run_eval())
