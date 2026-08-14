import time
import pytest
from memory.manager.short_term_memory import ShortTermMemory


def test_add_turns_no_expiry():
    stm = ShortTermMemory(max_turns=12, session_timeout=300)
    stm.add_user_turn("Hello")
    stm.add_assistant_turn("Hi there")
    assert len(stm.turns) == 2
    assert stm.turns[0].role == "user"
    assert stm.turns[1].role == "assistant"


def test_session_expiry_on_user_turn():
    stm = ShortTermMemory(max_turns=12, session_timeout=0.1)
    stm.add_user_turn("Hello")
    time.sleep(0.2)  # Wait for session timeout
    stm.add_user_turn("Are you there?")
    assert len(stm.turns) == 1
    assert stm.turns[0].content == "Are you there?"


def test_long_execution_gap():
    """
    Simulates a gap longer than session_timeout occurring between 
    add_user_turn and add_assistant_turn. Asserts that the session survives.
    """
    stm = ShortTermMemory(max_turns=12, session_timeout=0.1)
    
    # User asks something
    stm.add_user_turn("Run a long task")
    assert len(stm.turns) == 1
    
    # Task takes a long time (longer than timeout)
    time.sleep(0.2)
    
    # Assistant finally replies
    stm.add_assistant_turn("Task completed")
    
    # Session should NOT have expired because add_assistant_turn does not check expiry
    assert len(stm.turns) == 2
    assert stm.turns[0].content == "Run a long task"
    assert stm.turns[1].content == "Task completed"
    
    # Immediately after, user replies
    stm.add_user_turn("Great!")
    
    # Because add_assistant_turn updated last_activity, the session should STILL not expire
    assert len(stm.turns) == 3
    assert stm.turns[2].content == "Great!"


def test_compact_overflow():
    stm = ShortTermMemory(max_turns=2, session_timeout=300)
    stm.add_user_turn("Turn 1")
    stm.add_assistant_turn("Turn 2")
    stm.add_user_turn("Turn 3")
    assert len(stm.turns) == 2
    assert stm.turns[0].content == "Turn 2"
    assert stm.turns[1].content == "Turn 3"
    
    overflow = stm.pop_pending_summary_input()
    assert len(overflow) == 1
    assert overflow[0].content == "Turn 1"
