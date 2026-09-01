"""
Voice Manager

Main orchestrator for the Voice System.
Coordinates all voice components: wake word, STT, VAD, TTS, and interruption handling.
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from .audio_manager import AudioManager
from .interruption_manager import (
    BargeInHandler,
    InterruptionManager,
    InterruptionReason,
    InterruptionState,
)
from .models import (
    ConversationSession,
    ConversationState,
    InterruptReason,
    VADMode,
    VoiceContext,
)
from .stt_manager import STTManager, STTProvider, STTSettings
from .tts_manager import TTSManger, TTSSpeaker, TTSSettings
from .vad import VoiceActivityDetector
from .wake_word import WakeWordManager, WakeWordProvider

logger = logging.getLogger(__name__)


class VoiceSystemError(Exception):
    """Voice system error."""

    pass


class VoiceManager:
    """
    Main orchestrator for the Voice System.

    Coordinates all voice components and manages the conversation lifecycle.
    Implements the 9-state conversation state machine.
    """

    def __init__(self, settings: dict[str, Any] | None = None):
        """
        Initialize Voice Manager.

        Args:
            settings: Voice system settings dictionary
        """
        self.settings = self._default_settings(settings)

        # State tracking
        self.state = ConversationState.IDLE
        self.session = None
        self._lock = threading.RLock()

        # Components
        self.audio_manager = AudioManager()
        self.vad = VoiceActivityDetector(
            mode=VADMode(self.settings["vad_mode"]),
            silence_threshold=self.settings["silence_threshold"],
            energy_threshold=self.settings["energy_threshold"],
            silence_duration=self.settings.get("silence_duration", 0.8),
        )
        self.wake_word = WakeWordManager(
            provider=WakeWordProvider(self.settings["wake_word_provider"]),
            sensitivity=self.settings["wake_word_sensitivity"],
            phrase_list=self.settings["wake_word_phrases"],
        )
        self.stt_manager = STTManager(STTSettings(**self.settings["stt_settings"]))
        self.tts_manager = TTSManger(TTSSettings(**self.settings["tts_settings"]))
        self.interruption_manager = InterruptionManager(
            enable_interruptibility=self.settings["enable_interruptibility"],
            silence_threshold=self.settings["silence_threshold"],
            energy_threshold=self.settings["energy_threshold"],
        )

        # Barge-in handler
        self.barge_in_handler = BargeInHandler(
            vad_callback=self._on_speech_start,
            on_interrupt=self._on_interrupt,
            on_resume=self._on_resume,
        )

        # Event callbacks
        self.on_state_change: Callable[[ConversationState], None] | None = None
        self.on_wake_word_detected: Callable[[str], None] | None = None
        self.on_stt_result: Callable[[VoiceContext], None] | None = None
        self.on_stt_partial: Callable[[str, str], None] | None = None
        self.on_tts_start: Callable[[str], None] | None = None
        self.on_tts_complete: Callable[[], None] | None = None
        self.on_error: Callable[[str], None] | None = None

        # Setup callbacks
        self._setup_callbacks()

        # Turn state tracking
        self._speech_started_in_turn = False
        self._active_listening_start_time = 0.0

        logger.info("Voice Manager initialized")

    def _default_settings(self, settings: dict[str, Any] | None) -> dict[str, Any]:
        """Get default settings."""
        if settings is None:
            settings = {}

        provider_env = os.getenv("STT_PROVIDER", "groq").lower()
        if provider_env in ("groq", "whisper-turbo", "whisper_turbo"):
            stt_prov = STTProvider.GROQ.value
        elif provider_env in ("faster_whisper", "local", "whisper", "cuda"):
            stt_prov = STTProvider.FASTER_WHISPER.value
        elif provider_env in ("google", "gtts"):
            stt_prov = STTProvider.GOOGLE.value
        else:
            stt_prov = STTProvider.GROQ.value

        stt_lang = os.getenv("STT_LANGUAGE", "en")

        defaults = {
            "vad_mode": VADMode.BOTH.value,
            "silence_threshold": 0.9,
            "silence_duration": 0.9,
            "energy_threshold": 0.005,
            "wake_word_provider": WakeWordProvider.AURA.value,
            "wake_word_sensitivity": 0.5,
            "wake_word_phrases": ["aura", "hey aura"],
            "stt_settings": {
                "provider": stt_prov,
                "language": stt_lang,
                "sample_rate": 16000,
                "model_size": "small",
                "verbose": False,
                "chunk_size": 20,
                "processing_delay_ms": 50,
                "max_alternatives": 1,
            },
            "tts_settings": {
                "speaker": os.getenv("TTS_SPEAKER", TTSSpeaker.EDGE_TTS.value),
                "fallback_speaker": TTSSpeaker.PIPER.value,
                "voice": os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural"),
                "rate": float(os.getenv("TTS_RATE", "1.0")),
                "pitch": 1.0,
                "volume": 1.0,
                "streaming": True,
                "interruptible": True,
            },
            "enable_interruptibility": True,
        }

        # Merge settings
        result = defaults.copy()
        result.update(settings)
        return result

    def _setup_callbacks(self) -> None:
        """Setup callbacks for all components."""
        # VAD callbacks
        self.vad.on_speech_start = self._on_speech_start
        self.vad.on_speech_end = self._on_speech_end

        # Wake word callbacks
        self.wake_word.on_wake_word_detected = self._on_wake_word_detected
        self.wake_word.on_error = self._on_wake_word_error

        # STT callbacks — use set_callbacks() so callbacks persist through lazy init
        if hasattr(self.stt_manager, "set_callbacks"):
            self.stt_manager.set_callbacks(
                partial=self._on_stt_partial,
                final=self._on_stt_final,
            )

        # TTS callbacks — use set_callbacks() so they are stored and applied
        # when the engine is lazily created, even if it doesn't exist yet.
        if hasattr(self.tts_manager, "set_callbacks"):
            self.tts_manager.set_callbacks(
                complete=self._on_tts_complete,
                interrupt=self._on_tts_interrupt,
            )

        # Interruption callbacks
        self.interruption_manager.on_interrupt_start = self._on_interrupt_start
        self.interruption_manager.on_interrupt_end = self._on_interrupt_end

    def start(self) -> bool:
        """Start voice system."""
        with self._lock:
            try:
                # Initialize wake word
                if not self.wake_word.initialize():
                    logger.error("Failed to initialize wake word")
                    return False

                # Activate wake word
                if not self.wake_word.activate():
                    logger.error("Failed to activate wake word")
                    return False

                # Start audio manager
                input_device = self.audio_manager.get_default_input_device()
                output_device = self.audio_manager.get_default_output_device()

                if not input_device or not output_device:
                    logger.error("No audio devices found")
                    return False

                self.audio_manager.select_input_device(input_device.device_id)
                self.audio_manager.select_output_device(output_device.device_id)

                logger.info("Voice system started")
                self._update_state(ConversationState.IDLE)
                return True

            except Exception as e:
                logger.error(f"Error starting voice system: {e}")
                if self.on_error:
                    self.on_error(f"Failed to start: {e}")
                return False

    def stop(self) -> None:
        """Stop voice system."""
        with self._lock:
            try:
                # Deactivate wake word
                self.wake_word.deactivate()

                # Stop audio
                self.audio_manager.stop_recording()
                self.audio_manager.stop_playback()

                # Reset components
                self.stt_manager.reset()
                self.session = None

                logger.info("Voice system stopped")

            except Exception as e:
                logger.error(f"Error stopping voice system: {e}")

    def activate(self) -> bool:
        """Activate wake word listening."""
        logger.info("[VoiceManager] ACTIVATING")
        with self._lock:
            if self.state == ConversationState.WAKE_LISTENING:
                return True

            # If actively speaking, do not interrupt in-flight TTS playback
            if self.state == ConversationState.SPEAKING:
                logger.warning(f"Cannot activate wake-word while speaking in state: {self.state.value}")
                return False

            # Safe recovery from completed, thinking, paused, interrupted, error, or dormant states
            if self.state != ConversationState.IDLE:
                logger.info(f"Voice system recovering to IDLE from state: {self.state.value}")
                self._update_state(ConversationState.IDLE)

            try:
                if not self.wake_word.activate():
                    logger.error("[WAKE] Listener active: FAIL")
                    return False
                if not self._ensure_input_recording():
                    logger.error("[MIC] Stream opened: FAIL")
                    return False
                
                logger.info("[MIC] Stream opened: PASS")
                logger.info("[WAKE] Listener active: PASS")
                self._update_state(ConversationState.WAKE_LISTENING)
                return True

            except Exception as e:
                logger.error(f"Error activating voice system: {e}")
                if self.on_error:
                    self.on_error(f"Failed to activate: {e}")
                return False

    def deactivate(self) -> None:
        """Deactivate voice system."""
        with self._lock:
            self.wake_word.deactivate()
            self.audio_manager.stop_recording()
            self._update_state(ConversationState.IDLE)

    def _on_audio_chunk(self, chunk: bytes) -> None:
        """Route microphone audio through the active voice state machine."""
        self.process_audio(chunk, 16000)

    def _ensure_input_recording(self) -> bool:
        """Ensure the microphone stream is owned and capture is enabled."""
        if self.audio_manager.is_recording():
            if hasattr(self.audio_manager, "enable_capture"):
                self.audio_manager.enable_capture()
            return True

        ok = self.audio_manager.start_recording(self._on_audio_chunk)
        if ok and hasattr(self.audio_manager, "enable_capture"):
            self.audio_manager.enable_capture()
        return ok

    def process_audio(self, audio_data: bytes, sample_rate: int) -> None:
        """
        Process audio data through the voice system.

        Args:
            audio_data: Audio data
            sample_rate: Sample rate
        """
        with self._lock:
            try:
                # Update is_speaking on wake word engine
                if self.wake_word and getattr(self.wake_word, "engine", None) is not None:
                    self.wake_word.engine.is_speaking = (self.state == ConversationState.SPEAKING)

                # Process wake word detection during WAKE_LISTENING or SPEAKING (barge-in) state
                if self.state in (ConversationState.WAKE_LISTENING, ConversationState.SPEAKING):
                    self.wake_word.process_audio(audio_data, sample_rate)

                # Process VAD
                vad_state, energy = self.vad.process_audio(audio_data, sample_rate)
                if energy is not None:
                    try:
                        from gui.signals import app_signals
                        # Logarithmic/power scaling so normal conversational speech fills 40%-90% height
                        norm_level = min(1.0, max(0.0, float((energy * 35.0) ** 0.75)))
                        app_signals.voice_level.emit(norm_level)
                    except Exception:
                        pass

                # Update barge-in handler
                self.barge_in_handler.set_aura_speaking(
                    self.state == ConversationState.SPEAKING
                )

                # Process STT if active listening
                if self.state == ConversationState.ACTIVE_LISTENING:
                    self.stt_manager.process_audio(audio_data)

                    # Timeout check: if user didn't start speaking for 8.0 seconds after wake word
                    if (
                        not self._speech_started_in_turn
                        and (time.time() - self._active_listening_start_time > 8.0)
                    ):
                        logger.info("[VoiceManager] Active listening timed out waiting for speech (8.0s)")
                        self._finalize_stt()

                # Optional direct VAD-onset barge-in (opt-in via .env for headphones / AEC hardware)
                enable_vad_barge = os.getenv("ENABLE_VAD_BARGE_IN", "false").lower() == "true"
                if enable_vad_barge and self.barge_in_handler.check_for_interrupt():
                    logger.info("[VoiceManager] User VAD speech-onset interrupt detected")
                    self.interruption_manager.start_interrupt(
                        InterruptionReason.USER_INTERRUPT
                    )
                    self._handle_interrupt()

            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                if self.on_error:
                    self.on_error(f"Audio processing error: {e}")

    def _on_wake_word_detected(self, wake_word: str) -> None:
        """Handle wake word detection."""
        logger.info(f"[WAKE] Wake detected: PASS ({wake_word})")

        # Barge-in / Interruption: if currently speaking, thinking, or executing, halt immediately
        if self.state in (ConversationState.SPEAKING, ConversationState.THINKING, ConversationState.EXECUTING):
            logger.info(f"[VoiceManager] Interruption triggered during {self.state.name}! Halting current action.")
            self.tts_manager.stop()
            self._current_speaking_text = ""

        # Play immediate non-blocking audio earcon chime feedback
        try:
            from .earcon_player import EarconPlayer
            EarconPlayer.play_wake_chime()
        except Exception:
            pass

        if self.on_wake_word_detected:
            self.on_wake_word_detected(wake_word)

        # Start active listening
        self._start_active_listening()

    def _on_wake_word_error(self, error: str) -> None:
        """Handle wake word engine error."""
        logger.error(f"[VoiceManager] Wake word error: {error}")
        if self.on_error:
            self.on_error(error)

    def _start_active_listening(self) -> None:
        """Start active listening for commands."""
        try:
            # Start STT
            if not self.stt_manager.initialize():
                logger.error("Failed to initialize STT")
                return

            if not self._ensure_input_recording():
                logger.error("Failed to start audio recording")
                return

            # Reset VAD and STT buffer so wake word audio/silence isn't treated as the command
            self.vad.reset()
            self.stt_manager.reset()
            self._speech_started_in_turn = False
            self._active_listening_start_time = time.time()

            # Initialize session
            self.session = ConversationSession()
            self.session.start()

            # Update state
            self._update_state(ConversationState.ACTIVE_LISTENING)

            logger.info("[STT] Audio captured: PASS")

        except Exception as e:
            logger.error(f"Error starting active listening: {e}")
            if self.on_error:
                self.on_error(f"Failed to start active listening: {e}")

    def _on_speech_start(self) -> None:
        """Called when speech starts (from VAD)."""
        logger.debug("Speech start detected")
        if self.state == ConversationState.ACTIVE_LISTENING:
            self._speech_started_in_turn = True
        if self.state == ConversationState.SPEAKING:
            enable_vad_barge = os.getenv("ENABLE_VAD_BARGE_IN", "false").lower() == "true"
            if enable_vad_barge and self.barge_in_handler:
                self.barge_in_handler.on_vad_speech_start()

    def _on_speech_end(self) -> None:
        """Called when speech ends (from VAD)."""
        logger.debug("Speech end detected")
        if self.barge_in_handler:
            self.barge_in_handler.on_vad_speech_end()
        if self.state == ConversationState.ACTIVE_LISTENING:
            # If user hasn't started speaking their command yet and less than 1.0s has passed since wake trigger, ignore wake-word tail
            if not self._speech_started_in_turn and (time.time() - self._active_listening_start_time < 1.0):
                logger.debug("Ignoring speech end right after wake trigger before command speech")
                return
            self._finalize_stt()

    def _finalize_stt(self) -> None:
        """Finalize STT and transition to thinking state."""
        try:
            # Get final transcript
            transcript = self.stt_manager.finalize()

            if not transcript:
                logger.warning("No transcript generated")
                transcript = ""

            # Create voice context
            context = VoiceContext(
                transcript=transcript,
                confidence=1.0 if transcript else 0.0,
                duration=time.time() - self._active_listening_start_time,
            )
            context.provider = self.stt_manager.settings.provider.value

            with self._lock:
                self._update_state(ConversationState.THINKING)
                if self.session:
                    self.session.update_state(ConversationState.THINKING)

            logger.info("[STT] Transcription: PASS")
            self.stt_manager.reset()

            if self.on_stt_result:
                self.on_stt_result(context)

        except Exception as e:
            logger.error(f"Error finalizing STT: {e}")
            if self.on_error:
                self.on_error(f"STT finalization error: {e}")

    def speak(self, text: str) -> bool:
        """
        Start speaking text with live barge-in support.

        Args:
            text: Text to speak

        Returns:
            True if successful
        """
        try:
            # Track currently spoken text for self-trigger guarding
            self._current_speaking_text = text or ""

            # Add text to TTS (lazy initialization happens inside add_text if needed)
            if not self.tts_manager.add_text(text):
                logger.error("Failed to add text to TTS")
                return False

            # Start speaking
            if not self.tts_manager.speak():
                logger.error("Failed to start speaking")
                return False

            # Update state to SPEAKING
            self._update_state(ConversationState.SPEAKING)
            if self.session:
                self.session.update_state(ConversationState.SPEAKING)

            # Ensure microphone capture remains active so wake-word / barge-in can listen
            if self.audio_manager:
                if not self.audio_manager.is_recording():
                    self._ensure_input_recording()
                elif hasattr(self.audio_manager, "enable_capture"):
                    self.audio_manager.enable_capture()

            logger.info(f"[TTS] Piper playback: PASS ({text})")

            if self.on_tts_start:
                self.on_tts_start(text)

            return True

        except Exception as e:
            logger.error(f"Error speaking: {e}")
            if self.on_error:
                self.on_error(f"Speaking error: {e}")
            return False

    def interrupt(self) -> None:
        """Interrupt current speech or conversation."""
        try:
            # Stop TTS immediately
            self.tts_manager.stop()
            self._current_speaking_text = ""

            # Re-enable microphone capture if needed
            if self.audio_manager and hasattr(self.audio_manager, "enable_capture"):
                self.audio_manager.enable_capture()

            # Update state
            self._update_state(ConversationState.INTERRUPTED)
            if self.session:
                self.session.update_state(ConversationState.INTERRUPTED)

            # Record interruption
            self.interruption_manager.start_interrupt(InterruptionReason.USER_INTERRUPT)

            logger.info("Interrupted")

        except Exception as e:
            logger.error(f"Error interrupting: {e}")
            if self.on_error:
                self.on_error(f"Interrupt error: {e}")

    def _handle_interrupt(self) -> None:
        """Handle interruption event."""
        try:
            # Stop current activity and start listening
            self.interrupt()
            self._start_active_listening()

        except Exception as e:
            logger.error(f"Error handling interruption: {e}")

    def _on_interrupt_start(self, reason: InterruptReason) -> None:
        """Called when interruption starts."""
        logger.info(f"Interruption started: {reason.value}")

    def _on_interrupt_end(self) -> None:
        """Called when interruption ends."""
        logger.info("Interruption ended")
        self.interruption_manager.end_interrupt()

    def _on_interrupt(self, reason: str) -> None:
        """Called when user interrupts Aura."""
        logger.info(f"User interrupt detected: {reason}")
        self.interruption_manager.start_interrupt(InterruptionReason.USER_INTERRUPT)
        self.interrupt()
        self._start_active_listening()

    def _on_resume(self) -> None:
        """Called when user speech ends."""
        logger.debug("User speech ended, Aura can resume")
        if self.interruption_manager.state == InterruptionState.INTERRUPTED:
            self.interruption_manager.end_interrupt()

    def _on_stt_partial(self, confirmed: str, tentative: str) -> None:
        """Called when partial STT result is received."""
        if self.on_stt_partial:
            context = VoiceContext(transcript="")
            context.update_partial(confirmed, tentative)
            self.on_stt_partial(context)

    def _on_stt_final(self, text: str, duration: float) -> None:
        """Called when final STT result is received."""
        logger.info(f"Final transcript: {text}")
        if self.on_stt_result:
            context = VoiceContext(transcript=text)
            self.on_stt_result(context)

    def _on_tts_complete(self) -> None:
        """Called when TTS completes."""
        logger.info("[MIC] Buffer flushed: PASS")
        self._current_speaking_text = ""

        # Transition to next state
        self._update_state(ConversationState.IDLE)
        if self.session:
            self.session.update_state(ConversationState.IDLE)

        if self.on_tts_complete:
            self.on_tts_complete()

    def _on_tts_interrupt(self) -> None:
        """Called when TTS is interrupted."""
        logger.info("TTS interrupted")
        self._update_state(ConversationState.INTERRUPTED)

    def _update_state(self, new_state: ConversationState) -> None:
        """Update conversation state."""
        old_state = self.state
        self.state = new_state

        logger.info(f"State changed: {old_state.value} -> {new_state.value}")

        if self.on_state_change:
            self.on_state_change(new_state)

    def get_state(self) -> ConversationState:
        """Get current state."""
        return self.state

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        return {
            "state": self.state.value,
            "session": self.session.to_dict() if self.session else None,
            "vad": self.vad.get_stats(),
            "wake_word": self.wake_word.get_status(),
            "stt": self.stt_manager.get_status(),
            "tts": self.tts_manager.get_status(),
            "interruption": self.interruption_manager.get_stats(),
            "audio": self.audio_manager.get_audio_stats(),
        }

    def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up voice system")

        self.stop()
        self.audio_manager.cleanup()
        self.wake_word.engine.cleanup() if self.wake_word.engine else None
        self.vad.reset()
        self.interruption_manager.reset()
