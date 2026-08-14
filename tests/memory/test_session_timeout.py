import time
from unittest.mock import Mock, patch
import pytest

from memory.manager.short_term_memory import ShortTermMemory

def test_session_timeout_behavior():
    # Setup
    stm = ShortTermMemory(session_timeout=300) # 5 mins
    
    # Fast forward 6 minutes but mock time so assistant replies late
    with patch('time.time') as mock_time:
        # Start at t=0
        mock_time.return_value = 0.0
        stm.add_user_turn("what about notepad")
        assert len(stm.get_raw_turns()) == 1
        assert stm.last_activity == 0.0
        
        # Assistant replies 6 minutes later (e.g. slow execution)
        mock_time.return_value = 360.0
        stm.add_assistant_turn("I opened notepad for you.")
        
        # Assistant turn updates last_activity but does NOT clear the session!
        assert stm.last_activity == 360.0
        assert len(stm.get_raw_turns()) == 2
        
        # Now 6 MORE minutes pass (t=720) without user activity
        mock_time.return_value = 720.0
        
        # User finally replies
        stm.add_user_turn("what were we talking about?")
        
        # Session SHOULD wipe here because (720 - 360) > 300
        # The buffer should only have the new turn now.
        turns = stm.get_raw_turns()
        assert len(turns) == 1
        assert turns[0].content == "what were we talking about?"
