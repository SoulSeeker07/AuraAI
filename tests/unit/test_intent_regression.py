import pytest
from core.nlu.nlu_engine import NLUEngine
from brain.intent_router import IntentRouter
from core.orchestration.decision_engine import DecisionEngine
from core.orchestration.reference_resolver import ReferenceResolver

class MockMemory:
    def __init__(self):
        self.messages = []
    def extract_facts(self, *args, **kwargs):
        return []
    def get_context(self):
        return ""
    def upsert_fact(self, *args, **kwargs):
        pass
    def recent_messages(self, limit=5):
        return self.messages[-limit:]

def test_intent_router_date_time():
    memory = MockMemory()
    router = IntentRouter(memory)
    
    # 1. "what time is it today?" -> date/time
    intent = router.detect("what time is it today?")
    assert intent.name == "local_time"
    
    # 2. "what is today's date?" -> date/time
    intent = router.detect("what is today's date?")
    assert intent.name == "local_time"
    
    # 3. "what's today's USD to INR rate?" -> NOT date/time
    intent = router.detect("what's today's USD to INR rate?")
    assert intent.name != "local_time"
    
    # 4. "as of today, what's the USD to INR rate?" -> NOT date/time
    intent = router.detect("as of today, what's the USD to INR rate?")
    assert intent.name != "local_time"

def test_nlu_engine_typo_normalization():
    nlu = NLUEngine()
    
    res = nlu.process("what is the covertion rate of doller to inr")
    assert "conversion" in res.normalized_text.lower()
    assert "dollar" in res.normalized_text.lower()
    assert "covertion" not in res.normalized_text.lower()
    assert "doller" not in res.normalized_text.lower()
    
def test_decision_engine_research_routing():
    engine = DecisionEngine()
    
    # "what's today's USD to INR rate?" -> research
    out = engine.evaluate("what's today's USD to INR rate?")
    assert out.intent_type.value == "research"
    assert out.should_search_first == True
    
    # "what does exchange rate mean?" -> chat (not research)
    out = engine.evaluate("what does exchange rate mean?")
    assert out.intent_type.value != "research"
    
def test_three_turn_regression(monkeypatch):
    # Turn 1
    t1_text = "current dollar to rupees conversion rate"
    
    # Turn 2
    t2_text = "as of today?"
    
    # Setup mock memory for reference resolver
    class TestMemory:
        def __init__(self, *args, **kwargs):
            pass
        def recent_messages(self, limit=5):
            return [{"role": "user", "content": t1_text}]
            
    # Mock Memory.Memory
    import Memory
    monkeypatch.setattr(Memory, "Memory", TestMemory)
    
    resolved_text, meta = ReferenceResolver.resolve_references(t2_text, context={"memory_context": {}})
    
    assert meta["resolved"] is True
    # The 'current' word is stripped to prevent conflict with 'today'
    assert "dollar to rupees conversion rate as of today" in resolved_text
    
    # Verify the resolved text routes correctly
    memory = MockMemory()
    router = IntentRouter(memory)
    intent = router.detect(resolved_text)
    
    # The intent should NOT be local_time because it has conversion rate in it.
    assert intent.name != "local_time"
    
    engine = DecisionEngine()
    out = engine.evaluate(resolved_text)
    assert out.intent_type.value == "research"
