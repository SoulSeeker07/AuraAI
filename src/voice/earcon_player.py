"""
Earcon Player

Plays ultra-low-latency synthesized audio feedback (earcon / chime)
upon wake word detection or state transitions, mirroring the responsive
feel of Alexa / Siri.
"""

import logging
import threading
import numpy as np

logger = logging.getLogger(__name__)


class EarconPlayer:
    """Non-blocking, synthesized audio feedback player."""

    _cached_chime: np.ndarray | None = None
    _cached_followup_chime: np.ndarray | None = None
    _sample_rate: int = 16000

    @classmethod
    def generate_chime(cls, sample_rate: int = 16000) -> np.ndarray:
        """
        Generate a pleasant, non-clipping dual-tone rising chime (880 Hz -> 1320 Hz)
        with smooth cosine envelope to prevent speaker popping.
        """
        duration1 = 0.035  # 35ms for Tone 1
        duration2 = 0.045  # 45ms for Tone 2

        t1 = np.linspace(0, duration1, int(duration1 * sample_rate), endpoint=False)
        t2 = np.linspace(0, duration2, int(duration2 * sample_rate), endpoint=False)

        # Tone 1: 880 Hz (A5)
        wave1 = 0.25 * np.sin(2 * np.pi * 880 * t1)
        # Tone 2: 1320 Hz (E6)
        wave2 = 0.25 * np.sin(2 * np.pi * 1320 * t2)

        wave = np.concatenate([wave1, wave2])

        # Apply smooth cosine envelope (fade in 5ms, fade out 10ms)
        fade_in_len = min(int(0.005 * sample_rate), len(wave))
        fade_out_len = min(int(0.010 * sample_rate), len(wave))

        fade_in = np.sin(np.linspace(0, np.pi / 2, fade_in_len)) ** 2
        fade_out = np.cos(np.linspace(0, np.pi / 2, fade_out_len)) ** 2

        wave[:fade_in_len] *= fade_in
        wave[-fade_out_len:] *= fade_out

        return wave.astype(np.float32)

    @classmethod
    def generate_followup_chime(cls, sample_rate: int = 16000) -> np.ndarray:
        """
        Generate a soft, distinct high-pitched double-pip (1046 Hz -> 1318 Hz)
        to audibly cue the user that the 5s follow-up window is open.
        """
        dur = 0.030  # 30ms per pip
        t = np.linspace(0, dur, int(dur * sample_rate), endpoint=False)

        # 1046 Hz (C6) and 1318 Hz (E6)
        wave1 = 0.18 * np.sin(2 * np.pi * 1046 * t)
        wave2 = 0.18 * np.sin(2 * np.pi * 1318 * t)

        pause = np.zeros(int(0.015 * sample_rate), dtype=np.float32)
        wave = np.concatenate([wave1, pause, wave2])

        # Cosine envelope
        fade_len = min(int(0.004 * sample_rate), len(wave))
        fade_in = np.sin(np.linspace(0, np.pi / 2, fade_len)) ** 2
        fade_out = np.cos(np.linspace(0, np.pi / 2, fade_len)) ** 2

        wave[:fade_len] *= fade_in
        wave[-fade_len:] *= fade_out

        return wave.astype(np.float32)

    @classmethod
    def play_wake_chime(cls) -> None:
        """
        Play the wake earcon asynchronously on a background thread.
        Never blocks the caller and never raises on device errors.
        """
        def _play():
            try:
                import sounddevice as sd

                if cls._cached_chime is None:
                    cls._cached_chime = cls.generate_chime(cls._sample_rate)

                sd.play(cls._cached_chime, samplerate=cls._sample_rate, blocking=False)
            except Exception as e:
                logger.debug(f"[EarconPlayer] Playback skipped or failed: {e}")

        threading.Thread(target=_play, daemon=True, name="EarconPlayer").start()

    @classmethod
    def play_followup_chime(cls) -> None:
        """
        Play the follow-up earcon asynchronously on a background thread.
        Never blocks the caller and never raises on device errors.
        """
        def _play():
            try:
                import sounddevice as sd

                if cls._cached_followup_chime is None:
                    cls._cached_followup_chime = cls.generate_followup_chime(cls._sample_rate)

                sd.play(cls._cached_followup_chime, samplerate=cls._sample_rate, blocking=False)
            except Exception as e:
                logger.debug(f"[EarconPlayer] Followup playback skipped or failed: {e}")

        threading.Thread(target=_play, daemon=True, name="FollowupEarconPlayer").start()
