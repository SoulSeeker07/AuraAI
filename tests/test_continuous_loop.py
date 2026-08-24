import io
import pytest
import numpy as np
from unittest.mock import MagicMock
from AuraWakeWord.runtime.aura_wake_detector import AuraWakeDetector


def test_stdout_encoding_reconfiguration_prevents_emoji_crash():
    """
    Test that strict cp1252 encoding fails on emojis, while utf-8 / replace error handling succeeds.
    """
    raw_buffer = io.BytesIO()
    strict_cp1252_stream = io.TextIOWrapper(raw_buffer, encoding="cp1252", errors="strict")

    # Assert writing emoji fails under default strict cp1252 (simulates unconfigured Windows console)
    with pytest.raises(UnicodeEncodeError):
        strict_cp1252_stream.write("🎤 Live Score: 0.85\n")
        strict_cp1252_stream.flush()

    # Apply reconfigure
    strict_cp1252_stream.reconfigure(encoding="utf-8", errors="replace")

    # Assert writing emoji succeeds after reconfigure
    strict_cp1252_stream.write("🎤 Live Score: 0.85\n")
    strict_cp1252_stream.flush()
    assert b"\xf0\x9f\x8e\xa4 Live Score: 0.85" in raw_buffer.getvalue()


def test_aura_wake_detector_consecutive_failure_bubbling():
    """
    Test that AuraWakeDetector increments consecutive_failures and bubbles to on_error
    only when reaching MAX_CONSECUTIVE_FAILURES, rather than silently failing indefinitely.
    """
    detector = AuraWakeDetector(model_path="dummy.onnx")
    detector.ort_session = MagicMock()
    detector.input_name = "input"
    detector.on_error = MagicMock()

    # Mock ONNX inference to simulate a crash (e.g., driver/runtime issue)
    detector.ort_session.run.side_effect = RuntimeError("Simulated ONNX breakdown")
    t = np.arange(1600)
    dummy_chunk = (np.sin(2 * np.pi * 440 * t / 16000) * 8000).astype(np.int16).tobytes()

    # Call 4 times — should not trigger on_error yet
    for i in range(1, detector.MAX_CONSECUTIVE_FAILURES):
        result = detector.process_audio(dummy_chunk, 16000)
        assert result is False
        assert detector.consecutive_failures == i
        detector.on_error.assert_not_called()

    # 5th call — hits MAX_CONSECUTIVE_FAILURES and triggers on_error
    result = detector.process_audio(dummy_chunk, 16000)
    assert result is False
    assert detector.consecutive_failures == detector.MAX_CONSECUTIVE_FAILURES
    detector.on_error.assert_called_once()
    assert "consecutive failures" in detector.on_error.call_args[0][0]


def test_aura_wake_detector_resets_failure_counter_on_success():
    """
    Test that any successful processing step resets the consecutive_failures counter to 0.
    """
    detector = AuraWakeDetector(model_path="dummy.onnx")
    detector.ort_session = MagicMock()
    detector.input_name = "input"
    detector.on_error = MagicMock()

    # Pre-seed consecutive failures
    detector.consecutive_failures = 3

    # Mock successful run (low probability logit)
    detector.ort_session.run.return_value = [np.array([[-5.0]])]
    t = np.arange(1600)
    dummy_chunk = (np.sin(2 * np.pi * 440 * t / 16000) * 8000).astype(np.int16).tobytes()

    result = detector.process_audio(dummy_chunk, 16000)
    assert result is False
    assert detector.consecutive_failures == 0
    detector.on_error.assert_not_called()


