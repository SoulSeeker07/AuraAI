"""
scratch/test_live_progress_stream.py

Demonstration and verification of real-time intermediate progress event streaming
through CLIClient, AuraCore, and MasterOrchestrator.
"""

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(1, str(PROJECT_ROOT))

from core.aura_core import AuraCore
from core.progress_events import ProgressEmitter, CLIProgressRenderer


async def run_live_e2e_queries():
    print("=" * 70, flush=True)
    print("🚀 LIVE END-TO-END PROGRESS EVENT STREAMING TEST", flush=True)
    print("=" * 70, flush=True)

    # 1. Initialize Aura Core
    aura_core = AuraCore()

    queries = [
        # Query 1: Deterministic / Local intent
        "what time is it",
        # Query 2: Multi-stage desktop orchestration query
        "set volume to 60 and summarize today's session",
    ]

    for idx, query in enumerate(queries, 1):
        print(f"\n[{idx}] ───────────────────────────────────────────────────", flush=True)
        print(f"User Goal: '{query}'", flush=True)
        print("──────────────────────────────────────────────────────────", flush=True)

        # Test A: Collapsed Mode (default CLI user experience)
        print("\n--- [A] Collapsed Single-Line Mode (as seen by interactive user) ---", flush=True)
        emitter_collapsed = ProgressEmitter()
        renderer_collapsed = CLIProgressRenderer(expanded=False)
        emitter_collapsed.subscribe(renderer_collapsed)

        res_collapsed = await aura_core.process_request(query, emitter=emitter_collapsed)
        renderer_collapsed.finish()
        print(f"\nFinal Answer: {res_collapsed[:120]}..." if len(res_collapsed) > 120 else f"\nFinal Answer: {res_collapsed}", flush=True)

        # Test B: Expanded Mode (developer / trace mode)
        print("\n--- [B] Expanded Step Trace (developer / 'mode trace' view) ---", flush=True)
        emitter_expanded = ProgressEmitter()
        renderer_expanded = CLIProgressRenderer(expanded=True)
        emitter_expanded.subscribe(renderer_expanded)

        res_expanded = await aura_core.process_request(query, emitter=emitter_expanded)
        renderer_expanded.finish()
        renderer_expanded.render_full_trace()

    print("\n" + "=" * 70, flush=True)
    print("✨ LIVE E2E PROGRESS EVENT VERIFICATION COMPLETE", flush=True)
    print("=" * 70, flush=True)

    aura_core.shutdown()


if __name__ == "__main__":
    asyncio.run(run_live_e2e_queries())
