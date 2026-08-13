"""
Level 2: Mocked Voice Tests (NLU Integration)
Verifies that ContinuousVoiceLoop correctly orchestrates handoffs
to the existing NLU -> DecisionEngine -> ExecutionCoordinator path,
while mocking the hardware STT/TTS and Execution steps.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState
from src.core.orchestration.personal_os_runtime import PersonalOSRuntime, RuntimeExecutionReport
from src.brain.execution_coordinator import CoordinationResult


class TestContinuousVoiceLoopLevel2(unittest.TestCase):
    def setUp(self):
        # 1. Boot real PersonalOSRuntime to wire NLU, DMM, etc.
        self.os_runtime = PersonalOSRuntime.get_instance()
        # Mock event_runtime.start and create_task to prevent asyncio crash
        self.os_runtime.event_runtime.start = AsyncMock()
        with patch('asyncio.create_task'):
            self.os_runtime.boot()

        # 2. Mock hardware VoiceManager
        self.mock_voice_manager = MagicMock()
        self.mock_voice_manager.start.return_value = True
        self.mock_voice_manager.activate.return_value = True

        # Inject mock voice manager into the loop
        self.loop = self.os_runtime.voice_loop
        self.loop.voice_manager = self.mock_voice_manager

        # Clear history for clean test
        self.loop.history = []
        self.loop.turn_count = 0

    def tearDown(self):
        # Clean up singleton
        self.loop.stop()
        PersonalOSRuntime.reset_instance()

    @patch("src.core.orchestration.personal_os_runtime.ExecutionCoordinator.coordinate", new_callable=AsyncMock)
    def test_level2_full_pipeline_mocked_execution(self, mock_coordinate):
        """
        Tests the full pipeline:
        Mock Wake -> Mock STT -> Real NLU -> Real DMM -> Mocked Execution -> Mock TTS
        """
        # Prepare mock execution result
        mock_result = CoordinationResult(
            goal="open calculator",
            success=True,
            total_time=0.5,
            step_results=[{"status": "mocked_success"}],
            data={}
        )
        mock_coordinate.return_value = mock_result

        # Start the FSM
        self.loop.start()
        self.assertEqual(self.loop.state.name, "IDLE")

        # 1. Mock Wake
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state.name, "LISTENING")

        # 2. Mock STT String ("open calculator")
        # This will trigger Real NLU -> Real DMM -> our mock_coordinate
        self.loop.trigger_transcription_ready("open calculator")
        
        # After execution completes, it enters SPEAKING
        self.assertEqual(self.loop.state.name, "SPEAKING")

        # Verify the real routing reached the execution coordinator
        mock_coordinate.assert_called_once()
        
        # Ensure the history shows the result
        self.assertEqual(len(self.loop.history), 1)
        self.assertTrue(self.loop.history[0]["success"])
        self.assertEqual(self.loop.history[0]["transcript"], "open calculator")

        # 3. Mock TTS Complete -> Cooldown -> IDLE
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state.name, "IDLE")

        # --- Turn 2 ---
        
        mock_result_2 = CoordinationResult(
            goal="open notepad",
            success=True,
            total_time=0.5,
            step_results=[{"status": "mocked_success"}],
            data={}
        )
        mock_coordinate.return_value = mock_result_2

        # 1. Mock Wake
        self.loop.trigger_wake_detected("Aura")
        self.assertEqual(self.loop.state.name, "LISTENING")

        # 2. Mock STT ("open notepad")
        self.loop.trigger_transcription_ready("open notepad")
        self.assertEqual(self.loop.state.name, "SPEAKING")

        # Verify exactly 2 calls passed through the real NLU/DMM to the coordinator
        self.assertEqual(mock_coordinate.call_count, 2)

        # Ensure history
        self.assertEqual(len(self.loop.history), 2)
        self.assertEqual(self.loop.history[1]["transcript"], "open notepad")

        # 3. Mock TTS Complete
        self.loop.trigger_tts_completed()
        self.assertEqual(self.loop.state.name, "IDLE")

        # Stop
        self.loop.stop()
        self.assertFalse(self.loop._running)

if __name__ == "__main__":
    unittest.main(verbosity=2)
