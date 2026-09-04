"""
scratch/benchmark_twostep_latency.py

Runs the exact multi-step query "set volume to 60 and summarize today's session"
multiple times, breaking down latency per turn:
- Turn TTFT (Time to first reasoning token)
- Reasoning duration & token count
- Tool generation duration & argument size
- Final response generation duration
"""

import asyncio
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(1, str(PROJECT_ROOT))

from core.aura_core import AuraCore
from core.progress_events import ProgressEmitter, CLIProgressRenderer


async def run_comparison(runs: int = 3):
    print("=" * 70, flush=True)
    print(f"RUNNING EXACT TWO-STEP QUERY BENCHMARK ({runs} Iterations)", flush=True)
    print("Query: 'set volume to 60 and summarize today\\'s session'", flush=True)
    print("=" * 70, flush=True)

    aura_core = AuraCore()
    query = "set volume to 60 and summarize today's session"

    durations = []

    for i in range(1, runs + 1):
        print(f"\n--- [RUN {i}/{runs}] ---", flush=True)
        emitter = ProgressEmitter()
        renderer = CLIProgressRenderer(expanded=True)
        emitter.subscribe(renderer)

        t0 = time.time()
        response = await aura_core.process_request(query, emitter=emitter)
        total_time = time.time() - t0
        durations.append(total_time)

        renderer.finish()
        renderer.render_full_trace()
        print(f"Run {i} Total Wall-Clock Time: {total_time:.2f}s", flush=True)
        print(f"Final Answer Preview: {response[:100]}...", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("BENCHMARK SUMMARY", flush=True)
    print("=" * 70, flush=True)
    for idx, d in enumerate(durations, 1):
        print(f"  Run {idx}: {d:.2f}s", flush=True)
    print(f"  Average: {sum(durations)/len(durations):.2f}s | Median: {sorted(durations)[len(durations)//2]:.2f}s", flush=True)
    print("=" * 70, flush=True)

    aura_core.shutdown()


if __name__ == "__main__":
    asyncio.run(run_comparison(runs=3))
