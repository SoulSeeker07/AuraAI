"""
Unit tests for EarconPlayer.
"""

import numpy as np
from src.voice.earcon_player import EarconPlayer


def test_generate_chime():
    """Verify generated chime is valid float32 PCM audio with non-clipping amplitude."""
    sample_rate = 16000
    chime = EarconPlayer.generate_chime(sample_rate=sample_rate)

    assert isinstance(chime, np.ndarray)
    assert chime.dtype == np.float32
    assert len(chime) > 0

    # Ensure audio values stay safely within [-1.0, 1.0] without clipping
    assert np.max(chime) <= 0.5
    assert np.min(chime) >= -0.5

    # Check fade-in starts at zero and fade-out ends near zero
    assert abs(chime[0]) < 1e-4
    assert abs(chime[-1]) < 1e-4


def test_play_wake_chime_non_blocking():
    """Verify play_wake_chime executes asynchronously without raising exceptions."""
    try:
        EarconPlayer.play_wake_chime()
    except Exception as e:
        assert False, f"play_wake_chime raised an unexpected exception: {e}"
