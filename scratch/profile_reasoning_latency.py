"""
scratch/profile_reasoning_latency.py

Profiles the latency of Groq API calls across:
1. reasoning_effort (low vs medium vs none)
2. Tools schema payload size (50 tools vs 5 tools vs 0 tools)
3. Model comparison (openai/gpt-oss-120b vs llama-3.3-70b-versatile vs qwen/qwen3.6-27b)
"""

import asyncio
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(1, str(PROJECT_ROOT))

from ai.key_pool import KeyPool
from core.tools.aura_tool_registry import AuraToolRegistry


def run_benchmark():
    print("=" * 70, flush=True)
    print("REASONING LATENCY PROFILING BENCHMARK", flush=True)
    print("=" * 70, flush=True)

    key_pool = KeyPool.get_instance()
    all_tools = AuraToolRegistry.get_tool_definitions()
    print(f"Total tools in registry: {len(all_tools)}", flush=True)

    test_query = "Set system volume to 50%"
    messages = [
        {"role": "system", "content": "You are Aura AI assistant. Use available tools when requested."},
        {"role": "user", "content": test_query}
    ]

    configs = [
        # (Label, model, reasoning_effort, use_tools)
        ("120B | low effort | 50 tools", "openai/gpt-oss-120b", "low", all_tools),
        ("120B | medium effort | 50 tools", "openai/gpt-oss-120b", "medium", all_tools),
        ("120B | low effort | 0 tools", "openai/gpt-oss-120b", "low", None),
        ("70B Versatile | no effort | 50 tools", "llama-3.3-70b-versatile", None, all_tools),
        ("Qwen 27B | no effort | 50 tools", "qwen/qwen3.6-27b", None, all_tools),
    ]

    for label, model, effort, tools in configs:
        kw = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = "auto"
        if effort:
            kw["reasoning_effort"] = effort

        def _do_call(api_key: str):
            client = key_pool.get_groq_client(api_key)
            t0 = time.time()
            res = client.chat.completions.create(**kw)
            duration = time.time() - t0
            return res, duration

        try:
            res, duration = key_pool.execute_with_failover(_do_call, service="groq")
            choice = res.choices[0].message
            has_tool_call = bool(getattr(choice, "tool_calls", None))
            tool_name = choice.tool_calls[0].function.name if has_tool_call else "None"
            print(f"[{duration:5.2f}s] {label:<42} -> Tool: {tool_name}", flush=True)
        except Exception as e:
            print(f"[ERROR ] {label:<42} -> {e}", flush=True)

    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_benchmark()
