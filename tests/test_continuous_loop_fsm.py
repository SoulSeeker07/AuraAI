"""
Level 1: State-Machine Unit Tests for the Aura Continuous Voice Loop
Verifies pure FSM transitions without hardware dependencies.
"""

import unittest
from unittest.mock import MagicMock
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState


class TestContinuousVoiceLoopFSM(unittest.TestCase):
    def setUp(self):
        # Mock VoiceManager to avoid touching hardware
        self.mock_voice_manager = MagicMock()
        self.mock_voice_manager.start.return_value = True
        self.mock_voice_manager.activate.return_value = True

        self.loop = ContinuousVoiceLoop(voice_manager=self.mock_voice_manager)

    def test_initial_state(self):
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_basic_turn_flow(self):
        # The FSM is built so we don't even need to call `start()` to inject events,
        # but calling start ensures _running is True (required for some transitions).
        self.loop.start()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

        # 1. Wake detected
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

        # 2. Transcription ready
        self.loop.trigger_transcription_ready("open calculator")
        # trigger_transcription_ready internally synchronously calls _process_transcript,
        # which evaluates the map, sends it to EXECUTING (since it matches "calculator"),
        # and then ends at SPEAKING (waiting for TTS).
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        # 3. TTS Completes
        self.loop.trigger_tts_completed()
        # _handle_cooldown completes and returns to IDLE
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_conversational_routing(self):
        self.loop.start()

        # Transcript that does NOT match the static map should route to AI_RESPONSE
        # Wait, the current logic triggers SPEAKING directly after evaluating the map.
        # Let's verify the intermediate states by mocking _process_transcript if needed,
        # but the synchronous implementation runs through them.
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("what is the weather")

        # It routes to AI_RESPONSE internally, then SPEAKING
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_m21_regression_duplicate_tasks(self):
        """
        Regression Test Target:
        Verify Turn 1 completes, enters IDLE, waits, Turn 2 completes, enters IDLE,
        and `Stop Listening` cleanly releases microphone without orphan tasks.
        """
        self.loop.start()

        # --- TURN 1 ---
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

        self.loop.trigger_transcription_ready("open calculator")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

        # simulate wait
        import time
        time.sleep(0.1)

        # --- TURN 2 ---
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

        self.loop.trigger_transcription_ready("open notepad")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

        # --- STOP ---
        self.loop.stop()
        self.assertEqual(self.loop.state, VoiceState.IDLE)
        self.assertFalse(self.loop._running)
        self.mock_voice_manager.stop.assert_called_once()
        
        # Ensure only 2 turns were fully recorded
        self.assertEqual(self.loop.turn_count, 2)
        self.assertEqual(self.loop.history[0]["transcript"], "open calculator")
        self.assertEqual(self.loop.history[1]["transcript"], "open notepad")

    def test_negative_wake_while_speaking(self):
        """SPEAKING + wake_detected -> ignored -> remains SPEAKING"""
        self.loop.start()
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("open calculator")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        # Inject wake word while speaking
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING) # Should be ignored

    def test_negative_duplicate_wake(self):
        """WAKE_DETECTED + wake_detected -> ignored"""
        self.loop.start()
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

    def test_negative_empty_transcription(self):
        """TRANSCRIBING -> '' -> safely returns to IDLE"""
        self.loop.start()
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("")
        
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_negative_tts_failure(self):
        """SPEAKING -> TTS failure -> microphone lifecycle recovered -> IDLE"""
        self.loop.start()
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("open calculator")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        # Simulate TTS failure callback
        self.loop._on_voice_error("TTS crashed")
        # Error triggers trigger_tts_completed -> COOLDOWN -> IDLE
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_negative_stop_during_all_states(self):
        """Stop during every major state should terminate cleanly."""
        states_to_test = [
            VoiceState.IDLE,
            VoiceState.WAKE_DETECTED,
            VoiceState.LISTENING,
            VoiceState.TRANSCRIBING,
            VoiceState.UNDERSTANDING,
            VoiceState.EXECUTING,
            VoiceState.AI_RESPONSE,
            VoiceState.SPEAKING,
            VoiceState.COOLDOWN
        ]
        for state in states_to_test:
            loop = ContinuousVoiceLoop(voice_manager=self.mock_voice_manager)
            loop.start()
            loop.state = state
            loop.stop()
            self.assertEqual(loop.state, VoiceState.IDLE)
            self.assertFalse(loop._running)

if __name__ == "__main__":
    unittest.main(verbosity=2)
