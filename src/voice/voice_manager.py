"""
Voice Manager

Main orchestrator for the Voice System.
Coordinates all voice components: wake word, STT, VAD, TTS, and interruption handling.
"""


import logging
from typing import Optional, Callable, Dict, Any, List, Tuple
from enum import Enum
from datetime import datetime
import threading

from .models import (
    VoiceContext, ConversationState, ConversationSession,
    WakeWordSettings, STTSettings, TTSSettings,
    InterruptReason, VADMode
)
from .audio_manager import AudioManager
from .vad import VoiceActivityDetector, VADState
from .wake_word import WakeWordManager, WakeWordProvider
from .stt_manager import STTManager, STTProvider
from .tts_manager import TTSManger, TTSSpeaker
from .interruption_manager import (
    InterruptionManager, BargeInHandler,
    InterruptionReason, InterruptionState, InterruptionPolicy
)


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
    
    def __init__(
        self,
        settings: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Voice Manager.
        
        Args:
            settings: Voice system settings dictionary
        """
        self.settings = self._default_settings(settings)
        
        # State tracking
        self.state = ConversationState.IDLE
        self.session = None
        self._lock = threading.Lock()
        
        # Components
        self.audio_manager = AudioManager()
        self.vad = VoiceActivityDetector(
            mode=VADMode(self.settings['vad_mode']),
            silence_threshold=self.settings['silence_threshold'],
            energy_threshold=self.settings['energy_threshold']
        )
        self.wake_word = WakeWordManager(
            provider=WakeWordProvider(self.settings['wake_word_provider']),
            sensitivity=self.settings['wake_word_sensitivity'],
            phrase_list=self.settings['wake_word_phrases']
        )
        self.stt_manager = STTManager(STTSettings(**self.settings['stt_settings']))
        self.tts_manager = TTSManger(TTSSettings(**self.settings['tts_settings']))
        self.interruption_manager = InterruptionManager(
            enable_interruptibility=self.settings['enable_interruptibility'],
            silence_threshold=self.settings['silence_threshold'],
            energy_threshold=self.settings['energy_threshold']
        )
        
        # Barge-in handler
        self.barge_in_handler = BargeInHandler(
            vad_callback=self._on_vad_speech_start,
            on_interrupt=self._on_interrupt,
            on_resume=self._on_resume
        )
        
        # Event callbacks
        self.on_state_change: Optional[Callable[[ConversationState], None]] = None
        self.on_wake_word_detected: Optional[Callable[[str], None]] = None
        self.on_stt_result: Optional[Callable[[VoiceContext], None]] = None
        self.on_tts_start: Optional[Callable[[str], None]] = None
        self.on_tts_complete: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Setup callbacks
        self._setup_callbacks()
        
        logger.info("Voice Manager initialized")
    
    def _default_settings(self, settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get default settings."""
        if settings is None:
            settings = {}
        
        defaults = {
            'vad_mode': VADMode.BOTH.value,
            'silence_threshold': 1.0,
            'energy_threshold': 0.1,
            'wake_word_provider': WakeWordProvider.LOCAL.value,
            'wake_word_sensitivity': 0.5,
            'wake_word_phrases': ['aura', 'hey aura'],
            'stt_settings': {
                'provider': STTProvider.WHISPER.value,
                'language': 'en-US',
                'sample_rate': 16000,
                'model_size': 'base',
                'verbose': False,
                'chunk_size': 20,
                'processing_delay_ms': 50,
                'max_alternatives': 1
            },
            'tts_settings': {
                'speaker': TTSSpeaker.EDGE_TTS.value,
                'voice': None,
                'rate': 1.0,
                'pitch': 1.0,
                'volume': 1.0,
                'streaming': True,
                'interruptible': True
            },
            'enable_interruptibility': True
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
        
        # STT callbacks
        self.stt_manager.engine._partial_callback = self._on_stt_partial
        self.stt_manager.engine._final_callback = self._on_stt_final
        
        # TTS callbacks
        self.tts_manager.engine._playback_complete_callback = self._on_tts_complete
        self.tts_manager.engine._interrupt_callback = self._on_tts_interrupt
        
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
        with self._lock:
            if self.state != ConversationState.IDLE:
                logger.warning(f"Voice system not in IDLE state, current: {self.state}")
                return False
            
            try:
                self.wake_word.activate()
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
            self._update_state(ConversationState.IDLE)
    
    def process_audio(self, audio_data: bytes, sample_rate: int) -> None:
        """
        Process audio data through the voice system.
        
        Args:
            audio_data: Audio data
            sample_rate: Sample rate
        """
        with self._lock:
            try:
                # Process wake word detection
                if self.state == ConversationState.WAKE_LISTENING:
                    self.wake_word.process_audio(audio_data, sample_rate)
                
                # Process VAD
                vad_state, energy = self.vad.process_audio(audio_data, sample_rate)
                
                # Update barge-in handler
                self.barge_in_handler.set_aura_speaking(self.state == ConversationState.SPEAKING)
                
                # Process STT if active listening
                if self.state == ConversationState.ACTIVE_LISTENING:
                    self.stt_manager.process_audio(audio_data)
                
                # Check for user interruption
                if self.barge_in_handler.check_for_interrupt():
                    logger.info("User interrupt detected")
                    self.interruption_manager.start_interrupt(InterruptionReason.USER_INTERRUPT)
                    self._handle_interrupt()
                
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                if self.on_error:
                    self.on_error(f"Audio processing error: {e}")
    
    def _on_wake_word_detected(self, wake_word: str) -> None:
        """Called when wake word is detected."""
        logger.info(f"Wake word detected: {wake_word}")
        
        if self.on_wake_word_detected:
            self.on_wake_word_detected(wake_word)
        
        # Start active listening
        self._start_active_listening()
    
    def _start_active_listening(self) -> None:
        """Start active listening for commands."""
        try:
            # Start STT
            if not self.stt_manager.initialize():
                logger.error("Failed to initialize STT")
                return
            
            # Start audio recording
            def on_audio_chunk(chunk: bytes) -> None:
                self.process_audio(chunk, 16000)
            
            if not self.audio_manager.start_recording(on_audio_chunk):
                logger.error("Failed to start audio recording")
                return
            
            # Initialize session
            self.session = ConversationSession()
            self.session.start()
            
            # Update state
            self._update_state(ConversationState.ACTIVE_LISTENING)
            
            logger.info("Started active listening")
            
        except Exception as e:
            logger.error(f"Error starting active listening: {e}")
            if self.on_error:
                self.on_error(f"Failed to start active listening: {e}")
    
    def _on_speech_start(self) -> None:
        """Called when speech starts (from VAD)."""
        logger.debug("Speech start detected")
    
    def _on_speech_end(self) -> None:
        """Called when speech ends (from VAD)."""
        logger.debug("Speech end detected")
        
        if self.state == ConversationState.ACTIVE_LISTENING:
            self._finalize_stt()
    
    def _finalize_stt(self) -> None:
        """Finalize STT and transition to thinking state."""
        try:
            # Get final transcript
            transcript = self.stt_manager.finalize()
            
            if not transcript:
                logger.warning("No transcript generated")
                return
            
            # Create voice context
            context = VoiceContext(transcript=transcript)
            context.processing_time_ms = 100.0  # Placeholder
            context.provider = self.stt_manager.settings.provider.value
            
            logger.info(f"Final transcript: {transcript}")
            
            if self.on_stt_result:
                self.on_stt_result(context)
            
            # Transition to thinking
            self._update_state(ConversationState.THINKING)
            self.session.update_state(ConversationState.THINKING)
            
            # Stop recording
            self.audio_manager.stop_recording()
            self.stt_manager.reset()
            
        except Exception as e:
            logger.error(f"Error finalizing STT: {e}")
            if self.on_error:
                self.on_error(f"STT finalization error: {e}")
    
    def speak(self, text: str) -> bool:
        """
        Start speaking text.
        
        Args:
            text: Text to speak
            
        Returns:
            True if successful
        """
        try:
            # Add text to TTS
            if not self.tts_manager.add_text(text):
                logger.error("Failed to add text to TTS")
                return False
            
            # Start speaking
            if not self.tts_manager.speak():
                logger.error("Failed to start speaking")
                return False
            
            # Update state
            self._update_state(ConversationState.SPEAKING)
            self.session.update_state(ConversationState.SPEAKING)
            
            logger.info(f"Speaking: {text}")
            
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
            # Stop TTS
            self.tts_manager.stop()
            
            # Stop recording if active listening
            if self.state == ConversationState.ACTIVE_LISTENING:
                self.audio_manager.stop_recording()
                self.stt_manager.reset()
            
            # Update state
            self._update_state(ConversationState.INTERRUPTED)
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
            # Stop current activity
            self.interrupt()
            
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
    
    def _on_resume(self) -> None:
        """Called when user speech ends."""
        logger.debug("User speech ended, Aura can resume")
        if self.interruption_manager.state == InterruptionState.INTERRUPTED:
            self.interruption_manager.end_interrupt()
    
    def _on_stt_partial(self, text: str, duration: float) -> None:
        """Called when partial STT result is received."""
        logger.debug(f"Partial transcript: {text}")
    
    def _on_stt_final(self, text: str, duration: float) -> None:
        """Called when final STT result is received."""
        logger.info(f"Final transcript: {text}")
        if self.on_stt_result:
            context = VoiceContext(transcript=text)
            self.on_stt_result(context)
    
    def _on_tts_complete(self) -> None:
        """Called when TTS completes."""
        logger.info("TTS complete")
        
        if self.on_tts_complete:
            self.on_tts_complete()
        
        # Transition to next state
        self._update_state(ConversationState.IDLE)
        self.session.update_state(ConversationState.IDLE)
    
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        return {
            'state': self.state.value,
            'session': self.session.to_dict() if self.session else None,
            'vad': self.vad.get_stats(),
            'wake_word': self.wake_word.get_status(),
            'stt': self.stt_manager.get_status(),
            'tts': self.tts_manager.get_status(),
            'interruption': self.interruption_manager.get_stats(),
            'audio': self.audio_manager.get_audio_stats()
        }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up voice system")
        
        self.stop()
        self.audio_manager.cleanup()
        self.wake_word.engine.cleanup() if self.wake_word.engine else None
        self.vad.reset()
        self.interruption_manager.reset()
