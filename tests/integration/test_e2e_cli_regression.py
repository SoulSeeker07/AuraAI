import pytest
from core.nlu.nlu_engine import NLUEngine
from core.orchestration.reference_resolver import ReferenceResolver
from Memory import Memory


@pytest.fixture
def test_memory_instance(tmp_path):
    db_path = tmp_path / "test_memory.db"
    chat_log = tmp_path / "ChatLog.json"
    return Memory(db_path=str(db_path), chat_log_path=str(chat_log))


@pytest.mark.asyncio
async def test_end_to_end_3_turn_regression(test_memory_instance, monkeypatch):
    """
    Test the specific 3-turn regression identified by the user:
    Turn 1: current dollar to rupees conversion rate
    Turn 2: as of today?
    Turn 3: as of today whats the convertion rate of doller to inr
    """
    nlu_engine = NLUEngine()

    # Turn 1
    t1_text = "current dollar to rupees conversion rate"
    test_memory_instance.add_message("user", t1_text)

    # Monkeypatch Memory instantiation in ReferenceResolver to use test_memory_instance
    import Memory as MemModule
    monkeypatch.setattr(MemModule, "Memory", lambda *args, **kwargs: test_memory_instance)

    resolved_1, meta_1 = ReferenceResolver.resolve_references(t1_text, context={"world_state": {}})

    # Turn 2: resolves against conversational memory
    t2_text = "as of today?"
    resolved_2, meta_2 = ReferenceResolver.resolve_references(t2_text, context={"world_state": {}})

    assert meta_2["resolved"] is True
    # The 'current' word is stripped to prevent semantic conflict with 'today'
    assert "dollar to rupees conversion rate as of today" in resolved_2

    # Turn 3
    t3_text = "as of today whats the convertion rate of doller to inr"
    nlu_res = nlu_engine.process(t3_text)

    # Normalization check
    assert "conversion" in nlu_res.normalized_text.lower()
    assert "dollar" in nlu_res.normalized_text.lower()


@pytest.mark.asyncio
async def test_end_to_end_boundary_queries(test_memory_instance):
    """
    Test the boundaries between local_time and research/exchange rate routing.
    """
    from brain.intent_router import IntentRouter
    router = IntentRouter(test_memory_instance)

    queries = [
        ("what time is it?", "local_time"),
        ("what is today's date?", "local_time"),
        ("what is the current time in London?", "local_time"),
        ("what is today's USD to INR exchange rate?", "research"),
        ("as of today, what's the USD to INR exchange rate?", "research"),
    ]

    for query, expected_intent in queries:
        intent = router.detect(query)

        if expected_intent == "local_time":
            assert intent.name == "local_time", f"Expected local_time for '{query}', got '{intent.name}'"
        else:
            assert intent.name != "local_time", f"Expected NOT local_time for '{query}'"

            from core.orchestration.decision_engine import DecisionEngine
            engine = DecisionEngine()
            out = engine.evaluate(query)
            assert out.intent_type.value == "research", f"Expected research for '{query}' from DecisionEngine"
