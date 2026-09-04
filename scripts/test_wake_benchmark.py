"""
Comprehensive Benchmark for Aura Wake Word detection.
Evaluates detection rate across all 262 positive samples and false-alarm rate across 48 hard negatives.
Runs single-pass inference and produces comparative performance tables across thresholds and hit counts.
"""

import os
import sys
import wave
import argparse
from pathlib import Path
import numpy as np

# Ensure auto-saving is strictly disabled during benchmark
os.environ["SAVE_WAKE_WORD_SAMPLES"] = "false"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AuraWakeWord.runtime.aura_wake_detector import AuraWakeDetector


def stream_wav_through_detector(detector: AuraWakeDetector, wav_path: Path, chunk_size: int = 512):
    """
    Simulates real-time microphone streaming by feeding the WAV file in 512-sample (~32ms) chunks.
    Returns list of probability scores for each chunk.
    """
    detector.reset()
    try:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            raw_bytes = wf.readframes(wf.getnframes())
    except Exception as e:
        return []

    if n_channels > 1:
        audio_np = np.frombuffer(raw_bytes, dtype=np.int16).reshape(-1, n_channels)
        audio_np = np.mean(audio_np, axis=1).astype(np.int16)
        raw_bytes = audio_np.tobytes()

    probs = []
    chunk_bytes = chunk_size * 2
    for i in range(0, len(raw_bytes), chunk_bytes):
        chunk = raw_bytes[i : i + chunk_bytes]
        if len(chunk) < chunk_bytes:
            chunk = chunk + b"\x00" * (chunk_bytes - len(chunk))
        detector.process_audio(chunk, sample_rate=16000)
        probs.append(detector.last_probability)

    return probs


def calculate_max_consecutive(probs, threshold):
    """Calculate maximum consecutive frames meeting or exceeding threshold."""
    cur = 0
    max_consec = 0
    for p in probs:
        if p >= threshold:
            cur += 1
            if cur > max_consec:
                max_consec = cur
        else:
            cur = 0
    return max_consec


def main():
    parser = argparse.ArgumentParser(description="Test Aura Wake Word on raw dataset")
    parser.add_argument("--threshold", type=float, default=0.85, help="Primary threshold to display in detail (default: 0.85)")
    args = parser.parse_args()

    model_path = str(PROJECT_ROOT / "AuraWakeWord" / "models" / "aura_wakeword.onnx")
    pos_dir = PROJECT_ROOT / "AuraWakeWord" / "dataset" / "raw" / "positive"
    neg_dir = PROJECT_ROOT / "AuraWakeWord" / "dataset" / "raw" / "hard_negative"

    pos_files = sorted(list(pos_dir.glob("*.wav")))
    neg_files = sorted(list(neg_dir.glob("*.wav"))) if neg_dir.exists() else []

    print("=" * 86)
    print(" AURA WAKE WORD COMPREHENSIVE DATASET BENCHMARK")
    print("=" * 86)
    print(f"Total Positive Samples:     {len(pos_files)}")
    print(f"Total Hard Negative Samples:{len(neg_files)}")
    print(f"Model Path:                 {model_path}")
    print()

    detector = AuraWakeDetector(model_path=model_path)
    if not detector.initialize():
        print("[ERROR] Could not initialize AuraWakeDetector ONNX model.")
        sys.exit(1)
    detector.enabled = True

    # 1. Process Positive Samples (collect probability profiles)
    print(f"Streaming {len(pos_files)} positive samples through detector...")
    pos_profiles = []
    for idx, wav_p in enumerate(pos_files, 1):
        probs = stream_wav_through_detector(detector, wav_p)
        if probs:
            pos_profiles.append((wav_p.name, probs))
        if idx % 10 == 0 or idx == len(pos_files):
            sys.stdout.write(f"\rProgress (Positives): {idx}/{len(pos_files)} ({idx/len(pos_files)*100:.1f}%)")
            sys.stdout.flush()
    print(" [DONE]")

    # 2. Process Hard Negative Samples
    print(f"Streaming {len(neg_files)} hard negative samples through detector...")
    neg_profiles = []
    for idx, wav_p in enumerate(neg_files, 1):
        probs = stream_wav_through_detector(detector, wav_p)
        if probs:
            neg_profiles.append((wav_p.name, probs))
        if idx % 10 == 0 or idx == len(neg_files):
            sys.stdout.write(f"\rProgress (Hard Negatives): {idx}/{len(neg_files)} ({idx/len(neg_files)*100:.1f}%)")
            sys.stdout.flush()
    print(" [DONE]")

    # 3. Sweep across Thresholds (0.80, 0.82, 0.85, 0.88) and Hits (3 to 10)
    eval_thresholds = [0.80, 0.82, 0.85, 0.88]
    if args.threshold not in eval_thresholds:
        eval_thresholds.append(args.threshold)
        eval_thresholds.sort()

    for th in eval_thresholds:
        print("\n" + "=" * 86)
        print(f" PERFORMANCE MATRIX AT THRESHOLD = {th:.2f}")
        print("=" * 86)
        header = f"{'Hits':<6} | {'Positives Detected':<22} | {'True Positive %':<16} | {'Hard Neg False Alarms':<23} | {'False Alarm %'}"
        print(header)
        print("-" * len(header))

        for hits in range(3, 11):
            pos_count = sum(1 for name, probs in pos_profiles if calculate_max_consecutive(probs, th) >= hits)
            pos_pct = (pos_count / len(pos_profiles)) * 100 if pos_profiles else 0.0

            neg_count = sum(1 for name, probs in neg_profiles if calculate_max_consecutive(probs, th) >= hits)
            neg_pct = (neg_count / len(neg_profiles)) * 100 if neg_profiles else 0.0

            marker = ""
            if th >= 0.82 and hits in [5, 6, 7]:
                marker = " <-- RECOMMENDED"

            print(f"{hits:<6} | {pos_count}/{len(pos_profiles)} detected{'':<7} | {pos_pct:>6.1f}%{'':<8} | {neg_count}/{len(neg_profiles)} false alarms{'':<4} | {neg_pct:>6.1f}%{marker}")

        # List specific hard negatives that triggered
        triggered_negs = []
        for name, probs in neg_profiles:
            max_h = calculate_max_consecutive(probs, th)
            if max_h >= 4:
                peak = max(probs) if probs else 0.0
                triggered_negs.append((name, peak, max_h))
        if triggered_negs:
            print(f"\n  [ALERT] Hard negatives triggering at {th:.2f} (Hits >= 4):")
            for name, peak, max_h in triggered_negs:
                print(f"    - {name} | Peak: {peak:.4f} | Hits: {max_h}")
    print(" BENCHMARK COMPLETE")
    print("=" * 86)


if __name__ == "__main__":
    main()
