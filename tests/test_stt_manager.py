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
    
    stt_engine.process_chunk(bytes(3200))
    
    call_args = stt_engine._partial_executor.submit.call_args[0]
    submitted_window_start_s = call_args[2]
    
    # Should be exactly 3.1
    assert abs(submitted_window_start_s - 3.1) < 0.001


def test_google_stt_circuit_breaker_tripping_and_recovery():
    """Verify GoogleSTTEngine circuit breaker trips on consecutive RequestError failures and recovers."""
    import speech_recognition as sr
    from src.voice.stt_manager import GoogleSTTEngine, CircuitBreakerState

    settings = STTSettings(language="en-in", sample_rate=16000)
    engine = GoogleSTTEngine(settings)

    with patch("faster_whisper.WhisperModel", autospec=True):
        engine.initialize()

    # Mock recognizer to raise RequestError (network failure)
    engine.recognizer.recognize_google = MagicMock(side_effect=sr.RequestError("Network unreachable"))
    engine._fallback_engine.finalize = MagicMock(return_value="fallback command")

    # Generate synthetic speech audio (1 sec of 16kHz sine wave)
    import numpy as np
    t = np.linspace(0, 1.0, 16000, False)
    tone = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()

    # Turn 1: failure 1
    engine.process_chunk(tone)
    res1 = engine.finalize()
    assert res1 == "fallback command"
    assert engine._consecutive_failures == 1
    assert engine._circuit_state == CircuitBreakerState.CLOSED

    # Turn 2: failure 2
    engine.reset()
    engine.process_chunk(tone)
    res2 = engine.finalize()
    assert res2 == "fallback command"
    assert engine._consecutive_failures == 2
    assert engine._circuit_state == CircuitBreakerState.CLOSED

    # Turn 3: failure 3 -> Trips circuit breaker to OPEN
    engine.reset()
    engine.process_chunk(tone)
    res3 = engine.finalize()
    assert res3 == "fallback command"
    assert engine._consecutive_failures == 3
    assert engine._circuit_state == CircuitBreakerState.OPEN

    # Turn 4: while OPEN, recognize_google is NEVER called (0ms fast fallback bypass)
    engine.recognizer.recognize_google.reset_mock()
    engine.reset()
    engine.process_chunk(tone)
    res4 = engine.finalize()
    assert res4 == "fallback command"
    engine.recognizer.recognize_google.assert_not_called()

    # Turn 5: Simulate cooldown expiry -> probes in HALF_OPEN, succeeds, circuit CLOSES
    engine._last_failure_time = time.time() - 65.0  # 65s ago
    engine.recognizer.recognize_google.side_effect = None
    engine.recognizer.recognize_google.return_value = "online command recovered"

    engine.reset()
    engine.process_chunk(tone)
    res5 = engine.finalize()
    assert res5 == "online command recovered"
    assert engine._circuit_state == CircuitBreakerState.CLOSED
    assert engine._consecutive_failures == 0


def test_google_stt_unexpected_exception_does_not_trip_breaker():
    """Verify non-network exceptions (TypeError, bug) do NOT trip the circuit breaker."""
    from src.voice.stt_manager import GoogleSTTEngine, CircuitBreakerState

    settings = STTSettings(language="en-in", sample_rate=16000)
    engine = GoogleSTTEngine(settings)

    with patch("faster_whisper.WhisperModel", autospec=True):
        engine.initialize()

    # Raise non-network bug
    engine.recognizer.recognize_google = MagicMock(side_effect=TypeError("Unexpected refactor error"))
    engine._fallback_engine.finalize = MagicMock(return_value="fallback command")

    import numpy as np
    t = np.linspace(0, 1.0, 16000, False)
    tone = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()

    for _ in range(5):
        engine.reset()
        engine.process_chunk(tone)
        engine.finalize()

    # Breaker must NOT trip for non-network errors
    assert engine._consecutive_failures == 0
    assert engine._circuit_state == CircuitBreakerState.CLOSED


def test_google_stt_circuit_breaker_concurrent_hammering():
    """Verify circuit breaker thread-safety when multiple threads hammer finalize concurrently."""
    import speech_recognition as sr
    from concurrent.futures import ThreadPoolExecutor
    from src.voice.stt_manager import GoogleSTTEngine, CircuitBreakerState

    settings = STTSettings(language="en-in", sample_rate=16000)
    engine = GoogleSTTEngine(settings)

    with patch("faster_whisper.WhisperModel", autospec=True):
        engine.initialize()

    engine.recognizer.recognize_google = MagicMock(side_effect=sr.RequestError("Concurrent timeout"))
    engine._fallback_engine.finalize = MagicMock(return_value="fallback")

    import numpy as np
    t = np.linspace(0, 1.0, 16000, False)
    tone = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()

    def run_turn():
        engine.process_chunk(tone)
        return engine.finalize()

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(run_turn) for _ in range(10)]
        results = [f.result() for f in futures]

    assert all(r == "fallback" for r in results)
    # The circuit must have cleanly tripped to OPEN without race condition lockups
    assert engine._circuit_state == CircuitBreakerState.OPEN
    assert engine._consecutive_failures >= 3


def test_hybrid_streaming_partials_forwarding():
    """Verify GoogleSTTEngine only forwards streaming chunks when hybrid mode is enabled."""
    from src.voice.stt_manager import GoogleSTTEngine

    settings = STTSettings(language="en-in", sample_rate=16000)
    engine = GoogleSTTEngine(settings)

    with patch("faster_whisper.WhisperModel", autospec=True):
        engine.initialize()

    engine._fallback_engine.process_chunk = MagicMock()

    chunk = bytes(3200)

    # 1. Default (hybrid disabled) -> zero CPU overhead, does not forward
    engine.enable_hybrid_partials = False
    engine.process_chunk(chunk)
    engine._fallback_engine.process_chunk.assert_not_called()

    # 2. Hybrid enabled -> forwards for real-time live captions
    engine.enable_hybrid_partials = True
    engine.process_chunk(chunk)
    engine._fallback_engine.process_chunk.assert_called_once_with(chunk)


def test_polymorphic_load_buffer():
    """Verify polymorphic load_buffer properly populates audio buffers across engines."""
    settings = STTSettings(model_size="tiny", language="en", sample_rate=16000)
    engine = FasterWhisperSTTEngine(settings)

    chunks = [bytes(1600), bytes(3200), bytes(1600)]
    engine.load_buffer(chunks, duration=0.2)

    assert len(engine._audio_buffer) == 3
    assert engine._total_duration == 0.2
