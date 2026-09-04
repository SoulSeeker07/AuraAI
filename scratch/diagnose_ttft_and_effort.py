import asyncio
import time
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
sys.path.insert(0, os.path.abspath("src"))

from core.aura_core import AuraCore
from core.progress_events import ProgressEmitter, CLIProgressRenderer

async def run_diagnostics():
    print("=" * 70)
    print("DIAGNOSING TTFT & ACTUAL REASONING_EFFORT SENT TO GROQ")
    print("=" * 70)

    aura = AuraCore()

    emitter = ProgressEmitter()
    renderer = CLIProgressRenderer(expanded=False)
    emitter.subscribe(renderer)

    query = "set volume to 60 and summarize today's session"
    print(f"\n[Test Query] '{query}'\n")

    start_total = time.time()
    response = await aura.process_request(query, emitter=emitter)
    dur_total = time.time() - start_total

    renderer.finish()
    renderer.render_full_trace()

    print(f"\nTotal Wall-Clock: {dur_total:.2f}s")
    print(f"Final Answer Preview: {response[:150]}...")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
