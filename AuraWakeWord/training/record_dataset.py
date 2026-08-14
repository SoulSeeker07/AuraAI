import argparse
import os
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    print("Error: Missing required packages.")
    print("Please run: pip install sounddevice numpy")
    sys.exit(1)


# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = 'int16'
RECORD_SECONDS = 2.0


def save_audio(output_dir: Path, audio_data: np.ndarray, prefix: str) -> Path:
    """Save raw audio data to a WAV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"{prefix}_{timestamp}.wav"
    filepath = output_dir / filename
    
    with wave.open(str(filepath), 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(np.dtype(DTYPE).itemsize)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data.tobytes())
        
    return filepath


def record_sample(output_dir: Path, prefix: str = "sample", duration: float = RECORD_SECONDS):
    """Record a single audio sample interactively."""
    # Countdown
    for i in range(3, 0, -1):
        print(f"\rStarting in {i}...", end="", flush=True)
        time.sleep(1)
    
    print(f"\rRecording {duration} seconds... Speak now!    ")
    
    try:
        # Record audio
        audio_data = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE
        )
        
        # Simple progress bar
        print("[", end="")
        for i in range(10):
            time.sleep(duration / 10)
            print("=", end="", flush=True)
        print("] Done!")
        
        sd.wait()  # Wait until recording is finished
        
        filepath = save_audio(output_dir, audio_data, prefix)
        print(f"Saved to: {filepath}")
        return filepath
        
    except sd.PortAudioError as e:
        print(f"\n[!] Microphone Error: {e}")
        print("Please check your microphone connection and permissions.")
        return None


def record_continuous(output_dir: Path, prefix: str = "noise", chunk_duration: float = 2.0):
    """Continuously record background noise in chunks without interaction."""
    print(f"\nStarting continuous recording... Press Ctrl+C to stop.")
    count = 0
    
    try:
        while True:
            print(f"\rRecording chunk {count + 1}...", end="", flush=True)
            audio_data = sd.rec(
                int(chunk_duration * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE
            )
            sd.wait()
            save_audio(output_dir, audio_data, prefix)
            count += 1
            
    except KeyboardInterrupt:
        print(f"\n\nStopped continuous recording. Saved {count} chunks.")
    except sd.PortAudioError as e:
        print(f"\n[!] Microphone Error: {e}")
        print("Please check your microphone connection and permissions.")


def main():
    parser = argparse.ArgumentParser(description="AuraWakeWord Dataset Recorder")
    parser.add_argument(
        "--type", 
        type=str, 
        choices=["positive", "negative", "hard_negative"],
        required=True,
        help="Type of sample to record (positive='Hey Aura', negative=random, hard_negative='Aurora' etc.)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Duration to record per sample in seconds (default: 2.0)"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="",
        help="Prefix for filename (e.g., 'hey_aura', 'aurora', 'noise')"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Record continuously in chunks without asking for Enter (great for background noise)"
    )
    
    args = parser.parse_args()
    
    # Resolve directory
    base_dir = Path(__file__).resolve().parent.parent / "dataset"
    target_dir = base_dir / args.type
    
    if not target_dir.exists():
        print(f"Creating directory: {target_dir}")
        target_dir.mkdir(parents=True, exist_ok=True)
        
    prefix = args.prefix if args.prefix else args.type
    
    print("=" * 50)
    print(f"AURA WAKE-WORD RECORDER")
    print("=" * 50)
    print(f"Target directory : {target_dir}")
    print(f"Sample duration  : {args.duration} seconds")
    print(f"Format           : {SAMPLE_RATE} Hz, Mono, 16-bit PCM")
    print("=" * 50)
    print("\nInstructions:")
    
    if args.continuous:
        print("Continuous mode enabled. This will record non-stop until you press Ctrl+C.")
        print("Leave it running to capture background ambient noise.")
        record_continuous(target_dir, prefix=prefix, chunk_duration=args.duration)
        sys.exit(0)
        
    if args.type == "positive":
        print("Say: 'Hey Aura' (vary your pronunciation, speed, volume, and distance)")
    elif args.type == "hard_negative":
        print("Say similar sounding words: 'Aurora', 'Laura', 'Hey Google', 'Are you there'")
    else:
        print("Say random things to capture non-trigger speech.")
        
    print("\nType 'q' and press ENTER to quit at any time.")
    
    count = 0
    while True:
        try:
            cmd = input(f"\n[Recorded: {count}] Press ENTER to record (or 'q' to quit): ")
            if cmd.lower().strip() == 'q':
                break
                
            res = record_sample(target_dir, prefix=prefix, duration=args.duration)
            if res:
                count += 1
            
        except KeyboardInterrupt:
            break
            
    print(f"\nFinished. Recorded {count} new samples in {target_dir.name}/")

if __name__ == "__main__":
    main()
