import os
import wave
import numpy as np
from pathlib import Path
from AuraWakeWord.runtime.aura_wake_detector import AuraWakeDetector

def test_aura_wake_detector_save_positive_sample(tmp_path, monkeypatch):
    # Mock model initialization to avoid ONNX file loading
    monkeypatch.setattr(AuraWakeDetector, "initialize", lambda self: True)
    
    detector = AuraWakeDetector(model_path="dummy.onnx")
    
    # Create test audio buffer (2 seconds of 16kHz audio = 32000 samples)
    audio_buf = np.zeros(32000, dtype=np.float32)
    
    target_dir = Path(__file__).resolve().parents[2] / "AuraWakeWord" / "dataset" / "raw" / "positive"
    
    count_before = len(list(target_dir.glob("positive_*.wav"))) if target_dir.exists() else 0
    
    # Run _save_positive_sample
    detector._save_positive_sample(audio_buf)
    
    count_after = len(list(target_dir.glob("positive_*.wav"))) if target_dir.exists() else 0
    
    assert count_after == count_before + 1
    
    # Clean up created test file
    new_files = sorted(list(target_dir.glob("positive_*.wav")), key=lambda p: p.stat().st_mtime)
    latest_file = new_files[-1]
    
    # Verify WAV parameters
    with wave.open(str(latest_file), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        
    latest_file.unlink()  # Remove test artifact

def test_aura_wake_detector_save_positive_sample_deferred(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(AuraWakeDetector, "initialize", lambda self: True)
    detector = AuraWakeDetector(model_path="dummy.onnx")
    audio_buf = np.zeros(32000, dtype=np.float32)
    
    target_dir = Path(__file__).resolve().parents[2] / "AuraWakeWord" / "dataset" / "raw" / "positive"
    count_before = len(list(target_dir.glob("positive_*.wav"))) if target_dir.exists() else 0
    
    detector._save_positive_sample_deferred(audio_buf, post_delay_s=0.1)
    time.sleep(0.3)
    
    count_after = len(list(target_dir.glob("positive_*.wav"))) if target_dir.exists() else 0
    assert count_after == count_before + 1
    
    new_files = sorted(list(target_dir.glob("positive_*.wav")), key=lambda p: p.stat().st_mtime)
    latest_file = new_files[-1]
    latest_file.unlink()
