"""
Level 1: State-Machine Unit Tests for the Aura Continuous Voice Loop
Verifies pure FSM transitions without hardware dependencies.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.continuous_loop import ContinuousVoiceLoop, VoiceState


class TestContinuousVoiceLoopFSM(unittest.TestCase):
    def setUp(self):
        # Mock VoiceManager to avoid touching hardware
        self.mock_voice_manager = MagicMock()
        self.mock_voice_manager.start.return_value = True
        self.mock_voice_manager.activate.return_value = True
        self.mock_voice_manager.tts_manager = MagicMock()

        self.mock_aura_core = MagicMock()
        self.mock_aura_core.process_request = AsyncMock(return_value="Mock response")

        self.loop = ContinuousVoiceLoop(voice_manager=self.mock_voice_manager)
        self.loop._aura_core = self.mock_aura_core

    def test_initial_state(self):
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_basic_turn_flow(self):
        self.loop.start()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

        # 1. Wake detected
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

        # 2. Transcription ready
        self.loop.trigger_transcription_ready("open calculator")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        # 3. TTS Completes -> enters 3.5s follow-up listening mode
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)

        # 4. Timeout occurs with silence -> returns to IDLE (wake standby)
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_followup_direct_speech_without_wake_word(self):
        """Verify user can speak follow-up command directly during FOLLOW_UP_LISTENING without saying 'Aura'."""
        self.loop.start()

        # Turn 1: Wake -> "open calculator" -> Speak -> Follow-up
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("open calculator")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)

        # Turn 2: Direct speech during follow-up window (NO wake word)
        self.loop.trigger_transcription_ready("now open notepad")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)
        self.assertEqual(self.loop.turn_count, 2)
        self.assertEqual(self.loop.history[1]["transcript"], "now open notepad")

        # Complete Turn 2
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_conversational_routing(self):
        self.loop.start()

        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("what is the weather")

        self.assertEqual(self.loop.state, VoiceState.SPEAKING)
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_m21_regression_duplicate_tasks(self):
        """
        Regression Test Target:
        Verify Turn 1 completes, enters FOLLOW_UP_LISTENING, timeout to IDLE,
        Turn 2 completes, and Stop Listening cleanly releases microphone.
        """
        self.loop.start()

        # --- TURN 1 ---
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

        self.loop.trigger_transcription_ready("open calculator")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

        # --- TURN 2 ---
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

        self.loop.trigger_transcription_ready("open notepad")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

        # --- STOP ---
        self.loop.stop()
        self.assertEqual(self.loop.state, VoiceState.IDLE)
        self.assertFalse(self.loop._running)
        self.mock_voice_manager.stop.assert_called_once()
        
        self.assertEqual(self.loop.turn_count, 2)
        self.assertEqual(self.loop.history[0]["transcript"], "open calculator")
        self.assertEqual(self.loop.history[1]["transcript"], "open notepad")

    def test_barge_in_wake_while_speaking(self):
        """SPEAKING + wake_detected -> interrupts TTS and transitions to LISTENING (Barge-in)."""
        self.loop.start()
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("open calculator")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)

        # Inject wake word while speaking -> should barge in
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state, VoiceState.LISTENING)

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

    def test_spoken_pause_listening_phrase(self):
        """Verify saying 'go to sleep' speaks standby message, enters SPEAKING, and transitions to IDLE upon TTS completion."""
        self.loop.start()
        self.assertTrue(self.loop._running)

        # Wake -> Speak 'go to sleep'
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("Go to sleep.")

        # Loop speaks standby message (state is SPEAKING while audio plays)
        self.assertTrue(self.loop._running)
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)
        self.mock_voice_manager.speak.assert_called_with("Going on standby. Say Aura when you need me.")

        # TTS finishes -> triggers completed callback -> transitions to IDLE / wake-word listening
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_spoken_stop_listening_phrase(self):
        """Verify saying 'Stop listening' gracefully speaks farewell, halts loop, and calls on_stop."""
        self.loop.start()
        self.assertTrue(self.loop._running)

        mock_on_stop = MagicMock()
        self.loop.on_stop = mock_on_stop

        # Wake -> Speak 'Stop listening'
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("Stop listening.")

        # Loop should now be stopped
        self.assertFalse(self.loop._running)
        self.assertEqual(self.loop.state, VoiceState.IDLE)
        mock_on_stop.assert_called_once()
        self.mock_voice_manager.speak.assert_called_with("Stopping voice listening. Type start listening to resume.")

    def test_spoken_commands_no_false_positive_collisions(self):
        """Verify multi-word commands like 'cancel my download' or 'stop the timer' pass through to execution."""
        self.loop.start()
        self.assertTrue(self.loop._running)

        # 1. "Cancel my download" should NOT trigger standby — should process transcript normally
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("Cancel my download.")
        # Reaches SPEAKING because _process_transcript executes normally
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)
        self.assertTrue(self.loop._running)
        self.mock_aura_core.process_request.assert_called_with("Cancel my download.")

        # Complete turn
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

        # 2. "Pause the music" should NOT trigger standby
        self.loop.trigger_wake_detected("Aura")
        self.loop.trigger_transcription_ready("Pause the music.")
        self.assertEqual(self.loop.state, VoiceState.SPEAKING)
        self.assertTrue(self.loop._running)

        # Complete turn
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state, VoiceState.IDLE)

    def test_continuous_10_turns_stress_test(self):
        """Verify 10 continuous turns run back-to-back without getting stuck or deadlocking."""
        self.loop.start()
        for i in range(1, 11):
            self.loop.trigger_wake_detected("Aura")
            self.assertEqual(self.loop.state, VoiceState.LISTENING)
            self.loop.trigger_transcription_ready(f"open app {i}")
            self.assertEqual(self.loop.state, VoiceState.SPEAKING)
            self.loop.trigger_tts_completed()
            self.assertEqual(self.loop.state, VoiceState.FOLLOW_UP_LISTENING)
            self.loop._on_followup_timeout()
            self.assertEqual(self.loop.state, VoiceState.IDLE)
        self.assertEqual(self.loop.turn_count, 10)
        self.assertEqual(len(self.loop.history), 10)

if __name__ == "__main__":
    unittest.main(verbosity=2)