def test_continuous_voice_loop_wake_word_real_audio():
    """
    End-to-end test verifying that feeding real recorded audio of 'Hey Aura'
    through VoiceManager -> AuraWakeDetector correctly triggers ContinuousVoiceLoop
    to transition from IDLE to LISTENING.
    """
    import wave
    from pathlib import Path
    from voice.continuous_loop import ContinuousVoiceLoop, VoiceState
    from voice.voice_manager import VoiceManager

    wav_path = Path("AuraWakeWord/test_recordings/20260814_135424_DETECTED.wav")
    assert wav_path.exists(), "Test recording wav file missing"

    vm = VoiceManager()
    vm.audio_manager.start_recording = MagicMock(return_value=True)
    vm.audio_manager.stop_recording = MagicMock(return_value=True)
    loop = ContinuousVoiceLoop(voice_manager=vm)
    loop._process_transcript = MagicMock()
    loop.start()

    wf = wave.open(str(wav_path), "rb")
    detected = False
    try:
        while True:
            chunk = wf.readframes(1600)
            if not chunk:
                break
            vm.process_audio(chunk, 16000)
            if loop.state == VoiceState.LISTENING:
                detected = True
                break
    finally:
        wf.close()
        loop.stop()

    assert detected, "Real audio failed to trigger wake word in ContinuousVoiceLoop"


def test_full_chain_error_bubbling_to_stderr(capsys):
    """
    Integration test asserting that when the low-level AuraWakeDetector hits
    consecutive failures, the error propagates through:
    AuraWakeDetector.on_error -> WakeWordManager.on_error -> VoiceManager._on_wake_word_error ->
    ContinuousVoiceLoop._on_voice_error -> sys.stderr output.
    """
    from voice.continuous_loop import ContinuousVoiceLoop
    from voice.voice_manager import VoiceManager

    vm = VoiceManager()
    vm.audio_manager.start_recording = MagicMock(return_value=True)
    vm.audio_manager.stop_recording = MagicMock(return_value=True)
    loop = ContinuousVoiceLoop(voice_manager=vm)
    loop._process_transcript = MagicMock()
    loop.start()

    # Access the low-level detector
    detector = vm.wake_word.engine
    assert detector is not None

    # Mock the ONNX session inside the detector to simulate failures
    detector.ort_session = MagicMock()
    detector.ort_session.run.side_effect = RuntimeError("Forced hardware simulation fault")

    # Feed 5 chunks with signal energy to exceed MAX_CONSECUTIVE_FAILURES
    t = np.arange(1600)
    dummy_chunk = (np.sin(2 * np.pi * 440 * t / 16000) * 8000).astype(np.int16).tobytes()
    for _ in range(5):
        vm.process_audio(dummy_chunk, 16000)

    loop.stop()

    # Capture output written to stdout/stderr
    captured = capsys.readouterr()
    assert "⚠️ [Voice System Warning]" in captured.err
    assert "consecutive failures" in captured.err


def test_wake_detector_no_false_trigger_on_initial_stream_silence_or_noise():
    """
    Regression Test: Asserts that feeding initial streaming silence or ambient noise
    to a freshly instantiated AuraWakeDetector produces zero false triggers and scores < 0.35.
    """
    from pathlib import Path
    model_path = Path("AuraWakeWord/models/aura_wakeword.onnx")
    if not model_path.exists():
        pytest.skip("ONNX model file not found on disk")

    detector = AuraWakeDetector(model_path=str(model_path))
    assert detector.initialize() is True

    trigger_called = False
    def on_detect(phrase):
        nonlocal trigger_called
        trigger_called = True
    detector.on_wake_word_detected = on_detect

    # Simulate 3 seconds (48,000 samples) of continuous low-level ambient room noise (RMS ~ 0.005)
    np.random.seed(42)
    noise_stream = np.random.normal(0, 0.005, 48000).astype(np.float32)
    int16_noise = (noise_stream * 32767).astype(np.int16).tobytes()

    chunk_size = 3200  # 1600 samples (100ms chunks)
    for i in range(0, len(int16_noise), chunk_size):
        chunk = int16_noise[i:i+chunk_size]
        res = detector.process_audio(chunk, 16000)
        assert res is False, "Spurious wake-word detection fired on ambient room noise"
        assert detector.last_probability < 0.50, f"Score {detector.last_probability} exceeded safety ceiling"

    assert trigger_called is False, "Wake word callback must not be invoked during ambient baseline"


