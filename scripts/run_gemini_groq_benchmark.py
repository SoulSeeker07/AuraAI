import os
import sys
import time
import json
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.insert(0, "src")

from ai.key_pool import KeyPool
from google import genai
from groq import Groq

pool = KeyPool.get_instance()

def gemini_stream_call(model: str, prompt: str):
    def _call(key: str):
        client = genai.Client(api_key=key)
        return list(client.models.generate_content_stream(model=model, contents=prompt))
    return pool.execute_with_failover(_call, service="gemini")

def gemini_generate_call(model: str, prompt: str):
    def _call(key: str):
        client = genai.Client(api_key=key)
        return client.models.generate_content(model=model, contents=prompt)
    return pool.execute_with_failover(_call, service="gemini")

def groq_stream_call(model: str, prompt: str):
    def _call(key: str):
        client = Groq(api_key=key)
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=1500,
        )
        return list(stream)
    return pool.execute_with_failover(_call, service="groq")

def groq_generate_call(model: str, prompt: str):
    def _call(key: str):
        client = Groq(api_key=key)
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
    return pool.execute_with_failover(_call, service="groq")

def main():
    targets = [
        ("Gemini 2.5 Flash", "gemini", "gemini-2.5-flash"),
        ("Gemini 3 Flash Preview", "gemini", "gemini-3-flash-preview"),
        ("Groq GPT-OSS 120B", "groq", "openai/gpt-oss-120b"),
        ("Groq GPT-OSS 20B", "groq", "openai/gpt-oss-20b"),
    ]

    results = {name: {} for name, _, _ in targets}

    print("=" * 84)
    print("       AURA AI: GEMINI vs GROQ HEAD-TO-HEAD BENCHMARK (WITH KEY FAILOVER)")
    print("=" * 84)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n", flush=True)

    # --- TEST 1: Short Query & TTFT ---
    print(">>> TEST 1: Short Query Latency & Time to First Token (TTFT)", flush=True)
    short_prompt = "Explain the difference between a process and a thread in 2 bullet points."

    for name, provider, model in targets:
        time.sleep(1.2)
        t0 = time.perf_counter()
        first_token_time = None
        text_acc = []
        
        try:
            if provider == "gemini":
                # For TTFT measurement, we stream directly with active key
                key = pool.get_active_key("gemini")
                client = genai.Client(api_key=key)
                stream = client.models.generate_content_stream(model=model, contents=short_prompt)
                for chunk in stream:
                    txt = chunk.text or ""
                    if txt:
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - t0
                        text_acc.append(txt)
            else:
                key = pool.get_active_key("groq")
                client = Groq(api_key=key)
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": short_prompt}],
                    stream=True,
                    max_tokens=500,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - t0
                        text_acc.append(delta)
        except Exception as e:
            print(f"  [ERROR] {name} Test 1: {e}", flush=True)
            results[name]["ttft"] = 0.0
            results[name]["short_total"] = 0.0
            results[name]["short_speed"] = 0.0
            continue

        dur = time.perf_counter() - t0
        full_text = "".join(text_acc).strip()
        tokens = int(len(full_text.split()) * 1.33)
        gen_time = dur - (first_token_time or 0)
        speed = tokens / gen_time if gen_time > 0 else 0
        
        results[name]["ttft"] = first_token_time or 0.0
        results[name]["short_total"] = dur
        results[name]["short_speed"] = speed
        results[name]["short_tokens"] = tokens
        print(f"  • {name:<23} | TTFT: {results[name]['ttft']:.3f}s | Total: {dur:.2f}s | Speed: ~{speed:.0f} tok/s | Out: ~{tokens} tok", flush=True)

    print("\n>>> TEST 2: Complex Code Generation & Sustained Throughput", flush=True)
    code_prompt = """Write a Python class `AsyncTokenBucket` rate limiter using asyncio:
- takes rate (tok/s) and capacity (burst max)
- `async def acquire(tokens=1)` that waits with `asyncio.sleep` if needed
- thread/task safe
- include docstrings and a short usage example."""

    for name, provider, model in targets:
        time.sleep(1.5)
        t0 = time.perf_counter()
        first_token_time = None
        text_acc = []
        
        try:
            if provider == "gemini":
                key = pool.get_active_key("gemini")
                client = genai.Client(api_key=key)
                stream = client.models.generate_content_stream(model=model, contents=code_prompt)
                for chunk in stream:
                    txt = chunk.text or ""
                    if txt:
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - t0
                        text_acc.append(txt)
            else:
                key = pool.get_active_key("groq")
                client = Groq(api_key=key)
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": code_prompt}],
                    stream=True,
                    max_tokens=1500,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - t0
                        text_acc.append(delta)
        except Exception as e:
            print(f"  [ERROR] {name} Test 2: {e}", flush=True)
            results[name]["code_ttft"] = 0.0
            results[name]["code_total"] = 0.0
            results[name]["code_tp"] = 0.0
            results[name]["code_valid"] = False
            continue

        dur = time.perf_counter() - t0
        full_text = "".join(text_acc).strip()
        words = len(full_text.split())
        tokens = int(words * 1.33)
        gen_time = dur - (first_token_time or 0)
        tp = tokens / gen_time if gen_time > 0 else 0
        valid = "AsyncTokenBucket" in full_text and "asyncio.sleep" in full_text

        results[name]["code_ttft"] = first_token_time or 0.0
        results[name]["code_total"] = dur
        results[name]["code_tokens"] = tokens
        results[name]["code_tp"] = tp
        results[name]["code_valid"] = valid
        print(f"  • {name:<23} | TTFT: {results[name]['code_ttft']:.3f}s | Gen: {dur:.2f}s | Speed: ~{tp:.0f} tok/s | Out: ~{tokens} tok | Valid: {valid}", flush=True)

    print("\n>>> TEST 3: Structured Data Extraction (JSON Integrity)", flush=True)
    json_prompt = """Extract candidate info into pure JSON object with exact keys: name, role, years_experience, skills, certifications.
Bio: 'Alex Mercer is a Principal Cloud Architect with 12 years of enterprise experience specializing in Kubernetes, Distributed Systems, Terraform, and Python. Alex holds AWS Solutions Architect Professional and CKA certifications.'
Return ONLY raw JSON, without markdown formatting, without backticks."""

    for name, provider, model in targets:
        time.sleep(1.0)
        t0 = time.perf_counter()
        resp_text = ""
        
        try:
            if provider == "gemini":
                res = gemini_generate_call(model, json_prompt)
                resp_text = (res.text or "").strip()
            else:
                res = groq_generate_call(model, json_prompt)
                resp_text = (res.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"  [ERROR] {name} Test 3: {e}", flush=True)
            results[name]["json_time"] = 0.0
            results[name]["json_ok"] = False
            continue

        dur = time.perf_counter() - t0
        clean = resp_text.replace("```json", "").replace("```", "").strip()
        keys_ok = False
        try:
            d = json.loads(clean)
            req_keys = {"name", "role", "years_experience", "skills", "certifications"}
            keys_ok = req_keys.issubset(set(d.keys()))
        except Exception:
            keys_ok = False

        results[name]["json_time"] = dur
        results[name]["json_ok"] = keys_ok
        print(f"  • {name:<23} | Duration: {dur:.2f}s | Valid JSON Schema: {keys_ok}", flush=True)

    print("\n" + "=" * 84)
    print("                                BENCHMARK SUMMARY TABLE")
    print("=" * 84)
    fmt = "{:<24} | {:<9} | {:<10} | {:<14} | {:<11} | {:<8}"
    print(fmt.format("Model / Platform", "TTFT", "Short Lat", "Throughput", "Code Total", "JSON Test"))
    print("-" * 88)
    for name, data in results.items():
        print(fmt.format(
            name,
            f"{data.get('ttft', 0):.3f}s",
            f"{data.get('short_total', 0):.2f}s",
            f"~{data.get('code_tp', 0):.0f} tok/s",
            f"{data.get('code_total', 0):.2f}s",
            "PASS" if data.get('json_ok') else "FAIL"
        ))
    print("=" * 84, flush=True)

if __name__ == "__main__":
    main()
