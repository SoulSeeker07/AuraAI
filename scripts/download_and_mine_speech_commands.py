"""
Download and Mine Google Speech Commands Dataset.
Downloads the official ~107MB test set (thousands of 1-second real human speech WAVs),
streams them through the Aura Wake Word detector with an adversarial threshold (default: 0.70, hits >= 2),
and auto-saves any trapped false triggers into AuraWakeWord/dataset/raw/hard_negative.
Cleans up temporary downloads after mining.
"""

import os
import sys
import tarfile
import urllib.request
from pathlib import Path
import numpy as np

# Strictly disable auto-saving during mining
os.environ["SAVE_WAKE_WORD_SAMPLES"] = "false"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AuraWakeWord.runtime.aura_wake_detector import AuraWakeDetector

DATASET_URL = "http://download.tensorflow.org/data/speech_commands_test_set_v0.02.tar.gz"


def download_with_progress(url: str, dest_path: Path):
    print(f"Downloading Google Speech Commands test set (~107 MB)...")
    
    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = (downloaded / total_size) * 100
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\rDownload progress: {mb:.1f} MB / {total_mb:.1f} MB ({percent:.1f}%)")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, str(dest_path), reporthook)
    print("\nDownload complete!")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Mine hard negatives from Google Speech Commands")
    parser.add_argument("--threshold", type=float, default=0.70, help="Adversarial mining threshold (default: 0.70)")
    parser.add_argument("--hits", type=int, default=2, help="Consecutive hits required to trap (default: 2)")
    parser.add_argument("--max_samples", type=int, default=3000, help="Maximum number of audio files to scan (default: 3000)")
    args = parser.parse_args()

    temp_dir = PROJECT_ROOT / "Data" / "temp_speech_commands"
    temp_dir.mkdir(parents=True, exist_ok=True)
    tar_path = temp_dir / "speech_commands_test.tar.gz"

    dest_dir = PROJECT_ROOT / "AuraWakeWord" / "dataset" / "raw" / "hard_negative"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Download archive if not already downloaded
    if not tar_path.exists() or tar_path.stat().st_size < 100 * 1024 * 1024:
        download_with_progress(DATASET_URL, tar_path)
    else:
        print(f"Archive already cached at {tar_path}")

    # 2. Initialize Wake Word Detector
    model_path = str(PROJECT_ROOT / "AuraWakeWord" / "models" / "aura_wakeword.onnx")
    detector = AuraWakeDetector(model_path=model_path)
    if not detector.initialize():
        print("[ERROR] Could not initialize AuraWakeDetector ONNX model.")
        sys.exit(1)
    detector.enabled = True

    print("\n" + "=" * 80)
    print(f" STREAMING & MINING HARD NEGATIVES (Threshold >= {args.threshold:.2f}, Hits >= {args.hits})")
    print("=" * 80)

    # 3. Stream through the tar archive directly in memory without extracting thousands of files to disk!
    trapped = []
    scanned = 0

    with tarfile.open(str(tar_path), "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.name.endswith(".wav")]
        total_in_archive = len(members)
        print(f"Found {total_in_archive} audio files in archive. Scanning up to {args.max_samples}...")

        for member in members:
            if scanned >= args.max_samples:
                break

            scanned += 1
            f = tar.extractfile(member)
            if f is None:
                continue

            raw_wav_bytes = f.read()
            import wave
            import io

            try:
                with wave.open(io.BytesIO(raw_wav_bytes), "rb") as wf:
                    n_channels = wf.getnchannels()
                    audio_bytes = wf.readframes(wf.getnframes())
            except Exception:
                continue

            if n_channels > 1:
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16).reshape(-1, n_channels)
                audio_np = np.mean(audio_np, axis=1).astype(np.int16)
                audio_bytes = audio_np.tobytes()

            # Stream through detector in 512-sample chunks (~32ms)
            detector.reset()
            probs = []
            chunk_bytes = 512 * 2
            for i in range(0, len(audio_bytes), chunk_bytes):
                chunk = audio_bytes[i : i + chunk_bytes]
                if len(chunk) < chunk_bytes:
                    chunk = chunk + b"\x00" * (chunk_bytes - len(chunk))
                detector.process_audio(chunk, sample_rate=16000)
                probs.append(detector.last_probability)

            # Check consecutive hits >= threshold
            cur, max_hits = 0, 0
            for p in probs:
                if p >= args.threshold:
                    cur += 1
                    if cur > max_hits:
                        max_hits = cur
                else:
                    cur = 0

            peak = max(probs) if probs else 0.0

            if max_hits >= args.hits:
                clean_name = Path(member.name).stem.replace("/", "_").replace("\\", "_")
                dest_file = dest_dir / f"gsc_hardneg_{clean_name}.wav"

                # Save 2-second padded clip to match Aura wake buffer
                full_audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                if len(full_audio_np) < 32000:
                    pad = 32000 - len(full_audio_np)
                    full_audio_np = np.pad(full_audio_np, (0, pad), mode="constant")
                else:
                    full_audio_np = full_audio_np[:32000]

                with wave.open(str(dest_file), "wb") as out_wf:
                    out_wf.setnchannels(1)
                    out_wf.setsampwidth(2)
                    out_wf.setframerate(16000)
                    out_wf.writeframes(full_audio_np.tobytes())

                trapped.append({
                    "name": dest_file.name,
                    "peak": peak,
                    "hits": max_hits,
                    "original": member.name
                })
                print(f"\n[TRAPPED] {member.name} -> Peak: {peak:.4f}, Hits: {max_hits} (Saved as {dest_file.name})")

            if scanned % 50 == 0 or scanned == args.max_samples:
                sys.stdout.write(f"\rScanning: {scanned}/{args.max_samples} ({(scanned/args.max_samples)*100:.1f}%) | Trapped: {len(trapped)}")
                sys.stdout.flush()

    print("\n\n" + "=" * 80)
    print(f" MINING COMPLETE: Trapped {len(trapped)} hard negatives out of {scanned} scanned files")
    print("=" * 80)
    for t in trapped:
        print(f"  * {t['original']} (Peak={t['peak']:.4f}, Hits={t['hits']}) -> {t['name']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
