from src.core.aura_core import AuraCore

def test_auracore_max_history_attribute_and_truncation():
    core = AuraCore()
    assert hasattr(core, 'max_history')
    assert isinstance(core.max_history, int)
    assert core.max_history > 0

    core.clear_conversation_history()
    assert len(core.get_conversation_history()) == 0

    original_max = core.max_history
    try:
        core.max_history = 5
        for i in range(10):
            core.add_to_conversation('user' if i % 2 == 0 else 'assistant', f'Message {i}')

        history = core.get_conversation_history()
        assert len(history) == 5
        assert history[-1]['content'] == 'Message 9'
        assert history[0]['content'] == 'Message 5'
    finally:
        core.max_history = original_max
