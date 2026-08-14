import pytest
import asyncio
from src.core.orchestration.personal_os_runtime import PersonalOSRuntime
from src.brain.aca.engine_interface import EngineRegistry
from src.core.orchestration.reference_resolver import ReferenceResolver

class MockMemoryForRuntime:
    def __init__(self):
        self.messages = []
    
    def upsert_fact(self, *args, **kwargs):
        pass
        
    def recent_messages(self, limit=5):
        return self.messages[-limit:]

@pytest.fixture
def personal_os_runtime(monkeypatch):
    # Ensure PersonalOSRuntime doesn't start infinite loops in test
    runtime = PersonalOSRuntime.get_instance()
    
    # Mock memory for ReferenceResolver context
    mem = MockMemoryForRuntime()
    import Memory
    monkeypatch.setattr(Memory, "Memory", lambda *args, **kwargs: mem)
    
    # Provide access to the mock memory to modify it during tests
    runtime._mock_memory = mem
    return runtime

@pytest.mark.asyncio
async def test_end_to_end_3_turn_regression(personal_os_runtime):
    """
    Test the specific 3-turn regression identified by the user:
    Turn 1: current dollar to rupees conversion rate
    Turn 2: as of today?
    Turn 3: as of today whats the convertion rate of doller to inr
    """
    # Turn 1
    t1_text = "current dollar to rupees conversion rate"
    personal_os_runtime._mock_memory.messages.append({"role": "user", "content": t1_text})
    
    # Since PersonalOSRuntime currently skips direct intent generation in this stub,
    # we just want to ensure it passes through the pipeline cleanly and the resolver works.
    resolved_1, meta_1 = ReferenceResolver.resolve_references(t1_text, context={"memory_context": {}})
    
    # Turn 2
    t2_text = "as of today?"
    resolved_2, meta_2 = ReferenceResolver.resolve_references(t2_text, context={"memory_context": {}})
    
    assert meta_2["resolved"] is True
    # The 'current' word is stripped to prevent semantic conflict with 'today'
    assert "dollar to rupees conversion rate as of today" in resolved_2
    
    # Turn 3
    t3_text = "as of today whats the convertion rate of doller to inr"
    nlu_res = personal_os_runtime.nlu_engine.process(t3_text)
    
    # Normalization check
    assert "conversion" in nlu_res.normalized_text.lower()
    assert "dollar" in nlu_res.normalized_text.lower()

@pytest.mark.asyncio
async def test_end_to_end_boundary_queries(personal_os_runtime):
    """
    Test the boundaries between local_time and research/exchange rate routing.
    """
    from src.brain.intent_router import IntentRouter
    router = IntentRouter(personal_os_runtime._mock_memory)
    
    queries = [
        ("what time is it?", "local_time"),
        ("what is today's date?", "local_time"),
        ("what is the current time in London?", "local_time"),
        ("what is today's USD to INR exchange rate?", "research"), # research via ResearchDecision or web_search
        ("as of today, what's the USD to INR exchange rate?", "research"),
    ]
    
    for query, expected_intent in queries:
        # We test intent routing first
        intent = router.detect(query)
        
        if expected_intent == "local_time":
            assert intent.name == "local_time", f"Expected local_time for '{query}', got '{intent.name}'"
        else:
            # If it's research, it shouldn't be local_time
            assert intent.name != "local_time", f"Expected NOT local_time for '{query}'"
            
            # Check DecisionEngine
            from src.core.orchestration.decision_engine import DecisionEngine
            engine = DecisionEngine()
            out = engine.evaluate(query)
            assert out.intent_type.value == "research", f"Expected research for '{query}' from DecisionEngine"
