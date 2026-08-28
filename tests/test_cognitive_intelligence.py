"""
Test Suite for AuraAI Cognitive Intelligence Engine Upgrades
"""

import sys
import asyncio
from pathlib import Path

# Add src and root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(1, str(PROJECT_ROOT))

from core.tools.aura_tool_registry import AuraToolRegistry
from core.context.ambient_context_builder import AmbientContextBuilder
from core.aura_core import AuraCore


def test_tool_definitions():
    """Verify tool schemas are valid OpenAI/Groq function calling format."""
    tools = AuraToolRegistry.get_tool_definitions()
    assert len(tools) >= 8, f"Expected at least 8 tools, got {len(tools)}"
    
    for tool in tools:
        assert tool.get("type") == "function"
        fn = tool.get("function", {})
        assert "name" in fn and len(fn["name"]) > 0
        assert "description" in fn and len(fn["description"]) > 0
        assert "parameters" in fn
        assert fn["parameters"].get("type") == "object"
        assert "properties" in fn["parameters"]


def test_ambient_context_builder():
    """Verify ambient context builder gathers time, window, and system state."""
    ctx = AmbientContextBuilder.build_ambient_context()
    assert isinstance(ctx, str)
    assert "Current System Time" in ctx
    assert "Active Focused Window" in ctx or "Hardware State" in ctx


def test_tool_telemetry_execution():
    """Verify synchronous/async execution of telemetry tool."""
    async def _run():
        res = await AuraToolRegistry.execute_tool("system_get_telemetry", {})
        assert res.get("status") == "success"
        assert "cpu_usage" in res
        assert "ram_usage" in res
        assert "battery" in res

    asyncio.run(_run())


def test_multiturn_message_assembly():
    """Verify AuraCore builds multi-turn conversation messages correctly."""
    core = AuraCore.get_instance()
    core.clear_conversation_history()

    core.add_to_conversation("user", "Hello Aura, remember that my project is called Phoenix.")
    core.add_to_conversation("assistant", "Understood, I will remember project Phoenix.")

    messages = core._build_chat_messages("What is my project name?")
    assert len(messages) == 4  # system + user + assistant + new user
    assert messages[0]["role"] == "system"
    assert "AuraAI (v17.0)" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[2]["role"] == "assistant"
    assert messages[3]["role"] == "user"
    assert messages[3]["content"] == "What is my project name?"


if __name__ == "__main__":
    test_tool_definitions()
    print("✓ test_tool_definitions passed")
    test_ambient_context_builder()
    print("✓ test_ambient_context_builder passed")
    test_tool_telemetry_execution()
    print("✓ test_tool_telemetry_execution passed")
    test_multiturn_message_assembly()
    print("✓ test_multiturn_message_assembly passed")
    print("\n🎉 ALL COGNITIVE INTELLIGENCE TESTS PASSED SUCCESSFULLY!")
