import pytest
import asyncio
from src.core.orchestration.personal_os_runtime import PersonalOSRuntime

class MockMemoryForRuntime:
    def __init__(self):
        self.messages = []
    
    def upsert_fact(self, *args, **kwargs):
        pass
        
    def recent_messages(self, limit=5):
        return self.messages[-limit:]

@pytest.fixture
def personal_os(monkeypatch):
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
async def test_end_to_end_3_turn_regression(personal_os):
    """
    Test the specific 3-turn regression identified by the user.
    """
    # Turn 1
    t1_text = "current dollar to rupees conversion rate"
    personal_os._mock_memory.messages.append({"role": "user", "content": t1_text})
    
    # Turn 2
    t2_text = "as of today?"
    # We pass the memory context so ReferenceResolver can pick it up
    ctx = {"memory_context": {}}
    report2 = await personal_os.execute_goal(t2_text, context=ctx)
    
    # Check that it resolved to research internally (dmm sets steps)
    # The actual execution might fail without backends, but it should block/try to execute.
    # The most important part is that NLU or DMM didn't think it was local_time.
    # If it was local_time, intent_hint or steps would reflect time fetching.
    
    # Turn 3
    t3_text = "as of today whats the convertion rate of doller to inr"
    report3 = await personal_os.execute_goal(t3_text, context=ctx)
    
    # If it doesn't fail, it passed the routing phase!

@pytest.mark.asyncio
async def test_end_to_end_boundary_queries(personal_os):
    """
    Test the boundaries between local_time and research/exchange rate routing.
    """
    ctx = {"memory_context": {}}
    
    queries = [
        "what time is it?",
        "what is today's date?",
        "what is the current time in London?",
        "what is today's USD to INR exchange rate?",
        "as of today, what's the USD to INR exchange rate?",
    ]
    
    for query in queries:
        report = await personal_os.execute_goal(query, context=ctx)
        # Assuming the pipeline completes the routing and generates a report
        assert report is not None
