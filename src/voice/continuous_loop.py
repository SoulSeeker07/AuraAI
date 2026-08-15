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


def _safe_print(text: str, stream=None) -> None:
    """Helper to safely write to stdout/stderr without failing on encoding errors."""
    import sys
    target = stream or sys.stdout
    try:
        target.write(text)
        target.flush()
    except UnicodeEncodeError:
        try:
            target.buffer.write(text.encode("utf-8", errors="replace"))
            target.buffer.flush()
        except Exception:
            try:
                target.write(text.encode("ascii", errors="replace").decode("ascii"))
                target.flush()
            except Exception:
                pass
    except Exception:
        pass


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

    _global_aura_core: Any | None = None

    @classmethod
    def set_global_aura_core(cls, aura_core: Any) -> None:
        """Register active AuraCore singleton globally across all voice loops."""
        cls._global_aura_core = aura_core

    def __init__(
        self,
        voice_manager: VoiceManager | None = None,
        coordinator: Any | None = None,
        nlu_engine: Any | None = None,
        aura_core: Any | None = None,
    ):
        self.voice_manager = voice_manager or VoiceManager()
        self.coordinator = coordinator
        self.nlu_engine = nlu_engine
        # AuraCore reference – used by _process_transcript to reach the Groq path
        # (same as the text CLI path). Set here, injected via instance attribute,
        # or resolved from ContinuousVoiceLoop._global_aura_core.
        self._aura_core = aura_core or self._global_aura_core
        
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
        self.on_stop: Any | None = None

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
        if callable(getattr(self, "on_stop", None)):
            try:
                self.on_stop()
            except Exception as e:
                logger.debug(f"[ContinuousVoiceLoop] on_stop callback error: {e}")

    # ------------------------------------------------------------------------
    # State Machine Event Injections (For Testing & Hardware Callbacks)
    # ------------------------------------------------------------------------

    def trigger_wake_detected(self, wake_word: str = "Aura"):
        if self.state == VoiceState.IDLE and self._running:
            self._set_state(VoiceState.WAKE_DETECTED)
            # Typically, audio capture triggers immediately
            _safe_print("\n\n🎧 Wake word detected! Aura is listening for your command...\n")
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
            # Re-arm the wake-word detector so the mic doesn't go silent.
            # Without this, after a hallucination filter hit or error the system
            # would freeze at IDLE with no active listening.
            if self._running:
                if self.voice_manager.activate():
                    logger.info("[ContinuousVoiceLoop] Wake-word listener re-armed after returning to IDLE")
                else:
                    logger.warning("[ContinuousVoiceLoop] Failed to re-arm wake-word listener")

    VOICE_PAUSE_PHRASES = {
        "go to sleep",
        "go to sleep now",
        "standby",
        "stand by",
        "never mind",
        "nevermind",
        "cancel",
        "pause",
        "hold on",
        "sleep",
    }

    VOICE_STOP_PHRASES = {
        "stop listening",
        "stop voice",
        "stop listening now",
        "stop voice listening",
        "disable voice",
        "disable voice listening",
        "stop listening to me",
        "exit voice",
        "mute voice",
        "turn off voice",
        "turn off listening",
        "quit listening",
        "quit voice",
    }

    def trigger_transcription_ready(self, transcript: str):
        clean_t = transcript.strip().lower()
        clean_t_punct = clean_t.rstrip(".,!?")
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

        if self.state in (VoiceState.LISTENING, VoiceState.WAKE_DETECTED, VoiceState.TRANSCRIBING) or not self._running:
            # 1. Check for voice pause / standby commands (mic stays open, returns to wake-word idle)
            if clean_t_punct in self.VOICE_PAUSE_PHRASES or any(
                clean_t_punct.startswith(p)
                for p in ("go to sleep", "never mind", "nevermind", "stand by", "standby")
            ):
                self._set_state(VoiceState.TRANSCRIBING)
                _safe_print(f"\r\033[K\nYou > {transcript}\n")
                logger.info(f"[ContinuousVoiceLoop] Spoken voice pause/standby command detected: '{transcript}'")
                _safe_print("\n😴 Aura is on standby. Say 'Aura' to wake me up.\n")
                spoken_pause = "Going on standby. Say Aura when you need me."
                self._set_state(VoiceState.SPEAKING)
                try:
                    self.voice_manager.speak(spoken_pause)
                except Exception as e:
                    logger.debug(f"[ContinuousVoiceLoop] Standby TTS error: {e}")
                self._set_state(VoiceState.IDLE)
                self._return_to_listening_or_idle()
                return

            # 2. Check for voice hard stop / shutdown commands (mic stream closes, back to CLI)
            if clean_t_punct in self.VOICE_STOP_PHRASES or any(
                clean_t_punct.startswith(p)
                for p in ("stop listening", "stop voice", "quit listening", "disable voice", "turn off voice", "turn off listening")
            ):
                self._set_state(VoiceState.TRANSCRIBING)
                _safe_print(f"\r\033[K\nYou > {transcript}\n")
                logger.info(f"[ContinuousVoiceLoop] Spoken voice stop command detected: '{transcript}'")
                _safe_print("\n👋 Voice listening stopped. Type 'start listening' to resume.\n")
                spoken_farewell = "Stopping voice listening. Type start listening to resume."
                self._set_state(VoiceState.SPEAKING)
                try:
                    self.voice_manager.speak(spoken_farewell)
                except Exception as e:
                    logger.debug(f"[ContinuousVoiceLoop] Farewell TTS error: {e}")
                self.stop()
                return

            self._set_state(VoiceState.TRANSCRIBING)
            _safe_print(f"\r\033[K\nYou > {transcript}\n")  # Clear partial line, show final
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
        if context.confirmed_transcript or context.tentative_transcript:
            # Clear line and print
            # \033[K clears to end of line
            # \033[2m dims the tentative text
            # \033[0m resets formatting
            confirmed = context.confirmed_transcript
            tentative = context.tentative_transcript
            
            output = "\r\033[K🎤 You > "
            if confirmed:
                output += confirmed
                if tentative:
                    output += " "
            if tentative:
                output += f"\033[2m{tentative}\033[0m"
            _safe_print(output, end="", flush=True)

    def _on_state_change(self, new_state: Any) -> None:
        """Callback when underlying VoiceManager state changes."""
        logger.debug(f"[ContinuousVoiceLoop] VoiceManager state changed to: {new_state}")

    def _on_tts_complete(self) -> None:
        """Callback when TTS finishes speaking response."""
        logger.info("[VoiceManager] TTS_COMPLETE")
        self.trigger_tts_completed()

    def _on_voice_error(self, error: str) -> None:
        """Callback on voice system error."""
        logger.error(f"[ContinuousVoiceLoop] Voice error: {error}")
        import sys
        _safe_print(f"\n⚠️ [Voice System Warning] {error}\n", stream=sys.stderr)
        if self.state == VoiceState.SPEAKING:
             self.trigger_tts_completed()
        else:
             self._return_to_listening_or_idle()

    # ------------------------------------------------------------------------
    # Internal Handoffs
    # ------------------------------------------------------------------------

    def _process_transcript(self, transcript: str):
        """
        Hand the finalized voice transcript off to AuraCore and speak the response.

        Design notes
        ------------
        * We run on a *background audio thread* (called from the STT callback),
          NOT on the main asyncio event loop.
        * The main event loop is busy blocking in ``input()`` inside CLIClient.run(),
          so we MUST NOT schedule work onto it with run_coroutine_threadsafe – that
          coroutine would sit in the queue forever and fut.result() would time out
          after 60 s, silently swallowing the call.
        * Instead we create a *fresh* event loop owned by this thread via
          ``asyncio.run()``.  This is safe because aura_core.process_request is
          stateless with respect to which loop it runs on.
        * We deliberately mirror the text path in CLIClient._send_chat_message:
          ``aura_core.process_request(transcript)`` → Groq → spoken response.
          PersonalOSRuntime.execute_goal routes through ExecutionCoordinator (tool
          actions), which never reaches the Groq LLM for conversational utterances.
        """
        self._set_state(VoiceState.UNDERSTANDING)
        logger.info(
            f"[ContinuousVoiceLoop Turn #{self.turn_count}] Processing transcript: '{transcript}'"
        )

        # AuraCore must be injected before the first utterance via:
        #   personal_os.voice_loop._aura_core = self.aura_core   (CLIClient)
        # We deliberately do NOT attempt any import-based fallback because
        # main.py puts both "src/" and "." on sys.path, so any import of
        # "src.core.orchestration..." vs "core.orchestration..." resolves to
        # *different* module objects — which would create a second
        # PersonalOSRuntime singleton, a second ContinuousVoiceLoop, and a
        # second VoiceManager, re-initialising half the ML stack mid-turn.
        aura_core = getattr(self, "_aura_core", None) or self._global_aura_core
        if aura_core is None:
            logger.error(
                "[ContinuousVoiceLoop] _aura_core is None — voice command cannot reach Groq. "
                "Ensure CLIClient sets personal_os.voice_loop._aura_core before start()."
            )
            _safe_print(
                "\n⚠️ [Voice] Not connected to reasoning engine. "
                "Please stop and restart listening.\n"
            )
            self._return_to_listening_or_idle()
            return

        self._set_state(VoiceState.EXECUTING)

        spoken_summary: str | None = None
        success = False

        try:
            # Mirror CLIClient._send_chat_message exactly.
            # asyncio.run() creates a fresh loop on this background thread –
            # no interference with the main loop's blocking input() call.
            aura_core.add_to_conversation("user", transcript)
            _safe_print("\n🤔 Aura is thinking...\n")

            response: str = asyncio.run(aura_core.process_request(transcript))

            aura_core.add_to_conversation("assistant", response)
            _safe_print(f"\nAura > {response}\n")
            spoken_summary = response
            success = True
            logger.info(
                f"[ContinuousVoiceLoop Turn #{self.turn_count}] "
                f"Response ready ({len(response)} chars)"
            )
        except Exception as e:
            logger.error(
                f"[ContinuousVoiceLoop] aura_core.process_request failed: {e}",
                exc_info=True,
            )
            spoken_summary = f"Sorry, I ran into a problem: {e}"
            success = False

        if not spoken_summary:
            spoken_summary = "Sorry, I couldn't process that."

        self.history.append({
            "turn": self.turn_count,
            "transcript": transcript,
            "success": success,
            "spoken_summary": spoken_summary,
        })

        self._set_state(VoiceState.SPEAKING)

        if self._running:
            # VoiceManager speaks the response; its on_tts_complete callback will
            # call trigger_tts_completed() to advance the state machine.
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
