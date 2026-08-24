"""
Test openai/gpt-oss-120b across conversational prompts
Location: scratch/test_gpt_oss_120b_multiturn.py
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


async def run_gpt_oss_benchmark():
    print("=" * 85)
    print("  Live OS Latency Benchmark: openai/gpt-oss-120b on Groq")
    print("=" * 85)

    aura = AuraCore()
    tts_mgr = TTSManager()
    tts_mgr.initialize()

    test_prompts = [
        ("Short Prompt", "What is the capital of France? Answer concisely in one sentence."),
        ("Technical Prompt", "Explain semantic versioning v0.29.0 with 3.14 ms latency in 2 sentences."),
        ("Multi-Sentence Prompt", "What is Python and why is it popular? Give 3 concise bullet points."),
    ]

    for label, prompt in test_prompts:
        print(f"\n--- Benchmark: {label} ---")
        print(f"Prompt: '{prompt}'")
        
        messages = [
            {"role": "system", "content": "You are Aura, a fast, helpful, concise AI desktop assistant."},
            {"role": "user", "content": prompt},
        ]

        t0 = time.perf_counter()
        t_first_token = None
        t_first_chunk = None
        t_first_audio = None
        total_tokens = 0
        chunks = []

        completion = aura.groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=512,
            reasoning_effort="medium",
        )

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
            chunks.append(chunk)

            if t_first_audio is None and tts_mgr.engine and hasattr(tts_mgr.engine, "_synthesize_chunk"):
                pcm = tts_mgr.engine._synthesize_chunk(chunk)
                if pcm:
                    t_first_audio = time.perf_counter()
            print(f"  [Chunk #{len(chunks)}] {chunk}")

        t_end = time.perf_counter()

        ttft_ms = ((t_first_token - t0) * 1000) if t_first_token else 0.0
        first_chunk_ms = ((t_first_chunk - t0) * 1000) if t_first_chunk else 0.0
        ttfa_ms = ((t_first_audio - t0) * 1000) if t_first_audio else 0.0
        total_ms = (t_end - t0) * 1000

        print(f"\n  [Metrics]: TTFT={ttft_ms:.1f}ms | FirstChunk={first_chunk_ms:.1f}ms | TTFA={ttfa_ms:.1f}ms | Total={total_ms:.1f}ms | Tokens={total_tokens}")
        print(f"  [TTFA Target <= 800ms]: {'PASSED ✓' if ttfa_ms <= 800 else 'MISSED ✗'}")


if __name__ == "__main__":
    asyncio.run(run_gpt_oss_benchmark())
