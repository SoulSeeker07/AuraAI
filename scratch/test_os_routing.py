import asyncio
import sys
sys.path.insert(0, "D:/Sreekanta/VS Code Project/Desktop AI/AuraAI")

from src.core.orchestration.personal_os_runtime import PersonalOSRuntime
from src.core.orchestration.reference_resolver import ReferenceResolver
import Memory

class MockMemoryForRuntime:
    def __init__(self):
        self.messages = []
    
    def upsert_fact(self, *args, **kwargs):
        pass
        
    def recent_messages(self, limit=5):
        return self.messages[-limit:]

async def main():
    # Patch memory for reference resolver
    mem = MockMemoryForRuntime()
    Memory.Memory = lambda *args, **kwargs: mem
    
    os_runtime = PersonalOSRuntime.get_instance()
    os_runtime._mock_memory = mem
    
    print("=== TURN 1 ===")
    t1 = "current dollar to rupees conversion rate"
    mem.messages.append({"role": "user", "content": t1})
    
    # 1. NLU & Contextual Follow-Up Resolution (G3)
    resolved_1, meta_1 = os_runtime.reference_resolver.resolve_references(t1, {"memory_context": {}})
    nlu_1 = os_runtime.nlu_engine.process(resolved_1, {})
    dmm_1 = os_runtime.dmm.analyze(nlu_1.normalized_text, {})
    
    print(f"Goal: {t1}")
    print(f"Resolved: {resolved_1}")
    print(f"NLU Intent: {nlu_1.intent_hint}")
    print(f"NLU Normalized: {nlu_1.normalized_text}")
    print(f"DMM Steps: {dmm_1.execution_plan if hasattr(dmm_1, 'execution_plan') else dmm_1}")
    
    print("\n=== TURN 2 ===")
    t2 = "as of today?"
    
    resolved_2, meta_2 = os_runtime.reference_resolver.resolve_references(t2, {"memory_context": {}})
    nlu_2 = os_runtime.nlu_engine.process(resolved_2, {})
    dmm_2 = os_runtime.dmm.analyze(nlu_2.normalized_text, {})
    
    print(f"Goal: {t2}")
    print(f"Resolved: {resolved_2}")
    print(f"NLU Intent: {nlu_2.intent_hint}")
    print(f"NLU Normalized: {nlu_2.normalized_text}")
    print(f"DMM Steps: {dmm_2.execution_plan if hasattr(dmm_2, 'execution_plan') else dmm_2}")
    
    print("\n=== TURN 3 ===")
    t3 = "as of today whats the convertion rate of doller to inr"
    
    resolved_3, meta_3 = os_runtime.reference_resolver.resolve_references(t3, {"memory_context": {}})
    nlu_3 = os_runtime.nlu_engine.process(resolved_3, {})
    dmm_3 = os_runtime.dmm.analyze(nlu_3.normalized_text, {})
    
    print(f"Goal: {t3}")
    print(f"Resolved: {resolved_3}")
    print(f"NLU Intent: {nlu_3.intent_hint}")
    print(f"NLU Normalized: {nlu_3.normalized_text}")
    print(f"DMM Steps: {dmm_3.execution_plan if hasattr(dmm_3, 'execution_plan') else dmm_3}")
    
    print("\n=== BOUNDARY TESTS ===")
    boundaries = [
        "what time is it?",
        "what is today's date?",
        "what is the current time in London?",
        "what is today's USD to INR exchange rate?",
        "as of today, what's the USD to INR exchange rate?",
    ]
    
    for q in boundaries:
        resolved, _ = os_runtime.reference_resolver.resolve_references(q, {"memory_context": {}})
        nlu = os_runtime.nlu_engine.process(resolved, {})
        dmm = os_runtime.dmm.analyze(resolved, {})
        
        # Determine intent by looking at the steps / NLU
        print(f"Goal: {q}")
        print(f"NLU Intent: {nlu.intent_hint}")
        print(f"DMM Steps: {dmm.execution_plan if hasattr(dmm, 'execution_plan') else dmm}")
        print("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())
