"""
Integration test: ContextBuilder wires MemoryManager into ConversationEngine.

This test constructs ConversationEngine directly (bypassing AuraCore) to keep
the fixture lean and predictable.  It:

  1. Seeds the MemoryManager with a "Turn 1" user message ("open calculator").
  2. Calls ConversationEngine.process("what about notepad").
  3. Asserts that the ChatRequest sent to the LLM provider contains
     "open calculator" in the messages, proving ContextBuilder.build() injected
     the short-term buffer correctly.

This is the seam the user flagged as needing a real proof: that
ContextBuilder/ConversationEngine actually reads from the shared MemoryManager,
not from a separate buffer.
"""
import pytest
from unittest.mock import MagicMock, patch

from src.brain.conversation_engine import ConversationEngine
from src.memory.manager.memory_manager import MemoryManager
from ai.provider_manager import ProviderManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(memory_manager: MemoryManager) -> ConversationEngine:
    """Build a ConversationEngine with a mocked LLM provider."""
    mock_memory = MagicMock()
    mock_memory.get_context.return_value = ""
    mock_memory.get_recent_messages.return_value = []

    provider_manager = MagicMock(spec_set=["chat", "register"])
    provider_manager.chat.return_value = MagicMock(
        text="Notepad is now open.",
        provider="mock",
        model="mock",
    )

    engine = ConversationEngine(
        memory=mock_memory,
        provider_manager=provider_manager,
        settings={"provider": "mock", "model": "mock"},
        memory_manager=memory_manager,
    )
    return engine


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_builder_injects_memory_manager_turns():
    """
    ConversationEngine must pass prior turns from MemoryManager to the LLM.
    """
    # ── Setup ───────────────────────────────────────────────────────────────
    provider_mgr = ProviderManager()
    memory_manager = MemoryManager(provider_manager=provider_mgr)

    # Seed "Turn 1" — simulates what PersonalOSRuntime.execute_goal writes
    # after processing "open calculator"
    memory_manager.add_user_turn("open calculator")
    memory_manager.add_assistant_turn("Calculator is now open.", user_text="open calculator")

    engine = _make_engine(memory_manager)

    # ── Exercise ─────────────────────────────────────────────────────────────
    # Mock IntentRouter so we don't need a real Memory for intent classification
    # The real method is detect(), not route()
    with patch.object(engine.intent_router, "detect") as mock_detect:
        from brain.models import Intent
        mock_detect.return_value = Intent("chat")

        # Mock web search to avoid real I/O
        with patch.object(engine.web_search, "search", return_value=[]):
            result = await engine.process("what about notepad")

    # ── Assert ───────────────────────────────────────────────────────────────
    assert engine.provider_manager.chat.called, (
        "ProviderManager.chat was never called — ConversationEngine bailed early"
    )

    chat_call = engine.provider_manager.chat.call_args[0][0]   # ChatRequest
    message_texts = [m.content for m in chat_call.messages]

    assert any("open calculator" in txt for txt in message_texts), (
        f"'open calculator' not found in LLM context messages.\n"
        f"Messages sent: {message_texts}"
    )

    assert chat_call.messages[-1].content == "what about notepad", (
        f"Last message should be the user turn.\n"
        f"Got: {chat_call.messages[-1].content!r}"
    )
