import asyncio
import time
import os
import sys

sys.path.insert(0, os.path.abspath("src"))

from core.aura_core import AuraCore
from core.context.ambient_context_builder import AmbientContextBuilder
from core.progress_events import ProgressEmitter, CLIProgressRenderer

async def profile():
    print("=" * 70)
    print("PROFILING FULL REQUEST PIPELINE BREAKDOWN")
    print("=" * 70)

    aura = AuraCore()

    query = "set volume to 60 and summarize today's session"

    # Stage 1: Preamble
    t0 = time.time()
    _ = aura._focus_preamble(query)
    _ = aura._vision_dictation_preamble(query)
    t1 = time.time()
    print(f"1. Preambles: {(t1 - t0)*1000:.2f}ms")

    # Stage 2: Ambient Context Builder (Memory facts, window, hardware)
    t2 = time.time()
    ambient_info = AmbientContextBuilder.build_ambient_context(aura, query=query)
    t3 = time.time()
    print(f"2. AmbientContextBuilder: {(t3 - t2)*1000:.2f}ms")

    # Stage 3: Build Chat Messages
    t4 = time.time()
    messages = aura._build_chat_messages(query)
    t5 = time.time()
    print(f"3. Build Chat Messages: {(t5 - t4)*1000:.2f}ms")

    # Stage 4: Run process_request with emitter
    emitter = ProgressEmitter()
    renderer = CLIProgressRenderer(expanded=True)
    emitter.subscribe(renderer)

    t6 = time.time()
    resp = await aura.process_request(query, emitter=emitter)
    t7 = time.time()
    print(f"4. Full process_request: {(t7 - t6)*1000:.2f}ms ({t7 - t6:.2f}s)")
    renderer.finish()
    renderer.render_full_trace()

if __name__ == "__main__":
    asyncio.run(profile())
