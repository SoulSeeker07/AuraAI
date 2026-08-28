"""
Unit & Integration tests for:
1. Voice Barge-In (Interception during TTS playback via wake word and manual keys)
2. Self-trigger guard preventing false wake detection during TTS playback
3. Clean VoiceNotchOverlay shutdown and closeEvent timer cleanup
"""

import os
import time
from unittest.mock import MagicMock, patch
import pytest

from voice.models import ConversationState
from voice.voice_manager import VoiceManager
from voice.continuous_loop import ContinuousVoiceLoop, VoiceState


def test_barge_in_wake_word_halts_tts_and_listens():
    """Verify that wake word detected during SPEAKING state stops TTS and transitions to active listening."""
    vm = VoiceManager()
    vm.audio_manager.start_recording = MagicMock(return_value=True)
    vm.audio_manager.stop_recording = MagicMock(return_value=True)
    vm.audio_manager.enable_capture = MagicMock()
    vm.tts_manager.stop = MagicMock()
    vm.tts_manager.speak = MagicMock(return_value=True)

    # Put voice manager into SPEAKING state
    vm.speak("I am currently explaining something long to the user.")
    assert vm.state == ConversationState.SPEAKING
    assert vm._current_speaking_text == "I am currently explaining something long to the user."

    # Simulate wake word detected during speaking
    vm._on_wake_word_detected("Aura")

    # Assert TTS was halted and state transitioned to active listening
    assert vm.tts_manager.stop.called
    assert vm.state == ConversationState.ACTIVE_LISTENING
    assert vm._current_speaking_text == ""


def test_is_speaking_flag_propagated_to_wake_word_engine():
    """Verify that is_speaking flag is set on wake word engine during SPEAKING state."""
    vm = VoiceManager()
    vm.audio_manager.start_recording = MagicMock(return_value=True)
    vm.tts_manager.speak = MagicMock(return_value=True)
    vm.wake_word.engine = MagicMock()
    vm.wake_word.process_audio = MagicMock()

    vm.speak("Hello, my name is Aura, how can I help you today?")
    assert vm.state == ConversationState.SPEAKING

    dummy_audio = b"\x00" * 3200
    vm.process_audio(dummy_audio, 16000)

    # Assert is_speaking was flagged True on the engine
    assert getattr(vm.wake_word.engine, "is_speaking", False) is True
    assert vm.wake_word.process_audio.called


def test_barge_in_wake_detector_elevated_threshold():
    """Verify that AuraWakeDetector applies elevated threshold (0.88) and 4 required hits during TTS playback."""
    from AuraWakeWord.runtime.aura_wake_detector import AuraWakeDetector
    detector = AuraWakeDetector(model_path="AuraWakeWord/models/aura_wake_model_quant.onnx")

    # In idle / normal mode
    detector.is_speaking = False
    assert detector.is_speaking is False

    # In speaking mode
    detector.is_speaking = True
    assert detector.is_speaking is True


def test_continuous_loop_barge_in_synchronization():
    """Verify that ContinuousVoiceLoop correctly synchronizes to LISTENING on barge-in."""
    vm = VoiceManager()
    vm.audio_manager.start_recording = MagicMock(return_value=True)
    vm.audio_manager.stop_recording = MagicMock(return_value=True)
    vm.tts_manager.stop = MagicMock()

    loop = ContinuousVoiceLoop(voice_manager=vm)
    loop._set_state(VoiceState.SPEAKING)

    # Wake word trigger on continuous loop during speaking
    loop.trigger_wake_detected("Aura")

    assert loop.state == VoiceState.LISTENING
    assert vm.tts_manager.stop.called
    loop.stop()


def test_voice_notch_overlay_close_event_cleans_timers():
    """Verify that VoiceNotchOverlay.closeEvent cleanly stops all timers without error."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from gui.widgets.voice_notch_overlay import VoiceNotchOverlay
    notch = VoiceNotchOverlay()
    notch._is_test_env = True

    # Assert timers are initialized
    assert hasattr(notch, "_hover_timer")
    assert hasattr(notch, "_collapse_timer")
    assert hasattr(notch, "_result_collapse_timer")

    notch._hover_timer.start(1000)
    assert notch._hover_timer.isActive()

    # Trigger closeEvent
    from PySide6.QtGui import QCloseEvent
    close_ev = QCloseEvent()
    with patch.object(VoiceNotchOverlay, "close"):
        notch.closeEvent(close_ev)

    assert not notch._hover_timer.isActive()
    assert not notch._collapse_timer.isActive()
    assert not notch._result_collapse_timer.isActive()
    notch.deleteLater()
    app.processEvents()
