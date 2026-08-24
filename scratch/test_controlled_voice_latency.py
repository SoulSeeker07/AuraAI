"""
Controlled Multi-Model and Chunker Parameter Latency Benchmark
Location: scratch/test_controlled_voice_latency.py
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


async def run_single_eval(aura, tts_mgr, model_id, reasoning_effort, chunker, prompt):
    messages = [
        {"role": "system", "content": "You are Aura, a fast, helpful desktop AI assistant."},
        {"role": "user", "content": prompt},
    ]

    kwargs = {
        "model": model_id,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 256,
    }
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort

    t0 = time.perf_counter()
    t_first_token = None
    t_first_chunk = None
    t_first_audio = None
    token_timestamps = []
    tokens = []
    chunks = []

    completion = aura.groq_client.chat.completions.create(**kwargs)

    async def _token_gen():
        nonlocal t_first_token
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                now = time.perf_counter()
                if t_first_token is None:
                    t_first_token = now
                token_timestamps.append(now)
                tokens.append(text)
                yield text

    async for c in chunker.stream_chunks(_token_gen()):
        if t_first_chunk is None:
            t_first_chunk = time.perf_counter()
        chunks.append(c)

        if t_first_audio is None and tts_mgr.engine and hasattr(tts_mgr.engine, "_synthesize_chunk"):
            pcm = tts_mgr.engine._synthesize_chunk(c)
            if pcm:
                t_first_audio = time.perf_counter()

    t_end = time.perf_counter()

    ttft_ms = ((t_first_token - t0) * 1000) if t_first_token else 0.0
    first_chunk_ms = ((t_first_chunk - t0) * 1000) if t_first_chunk else 0.0
    ttfa_ms = ((t_first_audio - t0) * 1000) if t_first_audio else 0.0
    total_ms = (t_end - t0) * 1000

    chunker_overhead_ms = (first_chunk_ms - ttft_ms) if (t_first_chunk and t_first_token) else 0.0

    return {
        "ttft_ms": ttft_ms,
        "first_chunk_ms": first_chunk_ms,
        "chunker_overhead_ms": chunker_overhead_ms,
        "ttfa_ms": ttfa_ms,
        "total_ms": total_ms,
        "tokens_count": len(tokens),
        "chunks_count": len(chunks),
        "first_chunk": chunks[0] if chunks else "",
        "full_text": "".join(tokens),
    }


async def main():
    print("=" * 95)
    print("  Controlled Voice Pipeline Latency Benchmark: gpt-oss-120b vs gpt-oss-20b")
    print("=" * 95)

    aura = AuraCore()
    tts_mgr = TTSManager()
    tts_mgr.initialize()

    prompts = [
        ("Short Prompt", "What is the capital of France? Answer in one short sentence."),
        ("Technical Prompt", "Explain semantic versioning v0.29.0 with 3.14 ms latency in 2 sentences."),
        ("Multi-Sentence Prompt", "What is Python and why is it popular? Give 3 concise bullet points."),
    ]

    models_to_test = [
        ("openai/gpt-oss-120b", "medium", "gpt-oss-120b (medium)"),
        ("openai/gpt-oss-20b", None, "gpt-oss-20b"),
    ]

    # Warm up Groq connection & TTS
    print("\n[Warming up client connections...]")
    _ = await run_single_eval(aura, tts_mgr, "openai/gpt-oss-120b", "medium", ProsodyAwareChunker(), "Say hello.")
    _ = await run_single_eval(aura, tts_mgr, "openai/gpt-oss-20b", None, ProsodyAwareChunker(), "Say hello.")
    print("[Warm-up complete]\n")

    results = []

    for model_id, effort, model_label in models_to_test:
        print(f"\n{'='*40} Model: {model_label} {'='*40}")

        for prompt_label, prompt_text in prompts:
            print(f"\n--- Scenario: {prompt_label} ---")
            print(f"Prompt: '{prompt_text}'")

            runs = []
            for r in range(3):
                chunker = ProsodyAwareChunker()
                res = await run_single_eval(aura, tts_mgr, model_id, effort, chunker, prompt_text)
                runs.append(res)
                print(f"  Run {r+1}: TTFT={res['ttft_ms']:<6.1f}ms | ChunkerDelay={res['chunker_overhead_ms']:<6.1f}ms | TTFA={res['ttfa_ms']:<6.1f}ms | Total={res['total_ms']:<6.1f}ms | 1stChunk='{res['first_chunk'][:45]}...'")

            avg_ttft = sum(x["ttft_ms"] for x in runs) / len(runs)
            avg_chunker_delay = sum(x["chunker_overhead_ms"] for x in runs) / len(runs)
            avg_ttfa = sum(x["ttfa_ms"] for x in runs) / len(runs)
            avg_total = sum(x["total_ms"] for x in runs) / len(runs)

            results.append({
                "model": model_label,
                "prompt": prompt_label,
                "avg_ttft": avg_ttft,
                "avg_chunker_delay": avg_chunker_delay,
                "avg_ttfa": avg_ttfa,
                "avg_total": avg_total,
                "runs": runs,
            })

    # Print Summary Table
    print("\n" + "=" * 105)
    print(f"{'Model':<22} | {'Prompt Scenario':<20} | {'Avg TTFT':<10} | {'Chunker Lag':<12} | {'Avg TTFA':<10} | {'Target <=800ms'}")
    print("-" * 105)
    for r in results:
        target_str = "PASSED ✓" if r["avg_ttfa"] <= 800 else f"MISSED ({r['avg_ttfa']:.0f}ms) ✗"
        print(f"{r['model']:<22} | {r['prompt']:<20} | {r['avg_ttft']:<8.1f}ms | {r['avg_chunker_delay']:<10.1f}ms | {r['avg_ttfa']:<8.1f}ms | {target_str}")
    print("=" * 105)


if __name__ == "__main__":
    asyncio.run(main())
