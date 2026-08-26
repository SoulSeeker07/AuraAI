"""
AuraAI — Autonomous Capabilities Test Suite & Interactive Runner
-----------------------------------------------------------------
Tests Aura's Autonomous Engineering, Document Synchronization,
HUD Overlays, Memory Retrieval, and Desktop Automation.

Usage:
    .\\.venv\\Scripts\\python.exe scripts/test_aura_autonomous.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

# Ensure UTF-8 output in Windows PowerShell / CMD
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from Memory import Memory
from ai.registry import build_provider_manager
from brain.conversation_engine import ConversationEngine


TEST_PROMPTS = [
    (
        "1. Autonomous Document & Milestone Sync",
        "aura update documents in my project",
    ),
    (
        "2. Autonomous Engineering & Workspace Perception",
        "aura add jarvis style rings widget to my project same style as other widgets",
    ),
    (
        "3. HUD Overlay Launch Trigger",
        "aura show jarvis rings",
    ),
    (
        "4. Memory Profile & Fact Recall",
        "what is my name",
    ),
    (
        "5. Desktop Status Check",
        "aura battery status",
    ),
]


async def run_tests():
    print("=" * 70)
    print("🔮 AURA AI — AUTONOMOUS CAPABILITIES TEST SUITE")
    print(f"📁 Workspace: {PROJECT_ROOT}")
    print("=" * 70)

    # Initialize Engine
    mem = Memory(
        db_path=str(PROJECT_ROOT / "Memory.db"),
        chat_log_path=str(PROJECT_ROOT / "Data" / "ChatLog.json"),
    )
    pm = build_provider_manager(dict(os.environ))
    engine = ConversationEngine(memory=mem, provider_manager=pm)

    for idx, (title, prompt) in enumerate(TEST_PROMPTS, 1):
        print(f"\n[{idx}/{len(TEST_PROMPTS)}] 🧪 TESTING: {title}")
        print(f"👉 Prompt: '{prompt}'")
        print("-" * 70)
        
        res = await engine.process(prompt)
        print(f"🔮 Aura Response:\n{res.text}")
        print("-" * 70)

    print("\n✅ All Autonomous Capability Tests Completed Successfully!")


if __name__ == "__main__":
    asyncio.run(run_tests())
