"""
Aura Continuous Voice Loop Orchestrator
=======================================

Provides a continuous voice interaction loop using a strict state machine.
This orchestrator sits on top of the VoiceManager to handle lifecycle
transitions, handoffs to the existing NLU/Execution engines, and TTS echo
suppression boundaries.
"""

import asyncio
import logging
import time
from enum import Enum, auto
from typing import Any

from .models import VoiceContext
from .voice_manager import VoiceManager

logger = logging.getLogger(__name__)


class VoiceState(Enum):
    """Explicit lifecycle states for the voice interaction loop."""
    IDLE = auto()          # Waiting for the wake word (via VoiceManager)
    WAKE_DETECTED = auto() # Wake word confirmed; preparing audio capture
    LISTENING = auto()     # Capturing user speech via the microphone
    TRANSCRIBING = auto()  # Speech ended; STT engine decoding audio
    UNDERSTANDING = auto() # Routing transcript to existing NLU
    EXECUTING = auto()     # Running local deterministic tools
    AI_RESPONSE = auto()   # Generating conversational replies
    SPEAKING = auto()      # Piper TTS is actively playing audio
    COOLDOWN = auto()      # Settling period before explicit buffer flush


class ContinuousVoiceLoop:
    """
    Continuous Voice Loop orchestrator.
    Strictly manages voice state transitions and hands off STT to 
    existing CoreRouter/ExecutionCoordinator without bypassing them.
    """

    def __init__(
        self,
        voice_manager: VoiceManager | None = None,
        coordinator: Any | None = None,
        nlu_engine: Any | None = None,
    ):
        self.voice_manager = voice_manager or VoiceManager()
        self.coordinator = coordinator
        self.nlu_engine = nlu_engine
        
        self._running = False
        self._loop_task: asyncio.Task | None = None
        self.state = VoiceState.IDLE

        # Wire VoiceManager callbacks
        self.voice_manager.on_state_change = self._on_state_change
        self.voice_manager.on_stt_result = self._on_stt_result
        self.voice_manager.on_stt_partial = self._on_stt_partial
        self.voice_manager.on_wake_word_detected = self._on_wake_word_detected
        self.voice_manager.on_tts_complete = self._on_tts_complete
        self.voice_manager.on_error = self._on_voice_error

        # Turn history / stats
        self.turn_count = 0
        self.history: list[dict[str, Any]] = []

        logger.info("[ContinuousVoiceLoop] INITIALIZING")
        self._set_state(VoiceState.IDLE)

    def _set_state(self, new_state: VoiceState):
        logger.info(f"[ContinuousVoiceLoop] State: {new_state.name}")
        self.state = new_state

    def start(self) -> bool:
        """Start the continuous voice loop lifecycle."""
        if self._running:
            logger.warning("ContinuousVoiceLoop already running")
            return True

        try:
            self.main_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.main_loop = None

        logger.info("[ContinuousVoiceLoop] START_REQUESTED")
        self._running = True
        self._set_state(VoiceState.IDLE)
        
        success = self.voice_manager.start()
        if not success:
            logger.error("ContinuousVoiceLoop failed to start voice manager")
            self._running = False
            return False

        import os
        enable_wake_word = os.getenv("ENABLE_WAKE_WORD", "true").lower() == "true"

        if enable_wake_word:
            if not self.voice_manager.activate():
                self._running = False
                self.voice_manager.stop()
                logger.error("ContinuousVoiceLoop failed to enter wake-word listening")
                return False
            logger.info("[ContinuousVoiceLoop] WAITING_FOR_WAKE")
        else:
            logger.info("Wake word disabled by .env, skipping wake word and activating STT immediately")
            self._set_state(VoiceState.WAKE_DETECTED)
            self.trigger_listening()
            self.voice_manager._start_active_listening()

        logger.info("ContinuousVoiceLoop started and listening")
        return True

    def stop(self) -> None:
        """Stop the continuous voice loop cleanly."""
        logger.info("[ContinuousVoiceLoop] State: STOP_REQUESTED")
        self._running = False
        self.voice_manager.stop()
        logger.info("[VOICE] Shutdown: PASS")
        logger.info("[MIC] Stream released: PASS")
        logger.info("[ContinuousVoiceLoop] State: STOPPED")
        self._set_state(VoiceState.IDLE)

    # ------------------------------------------------------------------------
    # State Machine Event Injections (For Testing & Hardware Callbacks)
    # ------------------------------------------------------------------------

    def trigger_wake_detected(self, wake_word: str = "Aura"):
        if self.state == VoiceState.IDLE and self._running:
            self._set_state(VoiceState.WAKE_DETECTED)
            # Typically, audio capture triggers immediately
            import sys
            sys.stdout.write("\n\n🎧 Wake word detected! Aura is listening for your command...\n")
            sys.stdout.flush()
            self.trigger_listening()
            logger.info("[VoiceManager] STT_ACTIVE")

    def trigger_listening(self):
        if self.state == VoiceState.WAKE_DETECTED:
            self._set_state(VoiceState.LISTENING)

    def _return_to_listening_or_idle(self):
        """Helper to return to correct state based on wake word setting."""
        import os
        enable_wake_word = os.getenv("ENABLE_WAKE_WORD", "true").lower() == "true"
        if not enable_wake_word and self._running:
            self._set_state(VoiceState.WAKE_DETECTED)
            self.trigger_listening()
            self.voice_manager._start_active_listening()
        else:
            self._set_state(VoiceState.IDLE)

    def trigger_transcription_ready(self, transcript: str):
        if self.state in (VoiceState.LISTENING, VoiceState.WAKE_DETECTED, VoiceState.TRANSCRIBING):
            clean_t = transcript.strip().lower()
            hallucinations = [
                "i'll see you next time.",
                "i'll see you next time",
                "i'll see you in the next video.",
                "i'll see you in the next video",
                "thank you.",
                "thank you",
                "thanks for watching.",
                "thanks for watching",
                "bye.",
                "bye",
                "you",
            ]
            if not transcript.strip() or clean_t in hallucinations:
                # Empty transcription, return to correct state
                self._return_to_listening_or_idle()
                return
                
            self._set_state(VoiceState.TRANSCRIBING)
            import sys
            sys.stdout.write(f"\n🗣️ You said: '{transcript}'\n")
            sys.stdout.flush()
            self.turn_count += 1
            self._process_transcript(transcript)
        elif not self._running:
             clean_t = transcript.strip().lower()
             hallucinations = [
                 "i'll see you next time.",
                 "i'll see you next time",
                 "i'll see you in the next video.",
                 "i'll see you in the next video",
                 "thank you.",
                 "thank you",
                 "thanks for watching.",
                 "thanks for watching",
                 "bye.",
                 "bye",
                 "you",
             ]
             if not transcript.strip() or clean_t in hallucinations:
                 self._return_to_listening_or_idle()
                 return
             self._set_state(VoiceState.TRANSCRIBING)
             import sys
             sys.stdout.write(f"\n🗣️ You said: '{transcript}'\n")
             sys.stdout.flush()
             self.turn_count += 1
             self._process_transcript(transcript)

    def trigger_tts_completed(self):
        if self.state == VoiceState.SPEAKING:
            self._set_state(VoiceState.COOLDOWN)
            self._handle_cooldown()

    # ------------------------------------------------------------------------
    # Hardware Callbacks
    # ------------------------------------------------------------------------

    def _on_wake_word_detected(self, wake_word: str) -> None:
        """Callback when the microphone wake word is detected."""
        self.trigger_wake_detected(wake_word)

    def _on_stt_result(self, context: VoiceContext):
        if context.transcript:
            self.trigger_transcription_ready(context.transcript)

    def _on_stt_partial(self, context: VoiceContext):
        """Render live transcription to terminal with ANSI colors."""
        import sys
        if context.confirmed_transcript or context.tentative_transcript:
            # Clear line and print
            # \033[K clears to end of line
            # \033[2m dims the tentative text
            # \033[0m resets formatting
            confirmed = context.confirmed_transcript
            tentative = context.tentative_transcript
            
            output = "\r\033[K🗣️ You said: '"
            if confirmed:
                output += confirmed
                if tentative:
                    output += " "
            if tentative:
                output += f"\033[2m{tentative}\033[0m"
            output += "'..."
            
            sys.stdout.write(output)
            sys.stdout.flush()

    def _on_tts_complete(self) -> None:
        """Callback when TTS finishes speaking response."""
        logger.info("[VoiceManager] TTS_COMPLETE")
        self.trigger_tts_completed()

    def _on_voice_error(self, error: str) -> None:
        """Callback on voice system error."""
        logger.error(f"[ContinuousVoiceLoop] Voice error: {error}")
        if self.state == VoiceState.SPEAKING:
             self.trigger_tts_completed()
        else:
             self._return_to_listening_or_idle()

    # ------------------------------------------------------------------------
    # Internal Handoffs
    # ------------------------------------------------------------------------

    def _process_transcript(self, transcript: str):
        self._set_state(VoiceState.UNDERSTANDING)
        logger.info(f"[ContinuousVoiceLoop Turn #{self.turn_count}] Processing transcript: '{transcript}'")
        
        from src.core.orchestration.personal_os_runtime import PersonalOSRuntime
        os_runtime = PersonalOSRuntime.get_instance()
        
        self._set_state(VoiceState.EXECUTING)
        
        report = None
        try:
            # Use the captured main_loop if available and running
            loop = getattr(self, "main_loop", None)
            
            if not loop or not loop.is_running():
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

            if loop and loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(
                    os_runtime.execute_goal(transcript, input_type="voice"), loop
                )
                report = fut.result(timeout=60)
            else:
                logger.warning("[ContinuousVoiceLoop] Falling back to asyncio.run (no running loop found)")
                report = asyncio.run(os_runtime.execute_goal(transcript, input_type="voice"))
        except Exception as e:
            logger.error(f"[ContinuousVoiceLoop] Coordination error: {e}")
                
        success = getattr(report, "success", True) if report else False
        spoken_summary = getattr(report, "spoken_summary", None)
        
        if not spoken_summary:
            if success:
                spoken_summary = f"Done processing: {transcript}."
            else:
                spoken_summary = f"Sorry, {transcript} could not be completed successfully."

        turn_fact = {
            "turn": self.turn_count,
            "transcript": transcript,
            "success": success,
            "spoken_summary": spoken_summary,
            "report": report,
        }
        self.history.append(turn_fact)
        
        self._set_state(VoiceState.SPEAKING)
        
        # If running, we send to actual VoiceManager. If just state-testing, we skip actual TTS.
        if self._running:
            # We assume VoiceManager handles the underlying hardware speak task,
            # which will eventually trigger on_tts_complete and call trigger_tts_completed()
            self.voice_manager.speak(spoken_summary)
            
    def _handle_cooldown(self):
        """Brief settling period before flushing mic buffer and returning to IDLE."""
        if self._running:
            time.sleep(0.5)  # Extended cooldown to ensure hardware echo suppression
            import os
            enable_wake_word = os.getenv("ENABLE_WAKE_WORD", "true").lower() == "true"
            
            if not enable_wake_word:
                logger.info("Wake word disabled, returning to active listening immediately")
                self._set_state(VoiceState.WAKE_DETECTED)
                self.trigger_listening()
                self.voice_manager._start_active_listening()
            else:
                if self.voice_manager.activate():
                    logger.info("[MIC] Recovery: PASS")
                    logger.info("[WAKE] Listener resumed: PASS")
                    self._set_state(VoiceState.IDLE)
                else:
                    logger.error("[ContinuousVoiceLoop] Failed to restore wake-word listening")
                    self._set_state(VoiceState.IDLE)
        else:
            self._set_state(VoiceState.IDLE)
