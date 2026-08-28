"""
Voiceprint Enrollment CLI Tool
==============================
Records 3 spoken samples from the primary user to generate an on-device
voiceprint embedding, ensuring Aura only activates for YOUR voice.
"""

import os
import sys
import time
import pyaudio
import numpy as np
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(1, str(root))

from voice.speaker_verification import SpeakerVerificationEngine


def record_sample(p: pyaudio.PyAudio, sample_idx: int, duration_s: float = 3.0) -> bytes:
    print(f"\n[Sample {sample_idx}/3] Speak into your mic: 'Hey Aura, this is my voice.'")
    for i in range(3, 0, -1):
        print(f"  Starting in {i}...", end="\r", flush=True)
        time.sleep(1.0)
    print("  🎤 RECORDING NOW... (Speak clearly)", flush=True)

    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1024,
    )

    frames = []
    num_frames = int(16000 / 1024 * duration_s)
    for _ in range(num_frames):
        data = stream.read(1024, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    print("  ✓ Captured sample.", flush=True)
    return b"".join(frames)


def main():
    print("================================================================")
    print("         AURA AI — OWNER VOICEPRINT ENROLLMENT WIZARD           ")
    print("================================================================\n")
    print("This wizard will capture 3 short audio samples to generate your")
    print("unique on-device acoustic voiceprint.\n")

    p = pyaudio.PyAudio()
    samples = []
    try:
        for idx in range(1, 4):
            raw = record_sample(p, idx, duration_s=2.5)
            samples.append(raw)

        print("\n[Processing] Computing 192-dimensional neural speaker embedding...")
        engine = SpeakerVerificationEngine.get_instance()
        success = engine.enroll(samples)

        if success:
            print("\n================================================================")
            print("  ✓ SUCCESS: Owner Voiceprint Enrolled Successfully!")
            print(f"  Profile saved at: {engine.profile_path}")
            print("  Aura will now verify and only trigger on YOUR voice.")
            print("================================================================\n")
        else:
            print("\n[FAIL] Enrollment failed: Audio quality too low or silent.")

    except Exception as e:
        print(f"\n[Error] Enrollment failed: {e}")
    finally:
        p.terminate()


if __name__ == "__main__":
    main()
