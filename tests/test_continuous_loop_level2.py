"""
Level 2: Mocked Voice Tests (NLU Integration)
Verifies that ContinuousVoiceLoop correctly orchestrates handoffs
to AuraCore and ExecutionCoordinator, while mocking hardware STT/TTS.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState
from src.brain.execution_coordinator import CoordinationResult


class TestContinuousVoiceLoopLevel2(unittest.TestCase):
    def setUp(self):
        # 1. Mock hardware VoiceManager
        self.mock_voice_manager = MagicMock()
        self.mock_voice_manager.start.return_value = True
        self.mock_voice_manager.activate.return_value = True

        # 2. Mock AuraCore
        self.mock_aura_core = MagicMock()
        self.mock_aura_core.process_request = AsyncMock(return_value="Mock response")

        # 3. Instantiate ContinuousVoiceLoop directly
        self.loop = ContinuousVoiceLoop(
            voice_manager=self.mock_voice_manager,
            aura_core=self.mock_aura_core,
        )
        self.loop.history = []
        self.loop.turn_count = 0

    def tearDown(self):
        self.loop.stop()

    def test_level2_full_pipeline_mocked_execution(self):
        """
        Tests the voice loop state transitions:
        Mock Wake -> Mock STT -> AuraCore -> Mock TTS
        """
        # Start the FSM
        self.loop.start()
        self.assertEqual(self.loop.state.name, "IDLE")

        # 1. Mock Wake
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state.name, "LISTENING")

        # 2. Mock STT String ("open calculator")
        self.loop.trigger_transcription_ready("open calculator")
        
        # After execution completes, it enters SPEAKING
        self.assertEqual(self.loop.state.name, "SPEAKING")

        # Verify AuraCore was called
        self.mock_aura_core.process_request.assert_called_once_with("open calculator")
        
        # Ensure the history shows the result
        self.assertEqual(len(self.loop.history), 1)
        self.assertTrue(self.loop.history[0]["success"])
        self.assertEqual(self.loop.history[0]["transcript"], "open calculator")

        # 3. Mock TTS Complete -> Cooldown -> FOLLOW_UP_LISTENING -> timeout -> IDLE
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state.name, "FOLLOW_UP_LISTENING")
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state.name, "IDLE")

        # --- Turn 2 ---
        # 1. Mock Wake
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state.name, "LISTENING")

        # 2. Mock STT ("open notepad")
        self.loop.trigger_transcription_ready("open notepad")
        self.assertEqual(self.loop.state.name, "SPEAKING")

        # Verify exactly 2 calls passed to AuraCore
        self.assertEqual(self.mock_aura_core.process_request.call_count, 2)

        # Ensure history
        self.assertEqual(len(self.loop.history), 2)
        self.assertEqual(self.loop.history[1]["transcript"], "open notepad")

        # 3. Mock TTS Complete
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state.name, "FOLLOW_UP_LISTENING")
        self.loop._on_followup_timeout()
        self.assertEqual(self.loop.state.name, "IDLE")

        # Stop
        self.loop.stop()
        self.assertFalse(self.loop._running)


if __name__ == "__main__":
    unittest.main(verbosity=2)
