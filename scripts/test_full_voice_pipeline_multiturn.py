"""
Full End-to-End Voice Pipeline Multi-Turn & Barge-In Stress Test
================================================================
Exercises the complete ContinuousVoiceLoop + VoiceManager state machine,
turn-to-turn transitions, VAD, STT finalization, TTS playback, and live barge-in
interruptions over 5+ consecutive turns.
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from voice.audio_manager import AudioManager
from voice.voice_manager import VoiceManager
from voice.continuous_loop import ContinuousVoiceLoop, VoiceState
from voice.models import ConversationState, VoiceContext

def main():
    print("=" * 70)
    print(" FULL AURA CONTINUOUS VOICE LOOP MULTI-TURN & BARGE-IN TEST")
    print("=" * 70)

    # 1. Initialize VoiceManager
    voice_mgr = VoiceManager()
    
    # Mock only the heavy cloud STT/TTS external APIs to avoid external network dependencies
    # while keeping the real AudioManager, hardware streams, and full state machine active
    voice_mgr.stt_manager = MagicMock()
    voice_mgr.stt_manager.finalize.side_effect = lambda: "What is the time?"
    voice_mgr.tts_manager = MagicMock()
    voice_mgr.tts_manager.add_text.return_value = True
    voice_mgr.tts_manager.speak.return_value = True
    voice_mgr.tts_manager.stop.return_value = True

    # 2. Initialize ContinuousVoiceLoop
    mock_core = MagicMock()
    async def _mock_stream_request(text):
        yield "The time is 1:15 AM."
    mock_core.process_request_stream = _mock_stream_request

    loop = ContinuousVoiceLoop(voice_manager=voice_mgr, aura_core=mock_core)
    
    print("\n[Step 1] Starting ContinuousVoiceLoop...")
    assert loop.start() is True
    print(f"[*] Loop state: {loop.state.value}")
    print(f"[*] VoiceManager state: {voice_mgr.state.value}")
    print(f"[*] Physical stream active: {voice_mgr.audio_manager.is_recording()}")
    print(f"[*] Capture enabled: {voice_mgr.audio_manager.is_capture_enabled()}")

    # 3. Execute 5 Full Conversational Turns through the real state machine
    for turn in range(1, 6):
        print(f"\n--- Turn #{turn} ---")
        
        # A. Wake word detection triggers active listening
        print(f"[*] [Turn {turn}] Wake word 'Hey Aura' detected...")
        voice_mgr.wake_word.on_wake_word_detected("aura")
        assert voice_mgr.state == ConversationState.ACTIVE_LISTENING
        assert loop.state == VoiceState.LISTENING
        assert voice_mgr.audio_manager.is_capture_enabled() is True
        print(f"    -> State: {loop.state.name}, Mic capture: ENABLED")

        # B. User speaks, STT processes, speech ends -> finalize STT
        time.sleep(0.3)
        print(f"[*] [Turn {turn}] VAD detected silence -> Finalizing STT...")
        voice_mgr._finalize_stt()
        
        # State transitions to UNDERSTANDING / THINKING while LLM generates
        print(f"    -> State during reasoning: {loop.state.value}")
        assert loop.state in (VoiceState.UNDERSTANDING, VoiceState.SPEAKING)
        assert voice_mgr.audio_manager.is_capture_enabled() is False
        print(f"    -> Mic capture: DISABLED (software-muted)")

        # C. On Turn 3 & 4: Simulate Barge-in Interruption while speaking
        if turn in (3, 4):
            print(f"[*] [Turn {turn}] Simulating User Barge-in during response...")
            # Wake word or barge-in interrupt fired
            voice_mgr.interrupt()
            assert voice_mgr.state == ConversationState.INTERRUPTED
            print(f"    -> Interruption state verified: {voice_mgr.state.value}")
            
            # Continuous loop recovers to active listening on barge-in
            voice_mgr._start_active_listening()
            assert voice_mgr.audio_manager.is_capture_enabled() is True
            print(f"    -> Resumed to active listening: {voice_mgr.state.value}")
            time.sleep(0.2)
            voice_mgr._finalize_stt()

        # D. TTS playback completes -> triggers cooldown & follow-up window
        time.sleep(0.2)
        print(f"[*] [Turn {turn}] TTS playback complete -> triggering completion...")
        voice_mgr._on_tts_complete()
        
        # Follow-up timer engages (mic unmuted for follow-up query)
        time.sleep(0.4)
        print(f"    -> Post-turn state: {voice_mgr.state.value}, Loop state: {loop.state.value}")
        print(f"    -> Mic capture active: {voice_mgr.audio_manager.is_capture_enabled()}")

    print("\n[Step 2] Verifying system integrity after 5 full conversational turns...")
    print(f"[*] Total completed turns: {loop.turn_count}")
    assert loop.turn_count >= 5, f"Expected 5+ turns, got {loop.turn_count}"
    assert voice_mgr.audio_manager.is_recording() is True, "Physical stream was unexpectedly closed!"

    # 4. Clean shutdown
    print("\n[Step 3] Stopping loop...")
    loop.stop()
    print(f"[*] Physical stream closed: {not voice_mgr.audio_manager.is_recording()}")
    print("\n" + "=" * 70)
    print(" ALL 5+ FULL CONVERSATIONAL TURNS & BARGE-INS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
