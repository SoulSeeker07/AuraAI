"""
Integration test: verifies that PersonalOSRuntime.execute_goal feeds the
memory_manager correctly and that the ReferenceResolver receives prior-turn
context on the second call.

This drives the REAL execute_goal() path (including NLU → ReferenceResolver)
but mocks out the coordinator to avoid needing a real desktop/OS backend.
"""
import pytest
from unittest.mock import patch, MagicMock
from src.core.orchestration.personal_os_runtime import PersonalOSRuntime


def _make_coord_result(goal: str, success: bool = True):
    """Build a coordinator mock result with the attributes ActivityTraceRenderer needs."""
    result = MagicMock()
    result.goal = goal
    result.success = success
    result.total_time = 0.01
    result.step_results = []
    result.data = {}
    result.observations = [f"Opened {goal}"]
    result.confidence = 1.0
    return result


@pytest.mark.asyncio
async def test_voice_memory_integration():
    """
    Two-turn voice scenario:
      Turn 1: "open calculator"  → resolver gets no prior context
      Turn 2: "what about notepad" → resolver's memory_context must include
              the first turn's text, proving the short-term buffer is wired.
    """
    # ── 1. Grab singleton and wipe short-term buffer for clean state ──────────
    runtime = PersonalOSRuntime.get_instance()
    runtime.memory_manager.short_term.turns.clear()

    # ── 2. Patch the coordinator to skip real OS execution ───────────────────
    with patch.object(runtime.coordinator, "coordinate",
                      return_value=_make_coord_result("open calculator")) as mock_coord, \
         patch.object(runtime.nlu_engine, "process",
                      return_value=MagicMock(normalized_text="open calculator")) as mock_nlu, \
         patch.object(runtime, "_resolve_expert_domains",
                      return_value=[]) as mock_expert, \
         patch.object(runtime.reference_resolver, "resolve_references",
                      return_value=("open calculator", {"resolved": False})) as mock_resolve:

        # ── Turn 1 ────────────────────────────────────────────────────────────
        await runtime.execute_goal("open calculator")

        assert mock_resolve.call_count == 1, "ReferenceResolver not called on turn 1"

        turns_after_t1 = list(runtime.memory_manager.short_term.turns)
        assert len(turns_after_t1) >= 1
        assert turns_after_t1[0].content == "open calculator", (
            f"Expected 'open calculator' in first turn, got {turns_after_t1[0].content!r}"
        )

        # ── Double-log guard (issue #4) ────────────────────────────────────────
        # execute_goal writes user turn (line 226) and assistant turn (line 358).
        # If MasterOrchestrator._write_memory ALSO writes, this would be 4, not 2.
        assert len(turns_after_t1) == 2, (
            f"Expected exactly 2 turns after turn 1 (1 user + 1 assistant), "
            f"got {len(turns_after_t1)} — likely double-logging bug.\n"
            f"Turns: {[t.content for t in turns_after_t1]}"
        )

    # ── 3. Set up second turn, asserting memory_context flows through ────────
    with patch.object(runtime.coordinator, "coordinate",
                      return_value=_make_coord_result("open notepad")), \
         patch.object(runtime.nlu_engine, "process",
                      return_value=MagicMock(normalized_text="open notepad")), \
         patch.object(runtime, "_resolve_expert_domains", return_value=[]), \
         patch.object(runtime.reference_resolver, "resolve_references",
                      return_value=("open notepad", {"resolved": True, "target": "notepad"})) as mock_resolve2:

        await runtime.execute_goal("what about notepad")

        assert mock_resolve2.call_count == 1, "ReferenceResolver not called on turn 2"

        # Inspect the context dict passed to resolve_references on turn 2
        call_args = mock_resolve2.call_args[0]
        passed_goal = call_args[0]
        passed_ctx = call_args[1]

        assert passed_goal == "what about notepad"
        assert "open calculator" in passed_ctx.get("memory_context", ""), (
            f"'open calculator' missing from memory_context on turn 2.\n"
            f"Got: {passed_ctx.get('memory_context', '')!r}"
        )

    assert len(runtime.memory_manager.short_term.turns) >= 2
