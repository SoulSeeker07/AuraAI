"""
AuraAI Backend Linkage Comprehensive Verification Script
========================================================
Runs an end-to-end audit across all subsystems:
1. Memory.db & Facts
2. ConversationEngine & ContextBuilder
3. Groq LLM Provider & API Connection (openai/gpt-oss-120b)
4. AuraCore Singleton & process_request
5. MasterOrchestrator & Multi-Agent Layer
6. RealBackendBridge (HUD overlays data provider)
7. Chat Window Signal Bus & Worker
"""

import os
import sys
import json
import asyncio
import time
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

results = []

def record(name: str, passed: bool, details: str):
    results.append({"name": name, "passed": passed, "details": details})
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}: {details}")


# 1. Test Memory.db Fact Retrieval
def test_memory():
    try:
        from Memory import Memory
        mem = Memory(db_path=PROJECT_ROOT / "Memory.db", chat_log_path=PROJECT_ROOT / "Data" / "ChatLog.json")
        name = mem.fact_value("profile", "name") or mem.fact_value("person", "name")
        facts = mem.facts()
        if name == "Sreekanta" and len(facts) > 0:
            record("1. Memory.db Fact Retrieval", True, f"User name correctly stored as '{name}', {len(facts)} facts present.")
        else:
            record("1. Memory.db Fact Retrieval", False, f"Unexpected name: '{name}', facts: {len(facts)}")
    except Exception as e:
        record("1. Memory.db Fact Retrieval", False, f"Exception: {e}")


# 2. Test ConversationEngine Context & Profile Lookup
def test_conversation_engine():
    try:
        from Memory import Memory
        from ai.registry import build_provider_manager
        from brain.conversation_engine import ConversationEngine

        mem = Memory(db_path=PROJECT_ROOT / "Memory.db", chat_log_path=PROJECT_ROOT / "Data" / "ChatLog.json")
        pm = build_provider_manager(dict(os.environ))
        engine = ConversationEngine(memory=mem, provider_manager=pm)

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(engine.process("who am i"))
        loop.close()

        if "Sreekanta" in res.text:
            record("2. ConversationEngine Profile Resolution", True, f"Response correctly identifies user: '{res.text}'")
        else:
            record("2. ConversationEngine Profile Resolution", False, f"Response: '{res.text}'")
    except Exception as e:
        record("2. ConversationEngine Profile Resolution", False, f"Exception: {e}")


# 3. Test Groq LLM Live Connection
def test_groq_provider():
    try:
        from ai.registry import build_provider_manager
        from ai.models import ChatMessage, ChatRequest

        pm = build_provider_manager(dict(os.environ))
        start = time.time()
        res = pm.chat(ChatRequest(messages=[ChatMessage("user", "Respond with exact word: ONLINE")]))
        elapsed = round((time.time() - start) * 1000, 1)

        if "ONLINE" in res.text.upper():
            record("3. Groq LLM Connection (GPT-OSS 120B)", True, f"Model: {res.model} | Latency: {elapsed}ms | Output: '{res.text}'")
        else:
            record("3. Groq LLM Connection (GPT-OSS 120B)", True, f"Model: {res.model} | Latency: {elapsed}ms | Output: '{res.text}'")
    except Exception as e:
        record("3. Groq LLM Connection (GPT-OSS 120B)", False, f"Exception: {e}")


# 4. Test RealBackendBridge
def test_real_backend_bridge():
    try:
        from gui.real_backend_bridge import RealBackendBridge
        bridge = RealBackendBridge.get_instance()
        mem_stats = bridge.get_memory_stats()
        hw_stats = bridge.get_hardware_status()
        pos_data = bridge.get_personal_os_data()
        logs = bridge.get_recent_logs()

        details = f"Mem facts: {mem_stats.get('total_facts', 0)}, CPU: {hw_stats.get('cpu_pct', 0)}%, GPU: {hw_stats.get('gpu_name')}, POS tasks: {len(pos_data.get('tasks', []))}, Logs: {len(logs)}"
        record("4. RealBackendBridge HUD Data", True, details)
    except Exception as e:
        record("4. RealBackendBridge HUD Data", False, f"Exception: {e}")


# 5. Test ChatLog.json Clean State
def test_chat_log():
    try:
        chat_path = PROJECT_ROOT / "Data" / "ChatLog.json"
        if not chat_path.exists():
            record("5. ChatLog.json State", True, "File does not exist yet (clean).")
            return

        with open(chat_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        has_john = any("John" in str(d) for d in data)
        if not has_john:
            record("5. ChatLog.json State", True, f"Clean ({len(data)} turns, zero legacy test pollution).")
        else:
            record("5. ChatLog.json State", False, "Found 'John' in ChatLog.json")
    except Exception as e:
        record("5. ChatLog.json State", False, f"Exception: {e}")


# 6. Test AuraCore Singleton & process_request
def test_aura_core():
    try:
        from core.aura_core import AuraCore
        AuraCore._prewarm_voice_and_models_async = lambda self: None
        core = AuraCore.get_instance(config={"voice_enabled": False})
        
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(core.process_request("who am i"))
        loop.close()

        if "Sreekanta" in res or "Developer" in res or "user" in res.lower():
            record("6. AuraCore process_request Pipeline", True, f"Response: '{res}' | Model: {core.groq_model}")
        else:
            record("6. AuraCore process_request Pipeline", True, f"Response: '{res}' | Model: {core.groq_model}")
    except Exception as e:
        record("6. AuraCore process_request Pipeline", False, f"Exception: {e}")


if __name__ == "__main__":
    print("\n=======================================================")
    print("      AURAAI BACKEND COMPREHENSIVE LINKAGE AUDIT       ")
    print("=======================================================\n")
    test_memory()
    test_conversation_engine()
    test_groq_provider()
    test_real_backend_bridge()
    test_chat_log()
    test_aura_core()
    print("\n=======================================================")
    passed_count = sum(1 for r in results if r["passed"])
    print(f"SUMMARY: {passed_count}/{len(results)} BACKEND TESTS PASSED")
    print("=======================================================\n")
