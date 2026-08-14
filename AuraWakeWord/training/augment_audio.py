import argparse
import os
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("Error: numpy is required. Please install it using 'pip install numpy'")
    exit(1)

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16
MAX_INT16 = 32767


def load_wav(filepath: Path) -> np.ndarray:
    """Load a WAV file and return as a numpy array."""
    with wave.open(str(filepath), 'rb') as wf:
        if wf.getframerate() != SAMPLE_RATE:
            print(f"Warning: {filepath.name} has samplerate {wf.getframerate()}, expected {SAMPLE_RATE}")
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=DTYPE)
        return audio


def save_wav(filepath: Path, audio: np.ndarray):
    """Save a numpy array as a WAV file."""
    with wave.open(str(filepath), 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(np.dtype(DTYPE).itemsize)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())


def augment_volume(audio: np.ndarray, gain_factor: float) -> np.ndarray:
    """Change the volume of the audio."""
    # Convert to float for safe scaling, then clip to valid int16 range
    audio_float = audio.astype(np.float32) * gain_factor
    np.clip(audio_float, -MAX_INT16, MAX_INT16, out=audio_float)
    return audio_float.astype(DTYPE)


def add_white_noise(audio: np.ndarray, noise_level: float = 0.01) -> np.ndarray:
    """Add white noise to the audio."""
    noise_amp = noise_level * MAX_INT16
    noise = np.random.normal(0, noise_amp, len(audio))
    audio_float = audio.astype(np.float32) + noise
    np.clip(audio_float, -MAX_INT16, MAX_INT16, out=audio_float)
    return audio_float.astype(DTYPE)


def time_shift(audio: np.ndarray, shift_max_ms: int = 200) -> np.ndarray:
    """Randomly shift audio in time (pad with zeros on one end, trim the other)."""
    shift_samples = int((np.random.randint(-shift_max_ms, shift_max_ms) / 1000.0) * SAMPLE_RATE)
    
    if shift_samples == 0:
        return audio
        
    shifted = np.zeros_like(audio)
    if shift_samples > 0:
        # Shift right
        shifted[shift_samples:] = audio[:-shift_samples]
    else:
        # Shift left
        shift_samples = abs(shift_samples)
        shifted[:-shift_samples] = audio[shift_samples:]
        
    return shifted


def augment_file(filepath: Path, output_dir: Path, num_variations: int = 2):
    """Generate augmented versions of a single audio file."""
    audio = load_wav(filepath)
    
    # Just copy the original as base
    # (The original file remains in the source directory, augmented files go to a specific folder)
    # Actually, let's just generate N augmented variations.
    
    generated_files = []
    
    for i in range(num_variations):
        # 1. Randomly decide what augmentations to apply
        aug_audio = np.copy(audio)
        
        # Volume change (0.5x to 1.5x)
        if np.random.random() > 0.3:
            gain = np.random.uniform(0.5, 1.5)
            aug_audio = augment_volume(aug_audio, gain)
            
        # Add white noise (1% to 3%)
        if np.random.random() > 0.4:
            noise_lvl = np.random.uniform(0.01, 0.03)
            aug_audio = add_white_noise(aug_audio, noise_lvl)
            
        # Time shift (up to 300ms)
        if np.random.random() > 0.3:
            aug_audio = time_shift(aug_audio, shift_max_ms=300)
            
        # Save augmented file
        out_name = f"{filepath.stem}_aug_{i}.wav"
        out_path = output_dir / out_name
        save_wav(out_path, aug_audio)
        generated_files.append(out_path)
        
    return generated_files


def main():
    parser = argparse.ArgumentParser(description="AuraWakeWord Data Augmenter")
    parser.add_argument(
        "--variations",
        type=int,
        default=2,
        help="Number of augmented variations to create per original file (default: 2)"
    )
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).resolve().parent.parent / "dataset"
    categories = ["positive", "negative", "hard_negative"]
    train_dir = base_dir / "train"
    
    print("=" * 50)
    print("AURA WAKE-WORD AUDIO AUGMENTATION")
    print("=" * 50)
    print(f"Generating {args.variations} augmented samples per file.")
    
    total_augmented = 0
    
    for category in categories:
        src_dir = train_dir / category
        if not src_dir.exists():
            continue
            
        files = list(src_dir.glob("*.wav"))
        
        # Filter out already augmented files
        original_files = [f for f in files if "_aug_" not in f.name]
        
        if not original_files:
            continue
            
        print(f"Augmenting {len(original_files)} files in train/{category}/...")
        
        for f in original_files:
            augment_file(f, src_dir, num_variations=args.variations)
            total_augmented += args.variations
            
    print(f"\nDone! Generated {total_augmented} augmented training samples.")
    print("NOTE: Validation files remain untouched in the 'validation/' directory.")

if __name__ == "__main__":
    main()
