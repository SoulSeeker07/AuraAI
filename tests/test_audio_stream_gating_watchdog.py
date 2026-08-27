"""
Tests for Audio Stream Gating, Watchdog Recovery, and Multi-Turn Stability
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from voice.audio_manager import AudioManager, AudioDeviceInfo
from voice.voice_manager import VoiceManager
from voice.models import ConversationState, VoiceContext


@pytest.fixture
def fresh_audio_mgr():
    """Create an isolated AudioManager instance."""
    # Reset singleton state
    AudioManager._instance = None
    mgr = AudioManager()
    mgr.input_device = AudioDeviceInfo(1, "Test Mic", input=True, output=False, sample_rate=48000, channels=2)
    return mgr


def test_software_gating_preserves_hardware_stream(fresh_audio_mgr):
    """Verify enable/disable capture toggles queue delivery without calling stream.stop()."""
    mgr = fresh_audio_mgr
    received_chunks = []

    with patch("sounddevice.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        # Start recording (negotiated 16000Hz, 1 channel)
        assert mgr.start_recording(lambda c: received_chunks.append(c), sample_rate=16000, channels=1) is True
        assert mgr.is_capture_enabled() is True
        assert mgr._active_sample_rate == 16000
        assert mgr._active_channels == 1

        # Simulate audio chunk arriving while enabled
        mgr._stream_callback(MagicMock(tobytes=lambda: b"chunk1"), 160, 0.0, None)
        time.sleep(0.15)
        assert b"chunk1" in received_chunks

        # Software mute (disable capture)
        mgr.disable_capture()
        assert mgr.is_capture_enabled() is False

        # Simulate audio arriving while muted
        mgr._stream_callback(MagicMock(tobytes=lambda: b"chunk2_muted"), 160, 0.0, None)
        time.sleep(0.15)
        assert b"chunk2_muted" not in received_chunks

        # Verify physical InputStream.stop() was NEVER called during software mute
        mock_stream.stop.assert_not_called()

        # Re-enable capture
        mgr.enable_capture()
        assert mgr.is_capture_enabled() is True
        mgr._stream_callback(MagicMock(tobytes=lambda: b"chunk3"), 160, 0.0, None)
        time.sleep(0.15)
        assert b"chunk3" in received_chunks

        mgr.stop_recording()


def test_watchdog_recovers_silent_stream_and_preserves_negotiated_settings(fresh_audio_mgr):
    """Verify watchdog triggers recovery on silence >1.5s during active capture and uses negotiated settings."""
    mgr = fresh_audio_mgr

    with patch("sounddevice.InputStream") as mock_stream_cls:
        mock_stream1 = MagicMock()
        mock_stream2 = MagicMock()
        mock_stream_cls.side_effect = [mock_stream1, mock_stream2]

        assert mgr.start_recording(lambda c: None, sample_rate=16000, channels=1) is True
        assert mgr._active_sample_rate == 16000

        # Simulate stream going silent for 1.6s
        mgr._last_chunk_time = time.time() - 2.0
        time.sleep(0.2)  # Allow monitor thread to run empty queue watchdog

        # Second InputStream should have been created with exact negotiated settings (16000, 1), not device defaults (48000, 2)
        assert mock_stream_cls.call_count == 2
        calls = mock_stream_cls.call_args_list
        assert calls[1].kwargs["samplerate"] == 16000
        assert calls[1].kwargs["channels"] == 1

        # Recovery attempts counter should reset to 0 on successful recovery
        assert mgr._recovery_attempts == 0

        mgr.stop_recording()


def test_multi_turn_voice_manager_avoids_hardware_churn():
    """Verify 5+ consecutive turns with barge-in never call physical stop_recording on AudioManager."""
    # Reset singleton
    AudioManager._instance = None
    audio_mgr = AudioManager()
    audio_mgr.input_device = AudioDeviceInfo(1, "Test Mic", input=True, output=False)

    with patch("sounddevice.InputStream") as mock_stream_cls, \
         patch("sounddevice.OutputStream"):
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        vm = VoiceManager()
        vm.audio_manager = audio_mgr
        vm.stt_manager = MagicMock()
        vm.stt_manager.finalize.return_value = "Test Command"
        vm.tts_manager = MagicMock()
        vm.tts_manager.add_text.return_value = True
        vm.tts_manager.speak.return_value = True
        vm.wake_word = MagicMock()
        vm.wake_word.activate.return_value = True

        # Activate session
        assert vm.activate() is True
        assert mock_stream.start.call_count == 1
        assert mock_stream.stop.call_count == 0

        # Run 5 consecutive turns
        for turn in range(1, 6):
            # 1. Wake word detected -> start active listening
            vm._start_active_listening()
            assert audio_mgr.is_capture_enabled() is True

            # 2. User finishes speech -> finalize STT (software mute)
            vm._finalize_stt()
            assert audio_mgr.is_capture_enabled() is False

            # 3. TTS speak
            vm.speak(f"Response for turn {turn}")
            assert audio_mgr.is_capture_enabled() is False

            # 4. On turn 3, simulate a barge-in interrupt
            if turn == 3:
                vm.interrupt()
                assert audio_mgr.is_capture_enabled() is False

            # 5. Cooldown / resume listening
            vm._start_active_listening()
            assert audio_mgr.is_capture_enabled() is True

        # Verify physical stream was started ONCE at session start and NEVER stopped during turns
        assert mock_stream.start.call_count == 1
        assert mock_stream.stop.call_count == 0

        # Full session shutdown should finally call physical stop
        vm.stop()
        assert mock_stream.stop.call_count == 1
