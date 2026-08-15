"""
Unit tests for AuraWakeDetector.
Verifies that silence, ambient room noise, and 50Hz/60Hz electrical hum NEVER trigger wake word.
"""

from pathlib import Path
import numpy as np
import pytest
from AuraWakeWord.runtime.aura_wake_detector import AuraWakeDetector


@pytest.fixture
def detector():
    project_root = Path(__file__).resolve().parents[1]
    model_path = str(project_root / "AuraWakeWord" / "models" / "aura_wakeword.onnx")
    det = AuraWakeDetector(model_path=model_path, sensitivity=0.5)
    det.initialize()
    det.enabled = True
    return det


def test_silence_never_triggers_wake_word(detector):
    """Feed 100 chunks of pure silence (zeros) and verify 0 triggers occur."""
    triggered = []
    detector.on_wake_word_detected = lambda word: triggered.append(word)

    chunk = (np.zeros(512, dtype=np.int16)).tobytes()
    for _ in range(100):
        detector.process_audio(chunk, sample_rate=16000)

    assert len(triggered) == 0, f"Expected 0 triggers on silence, but got: {len(triggered)}"
    assert detector.last_probability == 0.0


def test_electrical_hum_and_dc_never_triggers(detector):
    """Feed 100 chunks of 50Hz ground hum + DC bias and verify 0 triggers occur."""
    triggered = []
    detector.on_wake_word_detected = lambda word: triggered.append(word)

    t = np.arange(512)
    # 50Hz electrical hum with DC offset (typical for USB ADC / laptop mics)
    raw_signal = (50 + 30 * np.sin(2 * np.pi * 50 * t / 16000)).astype(np.int16)
    chunk = raw_signal.tobytes()

    for _ in range(100):
        detector.process_audio(chunk, sample_rate=16000)

    assert len(triggered) == 0, f"Expected 0 triggers on 50Hz hum, but got: {len(triggered)}"


def test_sub_threshold_room_hiss_never_triggers(detector):
    """Feed 100 chunks of low-energy room background hiss (RMS < 0.002) and verify 0 triggers."""
    triggered = []
    detector.on_wake_word_detected = lambda word: triggered.append(word)

    for _ in range(100):
        # Ambient mic noise with peak ~30 (RMS ~0.0006)
        noise = np.random.normal(0, 20, 512).astype(np.int16)
        detector.process_audio(noise.tobytes(), sample_rate=16000)

    assert len(triggered) == 0, f"Expected 0 triggers on ambient hiss, but got: {len(triggered)}"
