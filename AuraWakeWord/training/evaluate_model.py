import argparse
import os
from pathlib import Path

import torch
import torchaudio
import torch.nn.functional as F
from train_model import AuraWakeModel, SAMPLE_RATE, NUM_SAMPLES, N_MELS, N_FFT, HOP_LENGTH


def load_model(model_path: Path, device: torch.device):
    model = AuraWakeModel().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    return model


def evaluate_dataset(model, data_dir: Path, threshold: float, device: torch.device):
    pos_dir = data_dir / "positive"
    neg_dir = data_dir / "negative"
    hard_neg_dir = data_dir / "hard_negative"
    
    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=SAMPLE_RATE,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
        n_mels=N_MELS
    ).to(device)
    
    def predict_file(filepath: Path) -> float:
        import wave
        import numpy as np
        
        with wave.open(str(filepath), 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            sr = wf.getframerate()
            
        waveform = torch.from_numpy(audio_np).unsqueeze(0)  # Shape: (1, time_steps)
        
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
            
        if sr != SAMPLE_RATE:
            resampler = torchaudio.transforms.Resample(sr, SAMPLE_RATE)
            waveform = resampler(waveform)
            
        if waveform.shape[1] > NUM_SAMPLES:
            waveform = waveform[:, :NUM_SAMPLES]
        elif waveform.shape[1] < NUM_SAMPLES:
            pad = NUM_SAMPLES - waveform.shape[1]
            waveform = F.pad(waveform, (0, pad))
            
        waveform = waveform.to(device)
        mel_spec = mel_transform(waveform)
        log_mel_spec = torch.log(mel_spec + 1e-9).unsqueeze(0) # Add batch dim
        
        with torch.no_grad():
            output = model(log_mel_spec)
            prob = torch.sigmoid(output).item()
            
        return prob
        
    # --- EVALUATE ---
    pos_files = list(pos_dir.glob("*.wav")) if pos_dir.exists() else []
    neg_files = list(neg_dir.glob("*.wav")) if neg_dir.exists() else []
    hard_neg_files = list(hard_neg_dir.glob("*.wav")) if hard_neg_dir.exists() else []
    
    print("\n" + "=" * 50)
    print(" " * 10 + "AURA WAKE WORD EVALUATION")
    print("=" * 50)
    print(f"Positive samples:    {len(pos_files)}")
    print(f"Negative samples:    {len(neg_files)}")
    print(f"Hard negatives:      {len(hard_neg_files)}")
    print("-" * 50)
    
    print("\n[Individual Positive Scores]")
    pos_scores = []
    for f in pos_files:
        prob = predict_file(f)
        pos_scores.append(prob)
        print(f"  {f.name}: {prob:.4f}")
        
    print("\n[Individual Hard Negative Scores]")
    hard_neg_scores = []
    for f in hard_neg_files:
        prob = predict_file(f)
        hard_neg_scores.append(prob)
        print(f"  {f.name}: {prob:.4f}")
        
    neg_scores = []
    for f in neg_files:
        prob = predict_file(f)
        neg_scores.append(prob)
        
    print("\n" + "-" * 50)
    print(f"{'Threshold':<12} | {'Recall':<10} | {'False Positive Rate':<20}")
    print("-" * 50)
    
    thresholds = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    
    for t in thresholds:
        true_pos = sum(1 for s in pos_scores if s >= t)
        false_pos = sum(1 for s in neg_scores + hard_neg_scores if s >= t)
        
        recall = (true_pos / len(pos_scores) * 100) if len(pos_scores) > 0 else 0.0
        total_neg = len(neg_scores) + len(hard_neg_scores)
        fpr = (false_pos / total_neg * 100) if total_neg > 0 else 0.0
        
        print(f"{t:<12.2f} | {recall:>6.2f}%    | {fpr:>16.2f}%")
        
    print("=" * 50 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate AuraWakeWord Model")
    parser.add_argument("--model", type=str, default="aura_model_best.pt", help="Model filename in models/ dir")
    parser.add_argument("--threshold", type=float, default=0.8, help="Detection threshold (0.0 to 1.0)")
    parser.add_argument("--split", type=str, choices=["validation", "training"], default="validation", help="Which dataset split to evaluate")
    args = parser.parse_args()
    
    base_dir = Path(__file__).resolve().parent.parent
    model_path = base_dir / "models" / args.model
    
    if args.split == "validation":
        data_dir = base_dir / "dataset" / "validation"
    else:
        data_dir = base_dir / "dataset"
        
    if not model_path.exists():
        print(f"Error: Model not found at {model_path}")
        exit(1)
        
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(model_path, device)
    
    print(f"Evaluating {args.split} dataset using model {args.model}...")
    evaluate_dataset(model, data_dir, args.threshold, device)
