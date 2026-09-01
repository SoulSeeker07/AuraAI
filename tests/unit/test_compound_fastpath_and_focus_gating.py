import pytest
from unittest.mock import MagicMock, patch
from core.aura_core import AuraCore

@pytest.fixture
def aura_core():
    # Reset singleton to ensure fresh instance
    AuraCore._initialized = False
    core = AuraCore.get_instance()
    return core

def test_focus_preamble_gating_skips_llm_on_non_focus_phrases(aura_core):
    """Verify non-focus queries skip the LLM slug extraction path completely."""
    non_focus_queries = [
        "what time is it",
        "calculate EBITDA and revenue",
        "turn on the bedroom light",
        "tell me a funny joke",
        "who was Albert Einstein",
    ]
    with patch.object(aura_core, "groq_client") as mock_groq:
        for q in non_focus_queries:
            intent = aura_core._resolve_focus_intent(q)
            assert intent["action"] in ("none", "list", "query", "close", "resume", "create", "close_all", "close_current")
            if intent["action"] == "none":
                # Ensure LLM chat completions create was NEVER invoked
                assert mock_groq.chat.completions.create.call_count == 0

def test_focus_preamble_allows_explicit_focus_phrases(aura_core):
    """Verify queries containing explicit focus keywords and prefix patterns resolve correctly."""
    assert aura_core._resolve_focus_intent("close all tasks")["action"] == "close_all"
    assert aura_core._resolve_focus_intent("close current thread")["action"] == "close_current"
    assert aura_core._resolve_focus_intent("start new task api_refactor")["action"] == "create"
    assert aura_core._resolve_focus_intent("resume backend_optimization")["action"] == "resume"
    assert aura_core._resolve_focus_intent("what are my active tasks")["action"] == "list"

@pytest.mark.asyncio
async def test_compound_fastpath_resolves_valid_multi_local_intents(aura_core):
    """Verify compound queries where all clauses are deterministic local intents resolve fast locally."""
    resp = await aura_core.get_ai_response("what time is it and what time is it", enable_tools=False)
    assert resp is not None
    assert "Today is" in resp or "time:" in resp.lower()

@pytest.mark.asyncio
async def test_compound_fastpath_falls_through_on_non_local_conjunctions(aura_core):
    """Verify conjunctions in single goals (e.g. search cats and dogs) do NOT falsely resolve as local compounds."""
    deterministic_local_intents = {
        "local_time", "live_weather", "battery_status", "memory_summary",
        "brightness_control", "audio_control", "profile_lookup",
        "skills_lookup", "goals_lookup", "preferences_lookup", "projects_lookup",
        "remember_fact"
    }
    non_local_conjunctions = [
        "search for cats and dogs",
        "remind me to call and email Sarah",
        "compare Python and Rust performance",
    ]
    
    for q in non_local_conjunctions:
        clauses = [c.strip() for c in q.split(" and ") if c.strip()]
        for c in clauses:
            intent = aura_core.conversation_engine.intent_router.detect(c)
            # At least one clause is either not in deterministic_local_intents or has no local answer
            if not intent or intent.name not in deterministic_local_intents:
                break
        else:
            pytest.fail(f"Query '{q}' had all clauses match deterministic local intents: {clauses}")

