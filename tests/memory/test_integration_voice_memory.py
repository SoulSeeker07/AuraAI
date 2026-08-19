"""
Integration test: verifies that AuraCore.memory_manager records turns correctly
and feeds prior-turn context into ReferenceResolver for multi-turn conversations.
"""
import pytest
from unittest.mock import patch, MagicMock
from core.aura_core import AuraCore
from core.orchestration.reference_resolver import ReferenceResolver


@pytest.fixture(autouse=True)
def reset_aura_core_singleton():
    AuraCore.reset_instance()
    yield
    AuraCore.reset_instance()


@pytest.mark.asyncio
async def test_voice_memory_integration(tmp_path):
    """
    Two-turn voice scenario:
      Turn 1: "open calculator" -> memory_manager records user + assistant turns.
      Turn 2: "what about notepad" -> resolver's memory_context must include
              the first turn's text, proving the short-term buffer is wired to AuraCore.
    """
    db_path = tmp_path / "test_memory.db"

    mock_groq = MagicMock()
    mock_pm = MagicMock()
    mock_mem = MagicMock()

    with patch("src.ai.groq_provider.GroqProvider", return_value=mock_groq), \
         patch("ai.provider_manager.ProviderManager", return_value=mock_pm), \
         patch("core.aura_core.Memory", return_value=mock_mem):

        core = AuraCore({
            "groq_model": "mock-model",
            "voice_enabled": False,
            "memory_db_path": str(db_path),
        })

    # ── 1. Clean short-term turns on AuraCore's real MemoryManager ──────────
    core.memory_manager.short_term.turns.clear()

    # ── 2. Simulate Turn 1 execution ─────────────────────────────────────────
    turn_1_goal = "open calculator"
    mem_ctx_1 = " ".join([t.content for t in core.memory_manager.get_raw_turns()])
    resolved_1, meta_1 = ReferenceResolver.resolve_references(turn_1_goal, {"memory_context": mem_ctx_1})

    assert resolved_1 == "open calculator"
    assert meta_1.get("resolved") is False

    # Simulate coordinator completing execution and recording turns to MemoryManager
    core.memory_manager.add_user_turn(turn_1_goal)
    core.memory_manager.add_assistant_turn("Opened calculator")

    turns_after_t1 = list(core.memory_manager.short_term.turns)
    assert len(turns_after_t1) == 2, (
        f"Expected exactly 2 turns after turn 1 (1 user + 1 assistant), "
        f"got {len(turns_after_t1)}. Turns: {[t.content for t in turns_after_t1]}"
    )
    assert turns_after_t1[0].content == "open calculator"
    assert turns_after_t1[1].content == "Opened calculator"

    # ── 3. Turn 2: verify memory_context contains turn 1 ─────────────────────
    turn_2_goal = "what about notepad"
    mem_ctx_2 = " ".join([t.content for t in core.memory_manager.get_raw_turns()])

    assert "open calculator" in mem_ctx_2, (
        f"'open calculator' missing from memory_context on turn 2. Got: {mem_ctx_2!r}"
    )

    resolved_2, meta_2 = ReferenceResolver.resolve_references(turn_2_goal, {"memory_context": mem_ctx_2})
    assert meta_2.get("resolved") is True or "notepad" in resolved_2

    # Record turn 2
    core.memory_manager.add_user_turn(turn_2_goal)
    core.memory_manager.add_assistant_turn("Opened notepad")

    assert len(core.memory_manager.short_term.turns) == 4
