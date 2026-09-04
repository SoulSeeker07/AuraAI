"""
scratch/profile_chat_messages_payload.py

Tests the latency impact of AuraCore._build_chat_messages vs minimal messages.
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

from core.aura_core import AuraCore
from ai.key_pool import KeyPool
from core.tools.aura_tool_registry import AuraToolRegistry


def run_benchmark():
    print("=" * 70, flush=True)
    print("AURA CORE PROMPT CONTEXT LATENCY BENCHMARK", flush=True)
    print("=" * 70, flush=True)

    aura = AuraCore()
    key_pool = KeyPool.get_instance()
    all_tools = AuraToolRegistry.get_tool_definitions()

    test_query = "set volume to 60 and summarize today's session"

    # 1. Minimal prompt
    minimal_messages = [
        {"role": "system", "content": "You are Aura AI assistant. Use available tools when requested."},
        {"role": "user", "content": test_query}
    ]

    # 2. Full AuraCore prompt
    full_messages = aura._build_chat_messages(test_query)

    print(f"Minimal prompt character length: {len(minimal_messages[0]['content'])} chars", flush=True)
    full_chars = sum(len(str(m.get('content', ''))) for m in full_messages)
    print(f"Full AuraCore messages total length: {full_chars} chars across {len(full_messages)} messages", flush=True)

    configs = [
        ("120B | Minimal Prompt", minimal_messages),
        ("120B | Full AuraCore Prompt", full_messages),
    ]

    for label, msgs in configs:
        kw = {
            "model": "openai/gpt-oss-120b",
            "messages": msgs,
            "tools": all_tools,
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens": 1024,
            "reasoning_effort": "low",
        }

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
            print(f"[{duration:5.2f}s] {label:<35} -> Tool: {tool_name}", flush=True)
        except Exception as e:
            print(f"[ERROR ] {label:<35} -> {e}", flush=True)

    print("=" * 70, flush=True)
    aura.shutdown()


if __name__ == "__main__":
    run_benchmark()
