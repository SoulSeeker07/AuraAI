import asyncio
import time
import os
import sys

sys.path.insert(0, os.path.abspath("src"))

from core.aura_core import AuraCore
from core.progress_events import ProgressEmitter, CLIProgressRenderer

async def run_test():
    print("=" * 70)
    print("TESTING STARTUP EMBEDDING WARMUP + REQUEST LATENCY")
    print("=" * 70)

    # 1. Start AuraCore (triggers background embedding warmup)
    t_init_start = time.time()
    aura = AuraCore()
    print(f"AuraCore initialized in {(time.time() - t_init_start)*1000:.1f}ms (Warmup is running in background)")

    # 2. Wait for warmup to complete (simulating typical user think time before first prompt)
    print("Waiting for background warmup to finish...")
    t_w_start = time.time()
    await aura.embedding_warmup.ensure_ready()
    print(f"Background embedding warmup is 100% READY! (waited {(time.time() - t_w_start):.2f}s)")

    # 3. Now run the exact two-step query
    emitter = ProgressEmitter()
    renderer = CLIProgressRenderer(expanded=True)
    emitter.subscribe(renderer)

    query = "set volume to 60 and summarize today's session"
    print(f"\n[Executing User Query] '{query}'\n")

    t_req_start = time.time()
    response = await aura.process_request(query, emitter=emitter)
    t_req_end = time.time()

    renderer.finish()
    renderer.render_full_trace()

    print(f"\nRequest Wall-Clock Latency: {(t_req_end - t_req_start):.2f}s")
    print("\nFinal Response Preview:\n", response[:150], "...")

if __name__ == "__main__":
    asyncio.run(run_test())
