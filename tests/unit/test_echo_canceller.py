"""
Unit Tests for Acoustic Echo Suppressor (AES)
Location: tests/unit/test_echo_canceller.py
"""

import numpy as np
import pytest
from src.voice.echo_canceller import AcousticEchoSuppressor


def _generate_sine_pcm(freq: float = 440.0, duration: float = 0.1, sample_rate: int = 16000) -> bytes:
    """Generate 16-bit mono PCM sine wave bytes."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    waveform = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)
    return waveform.tobytes()


def test_01_echo_canceller_passthrough_when_speaker_silent():
    """Verify that when the speaker is silent, mic frames pass through untouched."""
    aes = AcousticEchoSuppressor(sample_rate=16000, attenuation_db=24.0)

    test_pcm = _generate_sine_pcm(freq=800.0, duration=0.05)
    processed = aes.process_capture_frame(test_pcm)

    assert processed == test_pcm
    assert not aes.is_suppressing()


def test_02_echo_canceller_suppresses_speaker_echo():
    """Verify that when speaker is actively playing and mic captures the same sound, attenuation fires."""
    aes = AcousticEchoSuppressor(
        sample_rate=16000,
        attenuation_db=20.0,
        correlation_threshold=0.25,
    )

    # 1. Simulate speaker playback frame
    speaker_audio = _generate_sine_pcm(freq=440.0, duration=0.05)
    aes.feed_playback_frame(speaker_audio)

    # 2. Simulate microphone capturing the acoustic echo of the speaker
    mic_echo = speaker_audio
    processed = aes.process_capture_frame(mic_echo)

    # Output should be attenuated
    in_arr = np.frombuffer(mic_echo, dtype=np.int16).astype(np.float32)
    out_arr = np.frombuffer(processed, dtype=np.int16).astype(np.float32)

    in_rms = np.sqrt(np.mean(in_arr ** 2))
    out_rms = np.sqrt(np.mean(out_arr ** 2))

    assert aes.is_suppressing()
    assert out_rms < in_rms * 0.25  # Substantial attenuation (~20dB)


def test_03_headphone_mode_bypasses_all_processing():
    """Verify that headphone mode applies zero attenuation or manipulation."""
    aes = AcousticEchoSuppressor(headphone_mode=True)

    speaker_audio = _generate_sine_pcm(freq=440.0, duration=0.05)
    aes.feed_playback_frame(speaker_audio)

    mic_echo = speaker_audio
    processed = aes.process_capture_frame(mic_echo)

    assert processed == mic_echo
    assert not aes.is_suppressing()
