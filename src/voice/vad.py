"""
Voice Activity Detection

Detects when speech starts and ends using voice activity detection algorithms.
Supports silence threshold, energy threshold, and hybrid approaches.
"""

import logging
from collections import deque
from collections.abc import Callable
from enum import Enum

import numpy as np

from .models import VADMode

logger = logging.getLogger(__name__)


class VADState(Enum):
    """VAD state machine."""

    IDLE = "idle"  # No speech detected
    SPEECH_START = "speech_start"  # Speech detected
    SPEECH_END = "speech_end"  # Speech ended
    ERROR = "error"  # Error occurred


class VoiceActivityDetector:
    """
    Voice Activity Detection (VAD) implementation.

    Detects speech activity in audio streams and signals when speech starts
    and ends. Supports multiple detection modes.
    """

    def __init__(
        self,
        mode: VADMode = VADMode.BOTH,
        silence_threshold: float = 1.8,
        energy_threshold: float = 0.005,
        window_size_ms: int = 30,
        min_speech_duration: float = 0.3,
        max_speech_duration: float = 30.0,
        silence_duration: float = 1.8,
    ):
        """
        Initialize VAD detector.

        Args:
            mode: Detection mode (SILENCE, ENERGY, or HYBRID)
            silence_threshold: Duration of silence to trigger speech end (seconds)
            energy_threshold: Minimum energy level to detect speech
            window_size_ms: Size of analysis window in milliseconds
            min_speech_duration: Minimum speech duration to consider valid
            max_speech_duration: Maximum speech duration before forcing end
            silence_duration: Duration of silence to trigger speech end
        """
        self.mode = mode
        self.silence_threshold = silence_threshold
        self.energy_threshold = energy_threshold
        self.window_size_ms = window_size_ms
        self.min_speech_duration = min_speech_duration
        self.max_speech_duration = max_speech_duration
        self.silence_duration = silence_duration

        # State tracking
        self.state = VADState.IDLE
        self.speech_start_time = None
        self.silence_timer = 0.0
        self.silence_buffer = deque(
            maxlen=int(silence_threshold / (window_size_ms / 1000.0))
        )
        self.current_energy = 0.0
        self.noise_floor = 0.0
        self.noise_floor_initialized = False

        # Statistics
        self.speech_count = 0
        self.total_speech_duration = 0.0
        self.total_silence_duration = 0.0

        # Callbacks
        self.on_speech_start: Callable[[], None] | None = None
        self.on_speech_end: Callable[[], None] | None = None
        self.on_speech_detected: Callable[[float], None] | None = (
            None  # Pass speech duration
        )

        logger.info(f"VAD initialized with mode: {mode.value}")

    def process_audio(
        self, audio_data: bytes, sample_rate: int, timestamp: float | None = None
    ) -> tuple[VADState, float]:
        """
        Process audio data and detect speech activity.

        Args:
            audio_data: Audio data bytes
            sample_rate: Sample rate of audio
            timestamp: Optional timestamp for processing

        Returns:
            Tuple of (VADState, energy_level)
        """
        if timestamp is None:
            timestamp = 0.0

        # Convert bytes to numpy array
        audio = np.frombuffer(audio_data, dtype=np.int16)

        # Calculate energy
        self.current_energy = self._calculate_energy(audio)

        # Process based on state
        if self.state == VADState.IDLE:
            return self._process_idle(audio)
        elif self.state == VADState.SPEECH_START:
            return self._process_speech_start(audio)
        elif self.state == VADState.SPEECH_END:
            return self._process_speech_end(audio)
        elif self.state == VADState.ERROR:
            return VADState.ERROR, self.current_energy

        return VADState.IDLE, self.current_energy

    def _process_idle(self, audio: np.ndarray) -> tuple[VADState, float]:
        """Process IDLE state - looking for speech start."""
        # Update dynamic noise floor when idle
        if not self.noise_floor_initialized:
            self.noise_floor = self.current_energy
            self.noise_floor_initialized = True
        else:
            # Exponential moving average for noise floor
            self.noise_floor = 0.95 * self.noise_floor + 0.05 * self.current_energy

        # Dynamic threshold is at least the base threshold, or 2x the noise floor
        dynamic_threshold = max(self.energy_threshold, self.noise_floor * 2.0)

        if self.current_energy > dynamic_threshold:
            self.state = VADState.SPEECH_START
            self.speech_start_time = timestamp()   # Fix: was 0.0, causing ~1.78B-second garbage duration
            self.silence_timer = 0.0
            self.silence_buffer.clear()

            if self.on_speech_start:
                self.on_speech_start()

            logger.debug(f"Speech start detected (energy: {self.current_energy:.4f}, noise: {self.noise_floor:.4f}, thresh: {dynamic_threshold:.4f})")

        return VADState.IDLE, self.current_energy

    def _process_speech_start(self, audio: np.ndarray) -> tuple[VADState, float]:
        """Process SPEECH_START state - tracking ongoing speech."""
        speech_duration = 0.0

        # Check for speech end conditions
        should_end = False

        # Use hysteresis: lower threshold while speech is ongoing so soft syllables don't trigger silence
        dynamic_threshold = max(self.energy_threshold * 0.7, self.noise_floor * 1.5)

        # Hard ceiling: force end if max_speech_duration exceeded.
        # Previously max_speech_duration was stored but never enforced, so
        # a VAD session could run indefinitely (observed: ~94 seconds).
        if self.speech_start_time is not None:
            elapsed = timestamp() - self.speech_start_time
            if elapsed >= self.max_speech_duration:
                logger.warning(
                    f"[VAD] max_speech_duration ({self.max_speech_duration}s) exceeded "
                    f"after {elapsed:.1f}s — forcing speech end"
                )
                self._trigger_speech_end(audio)
                return VADState.SPEECH_END, self.current_energy

        if self.mode == VADMode.SILENCE_THRESHOLD:
            should_end = self._check_silence(audio)
        elif self.mode == VADMode.ENERGY_THRESHOLD:
            should_end = self.current_energy < dynamic_threshold
        elif self.mode in (VADMode.HYBRID, VADMode.BOTH):
            should_end = (
                self._check_silence(audio)
                or self.current_energy < dynamic_threshold
            )

        # Update silence buffer
        self.silence_buffer.append(self.current_energy)

        # Check if silence threshold reached
        if should_end:
            self.silence_timer += self.window_size_ms / 1000.0

            if self.silence_timer >= self.silence_duration:
                self._trigger_speech_end(audio)
                return VADState.SPEECH_END, self.current_energy
        else:
            # Reset on genuine signal so only *continuous* silence counts.
            # Without this reset, silence accumulates across active speech frames.
            self.silence_timer = 0.0

        speech_duration = 0.0
        if self.speech_start_time is not None:
            speech_duration = timestamp() - self.speech_start_time  # now correct

        if self.on_speech_detected:
            self.on_speech_detected(speech_duration)

        return VADState.SPEECH_START, self.current_energy

    def _process_speech_end(self, audio: np.ndarray) -> tuple[VADState, float]:
        """Process SPEECH_END state - handling post-speech silence."""
        speech_duration = 0.0

        # Check if energy goes above threshold (speech continues)
        if self.current_energy > self.energy_threshold:
            self.state = VADState.SPEECH_START
            self.speech_start_time = timestamp() - self._calculate_speech_duration()
            self.silence_timer = 0.0

            if self.on_speech_start:
                self.on_speech_start()

            logger.debug("Speech continued after pause")
            return VADState.SPEECH_START, self.current_energy

        # Speech ended, finalize
        self._finalize_speech()
        return VADState.IDLE, self.current_energy

    def _check_silence(self, audio: np.ndarray) -> bool:
        """
        Check if audio segment indicates silence.

        Returns:
            True if silence detected
        """
        if len(self.silence_buffer) < 3:
            return False

        dynamic_threshold = max(self.energy_threshold, self.noise_floor * 1.5)
        # Check if most recent energy values are below threshold
        energy_values = list(self.silence_buffer)
        below_threshold = sum(1 for e in energy_values if e < dynamic_threshold)

        return below_threshold >= len(energy_values) - 1

    def _calculate_speech_duration(self) -> float:
        """Calculate total speech duration in current segment."""
        if self.speech_start_time is None:
            return 0.0

        total_duration = timestamp() - self.speech_start_time

        # Apply minimum speech duration
        if total_duration < self.min_speech_duration:
            return 0.0

        return total_duration

    def _trigger_speech_end(self, audio: np.ndarray):
        """Trigger speech end event."""
        self.state = VADState.SPEECH_END

        if self.on_speech_end:
            self.on_speech_end()

        logger.debug("Speech end detected")

    def _finalize_speech(self):
        """Finalize speech event and update statistics."""
        speech_duration = self._calculate_speech_duration()

        if speech_duration >= self.min_speech_duration:
            self.speech_count += 1
            self.total_speech_duration += speech_duration

            if self.on_speech_detected:
                self.on_speech_detected(speech_duration)

            logger.info(
                f"Speech detected: {speech_duration:.2f}s (count: {self.speech_count})"
            )

        # Reset state
        self.state = VADState.IDLE
        self.speech_start_time = None
        self.silence_timer = 0.0
        self.silence_buffer.clear()

    def _calculate_energy(self, audio: np.ndarray) -> float:
        """
        Calculate RMS energy of audio.

        Args:
            audio: Audio samples

        Returns:
            Energy level (0.0 - 1.0)
        """
        if len(audio) == 0:
            return 0.0

        # Calculate RMS
        audio_float = audio.astype(np.float32)
        rms = np.sqrt(np.mean(audio_float**2))

        # Normalize to 0-1 range (assuming 16-bit audio)
        max_amplitude = 32768
        energy = rms / max_amplitude

        return min(energy, 1.0)

    def reset(self):
        """Reset VAD state."""
        self.state = VADState.IDLE
        self.speech_start_time = None
        self.silence_timer = 0.0
        self.silence_buffer.clear()
        self.current_energy = 0.0
        self.speech_count = 0
        self.total_speech_duration = 0.0
        self.total_silence_duration = 0.0

        logger.info("VAD reset")

    def get_stats(self) -> dict:
        """Get VAD statistics."""
        return {
            "state": self.state.value,
            "current_energy": self.current_energy,
            "speech_count": self.speech_count,
            "total_speech_duration": self.total_speech_duration,
            "total_silence_duration": self.total_silence_duration,
            "silence_timer": self.silence_timer,
            "silence_buffer_size": len(self.silence_buffer),
        }

    def get_speech_duration(self) -> float:
        """Get duration of current speech segment."""
        return self._calculate_speech_duration()


