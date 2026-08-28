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

ENROLLMENT_PHRASES = [
    "Hey Aura, this is my voice.",
    "Hey Aura, open my workspace.",
    "Hey Aura, check system status.",
]


def record_sample(p: pyaudio.PyAudio, sample_idx: int, phrase: str, duration_s: float = 3.0) -> bytes:
    while True:
        print(f"\n[Sample {sample_idx}/3] Phrase to speak: \"{phrase}\"")
        input(f"👉 Press [Enter] when you are ready to speak... ")
        print("  🎤 RECORDING NOW... (Speak clearly!)", flush=True)

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

        raw_pcm = b"".join(frames)
        audio_np = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio_np**2)))

        if rms < 0.008:
            print(f"  [!] No speech detected (RMS: {rms:.4f} too quiet). Let's retry sample {sample_idx}...", flush=True)
            time.sleep(1.0)
            continue

        print(f"  ✓ Captured sample (Vocal RMS: {rms:.4f}).", flush=True)
        return raw_pcm


def main():
    print("================================================================")
    print("         AURA AI — OWNER VOICEPRINT ENROLLMENT WIZARD           ")
    print("================================================================\n")
    print("This wizard will capture 3 short audio samples to generate your")
    print("unique on-device acoustic voiceprint.\n")

    p = pyaudio.PyAudio()
    samples = []
    try:
        for idx, phrase in enumerate(ENROLLMENT_PHRASES, start=1):
            raw = record_sample(p, idx, phrase, duration_s=2.8)
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
