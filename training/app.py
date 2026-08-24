#!/usr/bin/env python3
"""Neural network training script.

This script demonstrates a full training pipeline using PyTorch. It includes:

* Data loading and preprocessing (MNIST via torchvision)
* A simple CNN architecture (configurable via command‑line arguments)
* Training loop with forward pass, loss computation, back‑propagation and optimizer step
* Validation/evaluation after each epoch
* Model checkpointing (saving and optional loading for inference)
* Configurable hyper‑parameters (learning rate, batch size, epochs, etc.)
* Command‑line interface via ``argparse``
* Progress reporting with ``tqdm`` and logging via the ``logging`` module

The script is deliberately self‑contained and can be used as a starting point for
more complex projects.
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Model definition
# ---------------------------------------------------------------------------

class SimpleCNN(nn.Module):
    """A simple convolutional neural network for image classification.

    The architecture consists of two convolutional layers followed by two fully
    connected layers. The number of output classes can be set via ``num_classes``.
    """

    def __init__(self, num_classes: int = 10):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(64 * 7 * 7, 128)
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def get_data_loaders(batch_size: int, data_dir: Path) -> Tuple[DataLoader, DataLoader]:
    """Create training and validation data loaders for MNIST.

    Args:
        batch_size: Number of samples per batch.
        data_dir: Directory where the dataset will be downloaded / cached.

    Returns:
        A tuple ``(train_loader, val_loader)``.
    """
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))
    ])

    train_dataset = datasets.MNIST(root=data_dir, train=True, download=True, transform=transform)
    val_dataset = datasets.MNIST(root=data_dir, train=False, download=True, transform=transform)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)
    return train_loader, val_loader


def train_one_epoch(model: nn.Module, device: torch.device, loader: DataLoader,
                    criterion: nn.Module, optimizer: optim.Optimizer, epoch: int) -> float:
    """Train the model for a single epoch.

    Returns the average training loss for the epoch.
    """
    model.train()
    running_loss = 0.0
    progress = tqdm(loader, desc=f"Epoch {epoch} [train]", leave=False)
    for batch_idx, (data, target) in enumerate(progress):
        data, target = data.to(device), target.to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        progress.set_postfix(loss=loss.item())
    avg_loss = running_loss / len(loader)
    logging.info(f"Epoch {epoch} training loss: {avg_loss:.4f}")
    return avg_loss


def evaluate(model: nn.Module, device: torch.device, loader: DataLoader,
             criterion: nn.Module, epoch: int) -> Tuple[float, float]:
    """Evaluate the model on the validation set.

    Returns a tuple ``(average_loss, accuracy)``.
    """
    model.eval()
    val_loss = 0.0
    correct = 0
    total = 0
    progress = tqdm(loader, desc=f"Epoch {epoch} [val]", leave=False)
    with torch.no_grad():
        for data, target in progress:
            data, target = data.to(device), target.to(device)
            output = model(data)
            loss = criterion(output, target)
            val_loss += loss.item()
            preds = output.argmax(dim=1, keepdim=True)
            correct += preds.eq(target.view_as(preds)).sum().item()
            total += target.size(0)
    avg_loss = val_loss / len(loader)
    accuracy = correct / total * 100.0
    logging.info(f"Epoch {epoch} validation loss: {avg_loss:.4f}, accuracy: {accuracy:.2f}%")
    return avg_loss, accuracy


def save_checkpoint(model: nn.Module, optimizer: optim.Optimizer, epoch: int, path: Path):
    """Save model checkpoint.

    The checkpoint contains the model state dict, optimizer state dict and the
    epoch number.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict()
    }, path)
    logging.info(f"Checkpoint saved to {path}")


def load_checkpoint(model: nn.Module, optimizer: optim.Optimizer, path: Path, device: torch.device) -> int:
    """Load a checkpoint and restore model/optimizer state.

    Returns the epoch stored in the checkpoint (useful for resuming training).
    """
    checkpoint = torch.load(path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    epoch = checkpoint["epoch"]
    logging.info(f"Loaded checkpoint from {path} (epoch {epoch})")
    return epoch

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a simple CNN on MNIST.")
    parser.add_argument("--data-dir", type=Path, default=Path("./data"), help="Directory for downloading the dataset")
    parser.add_argument("--output-dir", type=Path, default=Path("./output"), help="Directory to store model checkpoints and logs")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size for training and validation")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--resume", type=Path, default=None, help="Path to a checkpoint to resume training")
    parser.add_argument("--no-cuda", action="store_true", help="Disable CUDA even if it is available")
    parser.add_argument("--log-interval", type=int, default=10, help="How many batches to wait before logging training status")
    return parser.parse_args()


def main():
    args = parse_args()

    # -------------------------------------------------------------------
    # Logging configuration
    # -------------------------------------------------------------------
    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_file = args.output_dir / "training.log"
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        handlers=[logging.FileHandler(log_file), logging.StreamHandler()])
    logging.info("Starting training script with arguments: %s", args)

    # -------------------------------------------------------------------
    # Reproducibility
    # -------------------------------------------------------------------
    torch.manual_seed(args.seed)
    if torch.cuda.is_available() and not args.no_cuda:
        device = torch.device("cuda")
        torch.cuda.manual_seed_all(args.seed)
    else:
        device = torch.device("cpu")
    logging.info(f"Using device: {device}")

    # -------------------------------------------------------------------
    # Data loaders
    # -------------------------------------------------------------------
    train_loader, val_loader = get_data_loaders(args.batch_size, args.data_dir)

    # -------------------------------------------------------------------
    # Model, loss, optimizer
    # -------------------------------------------------------------------
    model = SimpleCNN(num_classes=10).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)

    start_epoch = 1
    if args.resume:
        if args.resume.is_file():
            start_epoch = load_checkpoint(model, optimizer, args.resume, device) + 1
        else:
            logging.warning(f"Resume checkpoint {args.resume} not found. Starting from scratch.")

    # -------------------------------------------------------------------
    # Training loop
    # -------------------------------------------------------------------
    for epoch in range(start_epoch, args.epochs + 1):
        train_loss = train_one_epoch(model, device, train_loader, criterion, optimizer, epoch)
        val_loss, val_acc = evaluate(model, device, val_loader, criterion, epoch)
        checkpoint_path = args.output_dir / f"checkpoint_epoch_{epoch}.pt"
        save_checkpoint(model, optimizer, epoch, checkpoint_path)

    # Final model export (optional – here we simply copy the last checkpoint)
    final_path = args.output_dir / "model_final.pt"
    torch.save(model.state_dict(), final_path)
    logging.info(f"Training complete. Final model saved to {final_path}")

if __name__ == "__main__":
    main()
