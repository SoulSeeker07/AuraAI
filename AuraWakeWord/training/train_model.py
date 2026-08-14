import argparse
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchaudio
import numpy as np
from torch.utils.data import Dataset, DataLoader

# Hyperparameters
SAMPLE_RATE = 16000
DURATION_SECS = 2.0
NUM_SAMPLES = int(SAMPLE_RATE * DURATION_SECS)
N_MELS = 40
N_FFT = 400
HOP_LENGTH = 160


class AuraDataset(Dataset):
    def __init__(self, data_dir: Path, is_train: bool = True):
        self.data_dir = data_dir
        self.is_train = is_train
        
        # Determine target directories
        self.pos_dir = data_dir / "positive"
        self.neg_dir = data_dir / "negative"
        self.hard_neg_dir = data_dir / "hard_negative"
            
        self.files = []
        self.labels = []
        
        # Load positives (Label: 1)
        if self.pos_dir.exists():
            for f in self.pos_dir.glob("*.wav"):
                self.files.append(f)
                self.labels.append(1.0)
                
        # Load negatives and hard negatives (Label: 0)
        for d in [self.neg_dir, self.hard_neg_dir]:
            if d.exists():
                for f in d.glob("*.wav"):
                    self.files.append(f)
                    self.labels.append(0.0)
                    
        self.mel_transform = torchaudio.transforms.MelSpectrogram(
            sample_rate=SAMPLE_RATE,
            n_fft=N_FFT,
            hop_length=HOP_LENGTH,
            n_mels=N_MELS
        )
        
        print(f"Loaded {'train' if is_train else 'val'} dataset: {len(self.files)} samples "
              f"({sum(self.labels)} positive, {len(self.labels) - sum(self.labels)} negative)")

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        filepath = self.files[idx]
        label = self.labels[idx]
        
        # Load audio using wave and numpy instead of torchaudio.load
        # to avoid torchcodec/soundfile backend issues on Windows
        import wave
        import numpy as np
        
        with wave.open(str(filepath), 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            sr = wf.getframerate()
            
        waveform = torch.from_numpy(audio_np).unsqueeze(0)  # Shape: (1, time_steps)
        
        # Ensure mono
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
            
        # Ensure sample rate
        if sr != SAMPLE_RATE:
            resampler = torchaudio.transforms.Resample(sr, SAMPLE_RATE)
            waveform = resampler(waveform)
            
        # Pad or trim to NUM_SAMPLES
        if waveform.shape[1] > NUM_SAMPLES:
            waveform = waveform[:, :NUM_SAMPLES]
        elif waveform.shape[1] < NUM_SAMPLES:
            pad = NUM_SAMPLES - waveform.shape[1]
            waveform = F.pad(waveform, (0, pad))
            
        # Compute Mel Spectrogram
        # Shape: (1, n_mels, time_steps)
        mel_spec = self.mel_transform(waveform)
        
        # Convert to log scale (adding a small epsilon to avoid log(0))
        log_mel_spec = torch.log(mel_spec + 1e-9)
        
        return log_mel_spec, torch.tensor([label], dtype=torch.float32)


class AuraWakeModel(nn.Module):
    """A small Depthwise Separable CNN (DS-CNN) for wake word detection."""
    def __init__(self):
        super().__init__()
        # Input shape: (Batch, 1, 40 (mels), 201 (time))
        
        # Standard convolution for initial feature extraction
        self.conv1 = nn.Conv2d(1, 32, kernel_size=(3, 3), stride=(1, 1), padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.pool1 = nn.MaxPool2d(kernel_size=(2, 2))
        
        # Depthwise Separable Convolution 1
        self.dw_conv2 = nn.Conv2d(32, 32, kernel_size=(3, 3), stride=(1, 1), padding=1, groups=32)
        self.pw_conv2 = nn.Conv2d(32, 64, kernel_size=(1, 1))
        self.bn2 = nn.BatchNorm2d(64)
        self.pool2 = nn.MaxPool2d(kernel_size=(2, 2))
        
        # Depthwise Separable Convolution 2
        self.dw_conv3 = nn.Conv2d(64, 64, kernel_size=(3, 3), stride=(1, 1), padding=1, groups=64)
        self.pw_conv3 = nn.Conv2d(64, 64, kernel_size=(1, 1))
        self.bn3 = nn.BatchNorm2d(64)
        self.pool3 = nn.MaxPool2d(kernel_size=(2, 2))
        
        # Global Average Pooling
        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        
        # Fully Connected Layer
        self.fc = nn.Linear(64, 1)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.pool1(x)
        
        x = F.relu(self.pw_conv2(self.dw_conv2(x)))
        x = self.bn2(x)
        x = self.pool2(x)
        
        x = F.relu(self.pw_conv3(self.dw_conv3(x)))
        x = self.bn3(x)
        x = self.pool3(x)
        
        x = self.gap(x)
        x = x.view(x.size(0), -1) # Flatten
        
        x = self.fc(x)
        # We use BCEWithLogitsLoss during training, so no sigmoid here.
        # During inference (ONNX), we can apply sigmoid if needed, or check threshold on logits.
        return x


def train_model(data_dir: Path, output_dir: Path, epochs: int = 20, batch_size: int = 16):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    train_dataset = AuraDataset(data_dir / "train", is_train=True)
    val_dataset = AuraDataset(data_dir / "validation", is_train=False)
    
    if len(train_dataset) == 0:
        print("Error: Training dataset is empty.")
        return
        
    # Calculate class weights for Balanced Sampling
    labels = np.array(train_dataset.labels)
    num_pos = np.sum(labels)
    num_neg = len(labels) - num_pos
    
    # Give positives slightly higher priority even with balanced sampling 
    # to enforce strong recall. We use moderate weighting here.
    weight_neg = 1.0 / num_neg
    weight_pos = (1.0 / num_pos) * 1.5  # Slight boost to positive samples
    
    sample_weights = np.array([weight_pos if l == 1.0 else weight_neg for l in labels])
    sampler = torch.utils.data.WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(sample_weights),
        replacement=True
    )
        
    train_loader = DataLoader(train_dataset, batch_size=batch_size, sampler=sampler)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False) if len(val_dataset) > 0 else None
    
    model = AuraWakeModel().to(device)
    
    # Binary Cross Entropy with Logits for stable training
    criterion = nn.BCEWithLogitsLoss()
    
    # Adam optimizer
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    print("\nStarting Training...")
    best_val_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            
        train_loss /= len(train_loader)
        
        # Validation
        val_loss = 0.0
        val_acc = 0.0
        if val_loader:
            model.eval()
            correct = 0
            total = 0
            with torch.no_grad():
                for inputs, targets in val_loader:
                    inputs, targets = inputs.to(device), targets.to(device)
                    outputs = model(inputs)
                    loss = criterion(outputs, targets)
                    val_loss += loss.item()
                    
                    preds = torch.sigmoid(outputs) >= 0.5
                    correct += (preds == targets).sum().item()
                    total += targets.size(0)
                    
            val_loss /= len(val_loader)
            val_acc = correct / total
            print(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")
            
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                model_path = output_dir / "aura_model_best.pt"
                torch.save(model.state_dict(), model_path)
        else:
            print(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f}")
            model_path = output_dir / "aura_model_latest.pt"
            torch.save(model.state_dict(), model_path)
            
    # Save the final model
    final_path = output_dir / "aura_model_final.pt"
    torch.save(model.state_dict(), final_path)
    print(f"\nTraining complete. Model saved to: {final_path}")
    if val_loader:
        print(f"Best validation model saved to: {output_dir / 'aura_model_best.pt'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AuraWakeWord Model")
    parser.add_argument("--epochs", type=int, default=20, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
    args = parser.parse_args()
    
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "dataset"
    models_dir = base_dir / "models"
    
    models_dir.mkdir(parents=True, exist_ok=True)
    
    train_model(data_dir, models_dir, epochs=args.epochs, batch_size=args.batch_size)
