import asyncio
import time
import os
import sys

sys.path.insert(0, os.path.abspath("src"))

from core.aura_core import AuraCore
from core.progress_events import ProgressEmitter, CLIProgressRenderer

async def test_race_and_profile_init():
    print("=" * 70)
    print("1. PROFILING AuraCore.__init__ CONSTRUCTOR BREAKDOWN")
    print("=" * 70)

    # Let's inspect component timings during construction
    t_start = time.time()
    aura = AuraCore()
    t_end = time.time()
    print(f"\nTotal AuraCore Constructor Time: {(t_end - t_start)*1000:.1f}ms")

    print("\n" + "=" * 70)
    print("2. IMMEDIATE QUERY TEST (0ms think time, Warmup In-Flight)")
    print("=" * 70)
    print(f"Warmup status immediately after constructor: is_ready={aura.embedding_warmup.is_ready}")

    emitter = ProgressEmitter()
    renderer = CLIProgressRenderer(expanded=True)
    emitter.subscribe(renderer)

    query = "set volume to 60 and summarize today's session"
    print(f"\n[Firing Request Immediately] '{query}'\n")

    t_req_start = time.time()
    response = await aura.process_request(query, emitter=emitter)
    t_req_end = time.time()

    renderer.finish()
    renderer.render_full_trace()

    print(f"\nTotal Request Wall-Clock Time: {(t_req_end - t_req_start):.2f}s")
    print(f"Warmup status after request: is_ready={aura.embedding_warmup.is_ready}")
    print("\nFinal Answer Preview:\n", response[:150], "...")

if __name__ == "__main__":
    asyncio.run(test_race_and_profile_init())
