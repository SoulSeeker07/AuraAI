import asyncio
import time
import os
import sys
import subprocess

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

print("=" * 70)
print("MULTI-RUN E2E IMMEDIATE-QUERY BENCHMARK (4 Independent Runs)")
print("=" * 70)

code = """
import asyncio, os, sys, time
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath("src"))
from core.aura_core import AuraCore
from core.progress_events import ProgressEmitter, CLIProgressRenderer

async def run_single():
    t_boot_start = time.time()
    aura = AuraCore()
    t_boot_end = time.time()
    boot_ms = (t_boot_end - t_boot_start) * 1000

    emitter = ProgressEmitter()
    renderer = CLIProgressRenderer(expanded=True)
    emitter.subscribe(renderer)

    query = "set volume to 60 and summarize today's session"
    t_req_start = time.time()
    resp = await aura.process_request(query, emitter=emitter)
    t_req_end = time.time()
    req_ms = (t_req_end - t_req_start) * 1000
    total_ms = (t_req_end - t_boot_start) * 1000

    renderer.finish()
    print("--- TRACE START ---")
    renderer.render_full_trace()
    print("--- TRACE END ---")
    print(f"METRIC:BOOT_MS:{boot_ms:.1f}")
    print(f"METRIC:REQ_MS:{req_ms:.1f}")
    print(f"METRIC:TOTAL_MS:{total_ms:.1f}")

asyncio.run(run_single())
"""

for i in range(4):
    print(f"\n==================== [RUN {i+1}/4] ====================")
    t0 = time.time()
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    out = (res.stdout or "") + "\n" + (res.stderr or "")
    print(out)
    time.sleep(2.0)  # Cooldown between runs
