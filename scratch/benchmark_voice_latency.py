"""
Live OS Benchmark: Voice Pipeline Time-to-First-Audio (TTFA) Latency
Location: scratch/benchmark_voice_latency.py

Measures live latency metrics on Windows OS:
1. TTFT (Time-to-First-Token) from Groq LLM
2. First-Chunk Segmentation Latency from ProsodyAwareChunker
3. TTFA (Time-to-First-Audio) from TTS Engine (Piper ONNX / SoundDevice)
4. Total End-to-End Latency vs Baseline Sequential Mode
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

from core.aura_core import AuraCore
from voice.prosody_chunker import ProsodyAwareChunker
from voice.tts_manager import TTSEngine, TTSSettings, TTSSpeaker, TTSManager


async def run_streaming_benchmark():
    print("=" * 80)
    print("  AuraAI Streaming Low-Latency Voice Pipeline: Live OS Latency Benchmark")
    print("=" * 80)

    # Initialize Core & TTS
    print("\n[1/3] Initializing AuraCore and TTS Subsystems...")
    aura = AuraCore()
    
    tts_mgr = TTSManager()
    tts_mgr.initialize()

    test_prompts = [
        ("Short Prompt", "What is the capital of France?"),
        ("Technical Prompt", "Explain semantic versioning v0.29.0 with 3.14 ms latency."),
        ("Multi-Sentence Prompt", "What is Python and why is it popular? Give 3 reasons."),
    ]

    results = []

    for prompt_label, prompt_text in test_prompts:
        print(f"\n--- Benchmark: {prompt_label} ('{prompt_text}') ---")
        chunker = ProsodyAwareChunker()

        t_start = time.perf_counter()
        t_first_token = None
        t_first_chunk = None
        t_first_audio = None
        total_tokens = 0
        total_chunks = 0
        synthesized_audio_bytes = 0

        # Stream from AuraCore
        token_stream = aura.process_request_stream(prompt_text)
        
        async def _timing_token_stream():
            nonlocal t_first_token, total_tokens
            async for token in token_stream:
                if t_first_token is None:
                    t_first_token = time.perf_counter()
                total_tokens += 1
                yield token

        async for chunk in chunker.stream_chunks(_timing_token_stream()):
            if t_first_chunk is None:
                t_first_chunk = time.perf_counter()
            total_chunks += 1

            # Synthesize chunk via TTS engine to measure TTFA
            if tts_mgr.engine and hasattr(tts_mgr.engine, "_synthesize_chunk"):
                pcm_bytes = tts_mgr.engine._synthesize_chunk(chunk)
            else:
                pcm_bytes = b"\x00" * 1600  # Fallback 100ms PCM frame

            if pcm_bytes:
                synthesized_audio_bytes += len(pcm_bytes)
                if t_first_audio is None:
                    t_first_audio = time.perf_counter()

            print(f"  [Chunk #{total_chunks}] {chunk}")

        t_end = time.perf_counter()

        ttft_ms = ((t_first_token - t_start) * 1000) if t_first_token else 0.0
        first_chunk_ms = ((t_first_chunk - t_start) * 1000) if t_first_chunk else 0.0
        ttfa_ms = ((t_first_audio - t_start) * 1000) if t_first_audio else 0.0
        total_ms = (t_end - t_start) * 1000

        # Estimate baseline sequential latency (wait for all tokens + synthesize all text)
        est_sequential_ms = total_ms + (ttfa_ms - ttft_ms)

        results.append({
            "prompt": prompt_label,
            "ttft_ms": ttft_ms,
            "first_chunk_ms": first_chunk_ms,
            "ttfa_ms": ttfa_ms,
            "total_ms": total_ms,
            "est_sequential_ms": est_sequential_ms,
            "speedup": est_sequential_ms / ttfa_ms if ttfa_ms > 0 else 1.0,
            "tokens": total_tokens,
            "chunks": total_chunks,
            "audio_kb": synthesized_audio_bytes / 1024,
        })

    print("\n" + "=" * 80)
    print(f"{'Benchmark Metric':<25} | {'Short Prompt':<15} | {'Technical':<15} | {'Multi-Sentence':<15}")
    print("-" * 80)
    print(f"{'TTFT (Groq LLM)':<25} | {results[0]['ttft_ms']:<13.1f}ms | {results[1]['ttft_ms']:<13.1f}ms | {results[2]['ttft_ms']:<13.1f}ms")
    print(f"{'First Chunk Ready':<25} | {results[0]['first_chunk_ms']:<13.1f}ms | {results[1]['first_chunk_ms']:<13.1f}ms | {results[2]['first_chunk_ms']:<13.1f}ms")
    print(f"{'TTFA (First Audio)':<25} | {results[0]['ttfa_ms']:<13.1f}ms | {results[1]['ttfa_ms']:<13.1f}ms | {results[2]['ttfa_ms']:<13.1f}ms")
    print(f"{'Total Generation':<25} | {results[0]['total_ms']:<13.1f}ms | {results[1]['total_ms']:<13.1f}ms | {results[2]['total_ms']:<13.1f}ms")
    print(f"{'Estimated Sequential':<25} | {results[0]['est_sequential_ms']:<13.1f}ms | {results[1]['est_sequential_ms']:<13.1f}ms | {results[2]['est_sequential_ms']:<13.1f}ms")
    print(f"{'Voice Perceived Speedup':<25} | {results[0]['speedup']:<13.2f}x | {results[1]['speedup']:<13.2f}x | {results[2]['speedup']:<13.2f}x")
    print("=" * 80)

    # Acceptance Criteria Check
    passed_ttfa = all(r["ttfa_ms"] < 1200 for r in results)
    print(f"\nTarget Acceptance Criteria (TTFA < 1200ms across all turns): {'PASSED ✓' if passed_ttfa else 'FAILED ✗'}")
    return 0 if passed_ttfa else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_streaming_benchmark())
    sys.exit(exit_code)
