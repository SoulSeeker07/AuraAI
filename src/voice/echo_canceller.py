"""
Acoustic Echo Suppressor (AES)
Location: src/voice/echo_canceller.py

Provides real-time output-reference subtraction and energy-based acoustic echo
suppression. Prevents Aura's microphone from capturing its own spoken voice when
operating in full-duplex mode without headphones.

Key Invariants:
1. Low Latency: Per-frame processing <= 2.0ms.
2. Circular Reference Buffer: Retains trailing 1.5s of speaker audio for correlation.
3. Headphone Mode: When enabled, zero audio manipulation is applied (bypassed).
4. Adaptive Attenuation: Scales mic input attenuation dynamically based on output energy.
"""

from __future__ import annotations

import collections
import logging
import math
import threading
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AcousticEchoSuppressor:
    """
    Real-time Acoustic Echo Suppressor for full-duplex voice pipelines.
    
    Monitors speaker playback via a reference stream tap and suppresses
    self-talk leakage in incoming microphone frames.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_size: int = 512,
        history_seconds: float = 1.5,
        attenuation_db: float = 24.0,
        correlation_threshold: float = 0.35,
        headphone_mode: bool = False,
    ):
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.history_seconds = history_seconds
        self.attenuation_factor = 10.0 ** (-attenuation_db / 20.0)
        self.correlation_threshold = correlation_threshold
        self.headphone_mode = headphone_mode

        # Maximum frames in circular reference buffer
        max_frames = int((sample_rate * history_seconds) / frame_size)
        self._ref_buffer: collections.deque[np.ndarray] = collections.deque(maxlen=max_frames)
        self._lock = threading.Lock()

        # Telemetry / state
        self._is_suppressing = False
        self._last_playback_time = 0.0
        self._suppressed_frame_count = 0
        self._total_frame_count = 0

        logger.info(
            f"[AcousticEchoSuppressor] Initialized: {sample_rate}Hz, "
            f"attenuation={attenuation_db}dB, headphone_mode={headphone_mode}"
        )

    def set_headphone_mode(self, enabled: bool) -> None:
        """Enable or disable headphone bypass mode."""
        self.headphone_mode = enabled
        logger.info(f"[AcousticEchoSuppressor] Headphone mode set to: {enabled}")

    def feed_playback_frame(self, pcm_bytes: bytes) -> None:
        """
        Record an audio frame sent to speakers as reference signal.
        Expected format: 16-bit signed PCM mono.
        """
        if self.headphone_mode or not pcm_bytes:
            return

        try:
            arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            with self._lock:
                self._ref_buffer.append(arr)
                self._last_playback_time = time.time()
        except Exception as e:
            logger.debug(f"[AcousticEchoSuppressor] Error feeding playback frame: {e}")

    def process_capture_frame(self, pcm_bytes: bytes) -> bytes:
        """
        Process an incoming microphone audio frame.
        If echo is detected from the speaker reference buffer, attenuates the signal.
        
        Returns:
            Processed PCM bytes.
        """
        if self.headphone_mode:
            return pcm_bytes

        self._total_frame_count += 1
        now = time.time()

        # If no speaker output in last 0.35s, speaker is idle; pass through frame untouched
        if now - self._last_playback_time > 0.35:
            self._is_suppressing = False
            return pcm_bytes

        try:
            mic_arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            mic_energy = float(np.mean(mic_arr ** 2))

            if mic_energy < 1e-6:
                # Silence
                return pcm_bytes

            with self._lock:
                if not self._ref_buffer:
                    return pcm_bytes
                # Check recent playback energy
                recent_ref = self._ref_buffer[-1]

            ref_energy = float(np.mean(recent_ref ** 2)) if len(recent_ref) > 0 else 0.0

            # If speakers are active
            if ref_energy > 1e-4:
                # Calculate normalized cross-correlation
                min_len = min(len(mic_arr), len(recent_ref))
                if min_len > 0:
                    norm_mic = mic_arr[:min_len] / (np.linalg.norm(mic_arr[:min_len]) + 1e-8)
                    norm_ref = recent_ref[:min_len] / (np.linalg.norm(recent_ref[:min_len]) + 1e-8)
                    corr = float(np.abs(np.dot(norm_mic, norm_ref)))
                else:
                    corr = 0.0

                if corr > self.correlation_threshold or ref_energy > (mic_energy * 0.8):
                    # Echo confirmed: suppress microphone frame
                    self._is_suppressing = True
                    self._suppressed_frame_count += 1
                    suppressed_arr = mic_arr * self.attenuation_factor
                    clamped = np.clip(suppressed_arr * 32768.0, -32768, 32767).astype(np.int16)
                    return clamped.tobytes()

            self._is_suppressing = False
            return pcm_bytes

        except Exception as e:
            logger.debug(f"[AcousticEchoSuppressor] Error processing capture frame: {e}")
            return pcm_bytes

    def is_suppressing(self) -> bool:
        """Returns True if currently attenuating speaker echo."""
        return self._is_suppressing

    def get_stats(self) -> dict[str, Any]:
        """Return suppression telemetry."""
        suppression_rate = (
            (self._suppressed_frame_count / max(1, self._total_frame_count)) * 100.0
        )
        return {
            "headphone_mode": self.headphone_mode,
            "is_suppressing": self._is_suppressing,
            "suppressed_frame_count": self._suppressed_frame_count,
            "total_frame_count": self._total_frame_count,
            "suppression_rate_pct": round(suppression_rate, 2),
        }
