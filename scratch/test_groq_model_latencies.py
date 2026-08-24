"""
Comparative TTFT & TTFA Benchmark across Active Groq Models
Location: scratch/test_groq_model_latencies.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

from core.aura_core import AuraCore
from voice.prosody_chunker import ProsodyAwareChunker
from voice.tts_manager import TTSManager


async def benchmark_model(aura, tts_mgr, model_id, extra_params, label, prompt):
    print(f"\n--- Testing: {label} ({model_id}) ---")
    
    runs = []
    for i in range(3):
        is_cold = (i == 0)
        messages = [
            {"role": "system", "content": "You are Aura, a fast, concise AI desktop assistant. Answer in one short sentence."},
            {"role": "user", "content": prompt},
        ]

        t0 = time.perf_counter()
        t_first_token = None
        t_first_chunk = None
        t_first_audio = None
        total_tokens = 0
        chunks_received = []

        try:
            kwargs = {
                "model": model_id,
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 256,
            }
            kwargs.update(extra_params)

            # Sync Groq streaming completion
            completion = aura.groq_client.chat.completions.create(**kwargs)

            # Convert sync completion iterator to async token generator
            async def _token_gen():
                nonlocal t_first_token, total_tokens
                for chunk in completion:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        if t_first_token is None:
                            t_first_token = time.perf_counter()
                        total_tokens += 1
                        yield text

            chunker = ProsodyAwareChunker()
            async for chunk in chunker.stream_chunks(_token_gen()):
                if t_first_chunk is None:
                    t_first_chunk = time.perf_counter()
                chunks_received.append(chunk)

                # Synthesize first chunk
                if t_first_audio is None and tts_mgr.engine and hasattr(tts_mgr.engine, "_synthesize_chunk"):
                    pcm = tts_mgr.engine._synthesize_chunk(chunk)
                    if pcm:
                        t_first_audio = time.perf_counter()

            t_end = time.perf_counter()

            ttft_ms = ((t_first_token - t0) * 1000) if t_first_token else 0.0
            first_chunk_ms = ((t_first_chunk - t0) * 1000) if t_first_chunk else 0.0
            ttfa_ms = ((t_first_audio - t0) * 1000) if t_first_audio else 0.0
            total_ms = (t_end - t0) * 1000

            full_resp = " ".join(chunks_received)
            runs.append({
                "cold": is_cold,
                "ttft_ms": ttft_ms,
                "first_chunk_ms": first_chunk_ms,
                "ttfa_ms": ttfa_ms,
                "total_ms": total_ms,
                "tokens": total_tokens,
                "chunks": len(chunks_received),
                "response": full_resp,
            })
            print(f"  Run {i+1} ({'Cold' if is_cold else 'Warm'}): TTFT={ttft_ms:.1f}ms | TTFA={ttfa_ms:.1f}ms | Total={total_ms:.1f}ms | Resp: '{full_resp}'")

        except Exception as e:
            print(f"  Run {i+1} FAILED: {e}")
            runs.append({"error": str(e)})

    return {"label": label, "model_id": model_id, "runs": runs}


async def main():
    print("=" * 90)
    print("  Groq Model TTFT & TTFA Benchmark on Active Models")
    print("=" * 90)

    aura = AuraCore()
    tts_mgr = TTSManager()
    tts_mgr.initialize()

    prompt = "What is the capital of France? Answer in one short sentence."

    candidates = [
        {"model": "openai/gpt-oss-120b", "extra": {"reasoning_effort": "low"}, "label": "gpt-oss-120b (low reasoning)"},
        {"model": "openai/gpt-oss-120b", "extra": {"reasoning_effort": "medium"}, "label": "gpt-oss-120b (medium reasoning)"},
        {"model": "openai/gpt-oss-20b", "extra": {}, "label": "gpt-oss-20b"},
        {"model": "qwen/qwen3.6-27b", "extra": {}, "label": "qwen3.6-27b"},
        {"model": "groq/compound-mini", "extra": {}, "label": "groq/compound-mini"},
        {"model": "groq/compound", "extra": {}, "label": "groq/compound"},
    ]

    all_results = []
    for c in candidates:
        res = await benchmark_model(aura, tts_mgr, c["model"], c["extra"], c["label"], prompt)
        all_results.append(res)

    print("\n" + "=" * 105)
    print(f"{'Model / Configuration':<32} | {'Cold TTFT':<11} | {'Warm TTFT':<11} | {'Warm TTFA':<11} | {'Total Time':<11} | {'Target Met?'}")
    print("-" * 105)

    for res in all_results:
        label = res["label"]
        runs = res["runs"]
        valid = [r for r in runs if "error" not in r]
        if not valid:
            err = runs[0].get("error", "Error")
            print(f"{label:<32} | {'ERROR: ' + err[:65]}")
            continue

        cold_ttft = valid[0]["ttft_ms"]
        warm = valid[1:] if len(valid) > 1 else valid
        avg_warm_ttft = sum(r["ttft_ms"] for r in warm) / len(warm)
        avg_warm_ttfa = sum(r["ttfa_ms"] for r in warm) / len(warm)
        avg_total = sum(r["total_ms"] for r in warm) / len(warm)

        met = "YES (≤800ms) ✓" if avg_warm_ttfa <= 800 else f"NO ({avg_warm_ttfa:.0f}ms) ✗"
        print(f"{label:<32} | {cold_ttft:<9.1f}ms | {avg_warm_ttft:<9.1f}ms | {avg_warm_ttfa:<9.1f}ms | {avg_total:<9.1f}ms | {met}")

    print("=" * 105)


if __name__ == "__main__":
    asyncio.run(main())
