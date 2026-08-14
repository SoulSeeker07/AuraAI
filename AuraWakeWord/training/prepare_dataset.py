import argparse
import os
import random
import shutil
from pathlib import Path

def prepare_splits(base_dir: Path, val_split: float = 0.2, seed: int = 42):
    """
    Randomly copy a percentage of files from raw directories to train and validation directories.
    This ensures strict separation before any augmentation occurs.
    """
    random.seed(seed)
    
    categories = ["positive", "negative", "hard_negative"]
    raw_dir = base_dir / "raw"
    train_dir = base_dir / "train"
    val_dir = base_dir / "validation"
    
    # Create train and val directories
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)
    
    for category in categories:
        src_dir = raw_dir / category
        train_cat_dir = train_dir / category
        val_cat_dir = val_dir / category
        
        if not src_dir.exists():
            print(f"Warning: Source directory not found: {src_dir}")
            continue
            
        # Ensure destination directories exist
        train_cat_dir.mkdir(parents=True, exist_ok=True)
        val_cat_dir.mkdir(parents=True, exist_ok=True)
        
        # Clear existing train/val files to prevent accumulation
        for f in train_cat_dir.glob("*.wav"):
            f.unlink()
        for f in val_cat_dir.glob("*.wav"):
            f.unlink()
        
        # Get all wav files
        files = list(src_dir.glob("*.wav"))
        if not files:
            print(f"No WAV files found in {src_dir}")
            continue
            
        # Calculate split
        num_val = int(len(files) * val_split)
        
        if num_val == 0:
            print(f"Warning: Not enough files in {category} for a validation split.")
            
        # Randomly select files for validation
        val_files = random.sample(files, num_val)
        train_files = [f for f in files if f not in val_files]
        
        # Copy files instead of move
        for f in val_files:
            dst = val_cat_dir / f.name
            shutil.copy2(str(f), str(dst))
            
        for f in train_files:
            dst = train_cat_dir / f.name
            shutil.copy2(str(f), str(dst))
            
        print(f"Copied {len(val_files)} files from {category} to validation/{category}")
        print(f"Copied {len(train_files)} files from {category} to train/{category}")


def main():
    parser = argparse.ArgumentParser(description="Prepare Dataset Splits")
    parser.add_argument(
        "--val_split", 
        type=float, 
        default=0.2,
        help="Percentage of data to move to validation set (0.0 to 1.0, default: 0.2)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible splits (default: 42)"
    )
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).resolve().parent.parent / "dataset"
    
    print("=" * 50)
    print("AURA WAKE-WORD DATASET PREPARATION")
    print("=" * 50)
    print(f"Dataset root : {base_dir}")
    print(f"Val split    : {args.val_split * 100}%")
    print("=" * 50)
    
    prepare_splits(base_dir, val_split=args.val_split, seed=args.seed)
    
    print("\nDataset split complete. Ready for augmentation.")

if __name__ == "__main__":
    main()
