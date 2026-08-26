import time
import asyncio
import io
import edge_tts
import soundfile as sf

async def benchmark_edge_tts():
    sentences = [
        "Short phrase.",
        "Hello! I am Aura, your personal desktop AI assistant. How can I help you today?",
        "Streaming text to speech allows the user to hear the start of the sentence almost immediately while the remaining audio data continues downloading in the background."
    ]
    
    print("=== Empirical Edge-TTS Latency Benchmark ===")
    for text in sentences:
        print(f"\nText ({len(text)} chars): '{text[:40]}...'")
        comm = edge_tts.Communicate(text, "en-US-AriaNeural")
        
        t0 = time.perf_counter()
        first_chunk_time = None
        chunks = []
        
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                if first_chunk_time is None:
                    first_chunk_time = time.perf_counter() - t0
                chunks.append(chunk["data"])
                
        total_time = time.perf_counter() - t0
        raw_audio = b"".join(chunks)
        data, sr = sf.read(io.BytesIO(raw_audio))
        audio_duration = len(data) / sr
        
        print(f"  - Time to First Audio Chunk (TTFB): {first_chunk_time*1000:.1f} ms")
        print(f"  - Total Stream Time: {total_time*1000:.1f} ms")
        print(f"  - Synthesized Duration: {audio_duration:.2f} s")
        print(f"  - Streaming Gain (Saved Wait Time): {(total_time - first_chunk_time)*1000:.1f} ms ({((total_time - first_chunk_time)/total_time)*100:.1f}% reduction)")

if __name__ == "__main__":
    asyncio.run(benchmark_edge_tts())
