import os
import sys
import time
from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.insert(0, "src")

from google import genai

key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=key)

models = ["gemini-3-flash-preview", "gemini-3.6-flash"]
results = {m: {} for m in models}

print("=== BENCHMARK: GEMINI 3 FLASH PREVIEW vs GEMINI 3.6 FLASH ===\n")

# 1. LATENCY (Short prompt)
print("--- Test 1: Short Prompt Latency (3 runs avg) ---")
for m in models:
    latencies = []
    for i in range(3):
        t0 = time.perf_counter()
        resp = client.models.generate_content(
            model=m,
            contents="Explain what is an API in 1 sentence."
        )
        lat = time.perf_counter() - t0
        latencies.append(lat)
        time.sleep(1)
    avg_lat = sum(latencies) / len(latencies)
    results[m]["short_latency"] = avg_lat
    sample = resp.text.strip().replace("\n", " ")[:70]
    print(f"[{m}] Avg Latency: {avg_lat:.2f}s | Sample: \"{sample}...\"")

# 2. STREAMING TTFT (Time to First Token)
print("\n--- Test 2: Streaming Time to First Token (TTFT) ---")
for m in models:
    t0 = time.perf_counter()
    stream = client.models.generate_content_stream(
        model=m,
        contents="Write a concise 3-paragraph summary of quantum computing."
    )
    ttft = None
    total_chunks = 0
    total_chars = 0
    for chunk in stream:
        if ttft is None:
            ttft = time.perf_counter() - t0
        total_chunks += 1
        total_chars += len(chunk.text or "")
    total_time = time.perf_counter() - t0
    results[m]["ttft"] = ttft
    results[m]["stream_total_time"] = total_time
    results[m]["stream_chunks"] = total_chunks
    results[m]["stream_chars"] = total_chars
    print(f"[{m}] TTFT: {ttft:.2f}s | Total Time: {total_time:.2f}s | Chunks: {total_chunks} | Output: {total_chars} chars")
    time.sleep(1)

# 3. CODE GENERATION & REASONING (Complex task)
print("\n--- Test 3: Code Generation Benchmark (Thread-Safe LRU Cache) ---")
code_prompt = """
Write a Python class `ThreadSafeLRUCache(capacity: int)` that supports `get(key)` and `put(key, value)` with O(1) time complexity.
Use a doubly linked list and a hash map with threading.RLock. Include full docstrings and 2 doctests.
"""
for m in models:
    t0 = time.perf_counter()
    resp = client.models.generate_content(
        model=m,
        contents=code_prompt
    )
    gen_time = time.perf_counter() - t0
    text = resp.text or ""
    words = len(text.split())
    tok_per_sec = words / gen_time if gen_time > 0 else 0
    results[m]["code_time"] = gen_time
    results[m]["code_words"] = words
    results[m]["code_tok_per_sec"] = tok_per_sec
    has_lock = "RLock" in text or "Lock" in text
    has_dll = "prev" in text and "next" in text
    print(f"[{m}] Generation Time: {gen_time:.2f}s | Words: {words} | Speed: ~{tok_per_sec:.1f} words/s")
    print(f"[{m}] Code Quality Checks: Uses Lock={has_lock}, DoublyLinkedList={has_dll}")
    time.sleep(1)

print("\n=== BENCHMARK SUMMARY TABLE ===")
print(f"{'Metric':<25} | {'gemini-3-flash-preview':<25} | {'gemini-3.6-flash':<25}")
print("-" * 80)
print(f"{'Short Prompt Latency':<25} | {results['gemini-3-flash-preview']['short_latency']:.2f}s{'':<20} | {results['gemini-3.6-flash']['short_latency']:.2f}s")
print(f"{'Streaming TTFT':<25} | {results['gemini-3-flash-preview']['ttft']:.2f}s{'':<20} | {results['gemini-3.6-flash']['ttft']:.2f}s")
print(f"{'Stream Total Time':<25} | {results['gemini-3-flash-preview']['stream_total_time']:.2f}s{'':<20} | {results['gemini-3.6-flash']['stream_total_time']:.2f}s")
print(f"{'Code Gen Time':<25} | {results['gemini-3-flash-preview']['code_time']:.2f}s{'':<20} | {results['gemini-3.6-flash']['code_time']:.2f}s")
print(f"{'Code Gen Speed':<25} | ~{results['gemini-3-flash-preview']['code_tok_per_sec']:.1f} words/s{'':<14} | ~{results['gemini-3.6-flash']['code_tok_per_sec']:.1f} words/s")
