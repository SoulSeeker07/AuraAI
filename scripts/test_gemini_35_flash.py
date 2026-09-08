import os
import sys
import time
from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.insert(0, "src")

from ai.key_pool import KeyPool
from google import genai
from google.genai import types

def test_model(model_name: str):
    pool = KeyPool.get_instance()
    key = pool.get_active_key("gemini")
    client = genai.Client(api_key=key)

    print(f"\n=======================================================", flush=True)
    print(f"Testing: {model_name}", flush=True)
    print(f"=======================================================", flush=True)

    # 1. Chat
    print("1. Testing Basic Completion...", flush=True)
    try:
        t0 = time.perf_counter()
        resp = client.models.generate_content(
            model=model_name,
            contents="Explain what is a hash map in 1 sentence."
        )
        dur = time.perf_counter() - t0
        print(f"   [OK] Chat in {dur:.2f}s: {(resp.text or '').strip()[:80]}...", flush=True)
    except Exception as e:
        print(f"   [FAIL] Chat error: {e}", flush=True)

    # 2. Streaming & TTFT
    print("2. Testing Streaming TTFT...", flush=True)
    try:
        t0 = time.perf_counter()
        stream = client.models.generate_content_stream(
            model=model_name,
            contents="Write 3 quick tips for clean code."
        )
        ttft = None
        chunks = []
        for chunk in stream:
            txt = chunk.text or ""
            if txt:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                chunks.append(txt)
        total_time = time.perf_counter() - t0
        full_text = "".join(chunks).strip()
        words = len(full_text.split())
        gen_time = total_time - (ttft or 0)
        tok_s = (words * 1.33) / gen_time if gen_time > 0 else 0
        print(f"   [OK] TTFT: {ttft:.3f}s | Total: {total_time:.2f}s | Speed: ~{tok_s:.1f} tok/s", flush=True)
    except Exception as e:
        print(f"   [FAIL] Stream error: {e}", flush=True)

    # 3. Function Calling
    print("3. Testing Function Calling...", flush=True)
    try:
        tool_decl = types.FunctionDeclaration(
            name="get_weather",
            description="Get weather for a city",
            parameters={
                "type": "OBJECT",
                "properties": {"city": {"type": "STRING"}},
                "required": ["city"]
            }
        )
        cfg = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[tool_decl])],
            temperature=0.0
        )
        t0 = time.perf_counter()
        tool_resp = client.models.generate_content(
            model=model_name,
            contents="What is the weather in Tokyo?",
            config=cfg
        )
        dur = time.perf_counter() - t0
        called_fn = None
        fn_args = None
        for candidate in tool_resp.candidates:
            for part in candidate.content.parts:
                if part.function_call:
                    called_fn = part.function_call.name
                    fn_args = part.function_call.args
        print(f"   [OK] Function Calling in {dur:.2f}s: called {called_fn}({fn_args})", flush=True)
    except Exception as e:
        print(f"   [FAIL] Function Calling error: {e}", flush=True)

    # 4. Code Generation
    print("4. Testing Code Generation...", flush=True)
    try:
        t0 = time.perf_counter()
        code_resp = client.models.generate_content(
            model=model_name,
            contents="Write a Python class for a LRU Cache."
        )
        dur = time.perf_counter() - t0
        print(f"   [OK] Code Gen in {dur:.2f}s | Output: {len(code_resp.text or '')} chars", flush=True)
    except Exception as e:
        print(f"   [FAIL] Code Gen error: {e}", flush=True)

def main():
    test_model("gemini-3.5-flash")
    time.sleep(2)
    test_model("gemini-3.5-flash-lite")

if __name__ == "__main__":
    main()