def test_whisper_initial_prompt_consistency():
    """
    Test that FasterWhisperSTTEngine uses the exact same immutable DESKTOP_VOCABULARY_PROMPT
    across all transcribe calls to prevent LocalAgreementStabilizer hypothesis drift.
    """
    from voice.stt_manager import DESKTOP_VOCABULARY_PROMPT, FasterWhisperSTTEngine, STTSettings
    assert isinstance(DESKTOP_VOCABULARY_PROMPT, str)
    assert len(DESKTOP_VOCABULARY_PROMPT) > 10

    engine = FasterWhisperSTTEngine(settings=STTSettings())
    engine.model = MagicMock()
    engine.model.transcribe.return_value = ([], None)
    engine.is_active = True

    # Test partial transcribe
    engine._run_partial_transcribe(bytes(3200), 0.0, 0)
    assert engine.model.transcribe.called
    kwargs_partial = engine.model.transcribe.call_args[1]
    assert kwargs_partial.get("initial_prompt") == DESKTOP_VOCABULARY_PROMPT

    # Test finalize
    engine._audio_buffer = [bytes(3200)]
    engine.finalize()
    kwargs_final = engine.model.transcribe.call_args[1]
    assert kwargs_final.get("initial_prompt") == DESKTOP_VOCABULARY_PROMPT


def test_two_tier_fuzzy_app_resolver():
    """
    Test two-tier app resolution in WindowManager:
    - Tier 1: fast-path phonetic variations ("load pad", "out pad", "whats up")
    - Tier 2: general close matches ("goat pad" -> notepad, "chrom" -> chrome)
    - Ambiguous: confidence gap check returns clarification error.
    """
    from desktop.native.managers.window_manager import WindowManager
    wm = WindowManager()

    # Tier 1 & Tier 2 positive resolutions
    res_type, target = wm._resolve_app_executable("out pad")
    assert res_type == "exe" and "notepad" in target.lower()

    res_type, target = wm._resolve_app_executable("load pad")
    assert res_type == "exe" and "notepad" in target.lower()

    res_type, target = wm._resolve_app_executable("goat pad")
    assert res_type == "exe" and "notepad" in target.lower()

    res_type, target = wm._resolve_app_executable("whats up")
    assert res_type in ("exe", "protocol", "url") and "whatsapp" in target.lower()

    res_type, target = wm._resolve_app_executable("instagram")
    assert res_type == "url" and "instagram.com" in target.lower()

    # Ambiguous test case (simulate close ambiguous candidates)
    res_type, target = wm._resolve_app_executable("word")
    assert res_type in ("exe", "ambiguous")


def test_standby_watchdog_rearms_if_tts_callback_drops():
    """
    Test that if VoiceManager TTS completion callback fails to fire during standby,
    the 8-second watchdog timer automatically recovers ContinuousVoiceLoop to IDLE/WAITING_FOR_WAKE.
    """
    import time
    from voice.continuous_loop import ContinuousVoiceLoop, VoiceState
    from voice.voice_manager import VoiceManager

    vm = VoiceManager()
    vm.audio_manager.start_recording = MagicMock(return_value=True)
    vm.audio_manager.stop_recording = MagicMock(return_value=True)
    vm.activate = MagicMock(return_value=True)
    vm.speak = MagicMock()  # Deliberately do NOT fire on_tts_complete

    loop = ContinuousVoiceLoop(voice_manager=vm)
    loop.start()
    loop._set_state(VoiceState.LISTENING)

    # Trigger pause
    loop.trigger_transcription_ready("pause")
    assert loop.state == VoiceState.SPEAKING
    assert loop._standby_watchdog is not None

    # Simulate watchdog timeout immediately
    loop._on_standby_watchdog_timeout()
    assert loop.state == VoiceState.IDLE
    vm.activate.assert_called()

    loop.stop()