def timestamp() -> float:
    """Get current timestamp in seconds."""
    import time

    return time.time()


class EnergyVAD(VoiceActivityDetector):
    """
    Simple energy-based VAD.

    Detects speech based on audio energy levels.
    """

    def __init__(
        self,
        threshold: float = 0.1,
        window_size_ms: int = 30,
        min_speech_duration: float = 0.3,
    ):
        """
        Initialize energy-based VAD.

        Args:
            threshold: Energy threshold for speech detection
            window_size_ms: Analysis window size
            min_speech_duration: Minimum speech duration
        """
        super().__init__(
            mode=VADMode.ENERGY,
            silence_threshold=min_speech_duration,
            energy_threshold=threshold,
            window_size_ms=window_size_ms,
            min_speech_duration=min_speech_duration,
        )


class SilenceVAD(VoiceActivityDetector):
    """
    Silence-based VAD.

    Detects speech end based on silence duration.
    """

    def __init__(
        self, silence_threshold: float = 1.0, min_speech_duration: float = 0.3
    ):
        """
        Initialize silence-based VAD.

        Args:
            silence_threshold: Duration of silence to trigger end
            min_speech_duration: Minimum speech duration
        """
        super().__init__(
            mode=VADMode.SILENCE,
            silence_threshold=silence_threshold,
            energy_threshold=0.01,
            window_size_ms=30,
            min_speech_duration=min_speech_duration,
        )


class HybridVAD(VoiceActivityDetector):
    """
    Hybrid VAD using both silence and energy detection.

    More robust than single-mode VAD.
    """

    def __init__(
        self,
        silence_threshold: float = 1.0,
        energy_threshold: float = 0.1,
        min_speech_duration: float = 0.3,
    ):
        """
        Initialize hybrid VAD.

        Args:
            silence_threshold: Silence duration threshold
            energy_threshold: Energy threshold
            min_speech_duration: Minimum speech duration
        """
        super().__init__(
            mode=VADMode.HYBRID,
            silence_threshold=silence_threshold,
            energy_threshold=energy_threshold,
            window_size_ms=30,
            min_speech_duration=min_speech_duration,
        )
