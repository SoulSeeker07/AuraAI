import time
import pytest
from unittest.mock import MagicMock, patch
from src.voice.stt_manager import FasterWhisperSTTEngine, LocalAgreementStabilizer
from src.voice.models import STTSettings

@pytest.fixture
def stt_engine():
    settings = STTSettings(model_size="tiny", language="en", sample_rate=16000)
    engine = FasterWhisperSTTEngine(settings)
    # Mock WhisperModel to avoid actual loading during tests
    with patch("faster_whisper.WhisperModel", autospec=True):
        engine.initialize()
    return engine

def test_stt_race_condition(stt_engine):
    """
    Test that a straggler partial task from a previous utterance
    does not corrupt the stabilizer state of the new utterance.
    """
    # We will mock the whisper model's transcribe method to sleep, 
    # simulating a slow transcribe, and then return fake data.
    class FakeWord:
        def __init__(self, word):
            self.word = word
            self.start = 0.0
            self.end = 1.0
            
    class FakeSegment:
        def __init__(self):
            self.words = [FakeWord("hello")]
            
    def mock_transcribe(*args, **kwargs):
        time.sleep(0.5)
        return [FakeSegment()], None

    stt_engine.model = MagicMock()
    stt_engine.model.transcribe = mock_transcribe
    
    # Spy on stabilizer update
    stt_engine._stabilizer = MagicMock(spec=LocalAgreementStabilizer)
    stt_engine._stabilizer.confirmed_audio_offset_s = 0.0
    
    # Mock _emit_partial so it doesn't crash if called
    stt_engine._emit_partial = MagicMock()

    # 1. Start processing a chunk (submits task to executor)
    stt_engine.process_chunk(bytes(3200)) # 100ms
    
    # 2. Immediately reset engine (increments utterance_id) before executor task finishes
    stt_engine.reset()
    
    # 3. Wait for the executor task to finish
    stt_engine._partial_executor.shutdown(wait=True)
    
    # Assert that stabilizer.update() was NEVER called because the utterance_id check blocked it
    stt_engine._stabilizer.update.assert_not_called()

def test_stt_max_window_cap(stt_engine):
    """
    Test that the sliding window correctly caps at _max_window_s even if
    the stabilizer never confirms any audio.
    """
    stt_engine._max_window_s = 2.0 # Use a small cap for fast testing
    stt_engine._partial_interval_s = 0.0 # Bypass time throttle
    
    # Mock stabilizer to simulate 0% agreement (worst-case audio)
    stt_engine._stabilizer = MagicMock()
    stt_engine._stabilizer.confirmed_audio_offset_s = 0.0
    
    # Mock executor to just ignore partial tasks to keep test fast
    stt_engine._partial_executor.submit = MagicMock()
    
    # Mock the in_flight lock so it doesn't block subsequent chunks
    stt_engine._partial_in_flight = MagicMock()
    stt_engine._partial_in_flight.acquire.return_value = True
    
    # Feed 5 seconds of audio in 100ms chunks
    for i in range(50):
        stt_engine.process_chunk(bytes(3200))
    
    # Calculate expected window start
    buffer_duration_s = 5.0
    expected_window_start = buffer_duration_s - stt_engine._max_window_s
    
    # Call process_chunk one last time and see where it slices
    # We will patch it or just check the math inside process_chunk by observing what it submits
    stt_engine.process_chunk(bytes(3200))
    
    # The last submitted task should have window_start_s == (5.1 - 2.0) = 3.1
    # Check the call args of submit
    call_args = stt_engine._partial_executor.submit.call_args[0]
    # signature: submit(_run_partial_transcribe, snapshot, window_start_s, utterance_id)
    submitted_window_start_s = call_args[2]
    
    # Should be exactly 3.1
    assert abs(submitted_window_start_s - 3.1) < 0.001
