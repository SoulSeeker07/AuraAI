"""
Adversarial Hard Negative Mining Script for Aura Wake Word.
Scans regular negative audio files with loose detection criteria (e.g. threshold 0.70, hits >= 2)
to trap difficult acoustic edge cases and promote them to raw/hard_negative for future retraining.
"""

import os
import sys
import wave
import shutil
import argparse
from pathlib import Path
import numpy as np

# Disable auto-saving during mining
os.environ["SAVE_WAKE_WORD_SAMPLES"] = "false"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AuraWakeWord.runtime.aura_wake_detector import AuraWakeDetector


def stream_wav_through_detector(detector: AuraWakeDetector, wav_path: Path, chunk_size: int = 512):
    detector.reset()
    try:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            raw_bytes = wf.readframes(wf.getnframes())
    except Exception:
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
    parser = argparse.ArgumentParser(description="Mine hard negatives from negative dataset")
    parser.add_argument("--threshold", type=float, default=0.70, help="Adversarial mining threshold (default: 0.70)")
    parser.add_argument("--hits", type=int, default=2, help="Consecutive hits required to trap a file (default: 2)")
    parser.add_argument("--source", type=str, default=None, help="Source directory (default: AuraWakeWord/dataset/raw/negative)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of source files to scan")
    parser.add_argument("--dry-run", action="store_true", help="Scan only without copying files")
    args = parser.parse_args()

    model_path = str(PROJECT_ROOT / "AuraWakeWord" / "models" / "aura_wakeword.onnx")
    src_dir = Path(args.source) if args.source else (PROJECT_ROOT / "AuraWakeWord" / "dataset" / "raw" / "negative")
    dest_dir = PROJECT_ROOT / "AuraWakeWord" / "dataset" / "raw" / "hard_negative"
    dest_dir.mkdir(parents=True, exist_ok=True)

    neg_files = sorted(list(src_dir.glob("*.wav")))
    if args.limit:
        neg_files = neg_files[: args.limit]

    print("=" * 80)
    print(" ADVERSARIAL HARD NEGATIVE MINING")
    print("=" * 80)
    print(f"Source Folder:       {src_dir} ({len(neg_files)} files)")
    print(f"Target Destination:  {dest_dir}")
    print(f"Mining Threshold:    {args.threshold:.2f}")
    print(f"Required Hits:       {args.hits}")
    print(f"Dry Run:             {args.dry_run}")
    print("=" * 80)

    detector = AuraWakeDetector(model_path=model_path)
    if not detector.initialize():
        print("[ERROR] Could not initialize AuraWakeDetector ONNX model.")
        sys.exit(1)
    detector.enabled = True

    mined = []
    for idx, wav_p in enumerate(neg_files, 1):
        probs = stream_wav_through_detector(detector, wav_p)
        peak = max(probs) if probs else 0.0
        max_hits = calculate_max_consecutive(probs, args.threshold)

        if max_hits >= args.hits:
            dest_name = f"mined_{wav_p.name}"
            dest_path = dest_dir / dest_name

            if not args.dry_run:
                shutil.copy2(str(wav_p), str(dest_path))

            mined.append({
                "source": wav_p.name,
                "dest": dest_name,
                "peak": peak,
                "hits": max_hits
            })
            print(f"\n[TRAPPED] {wav_p.name} -> Peak: {peak:.4f}, Hits @ {args.threshold:.2f}: {max_hits}")

        if idx % 25 == 0 or idx == len(neg_files):
            sys.stdout.write(f"\rScanning: {idx}/{len(neg_files)} ({(idx/len(neg_files))*100:.1f}%) | Trapped: {len(mined)}")
            sys.stdout.flush()

    print("\n\n" + "=" * 80)
    print(f" MINING SUMMARY: {len(mined)} Hard Negatives Trapped out of {len(neg_files)} files scanned")
    print("=" * 80)
    for m in mined:
        print(f"  * {m['source']} (Peak={m['peak']:.4f}, Hits={m['hits']}) -> {m['dest']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
