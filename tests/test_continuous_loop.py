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

    # Call 4 times — should not trigger on_error yet
    for i in range(1, detector.MAX_CONSECUTIVE_FAILURES):
        result = detector.process_audio(bytes(3200), 16000)
        assert result is False
        assert detector.consecutive_failures == i
        detector.on_error.assert_not_called()

    # 5th call — hits MAX_CONSECUTIVE_FAILURES and triggers on_error
    result = detector.process_audio(bytes(3200), 16000)
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

    result = detector.process_audio(bytes(3200), 16000)
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
    from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState
    from src.voice.voice_manager import VoiceManager

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
    from src.voice.continuous_loop import ContinuousVoiceLoop
    from src.voice.voice_manager import VoiceManager

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

    # Feed 5 chunks to exceed MAX_CONSECUTIVE_FAILURES
    for _ in range(5):
        vm.process_audio(bytes(3200), 16000)

    loop.stop()

    # Capture output written to stdout/stderr
    captured = capsys.readouterr()
    assert "⚠️ [Voice System Warning]" in captured.err
    assert "consecutive failures" in captured.err

