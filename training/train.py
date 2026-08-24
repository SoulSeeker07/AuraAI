#!/usr/bin/env python3
"""training/train.py

Self‑contained script for training a simple convolutional neural network on the MNIST dataset.

Features
--------
- Data loading and preprocessing using torchvision.
- Configurable hyper‑parameters via command‑line arguments or a JSON configuration file.
- Model definition (a small CNN) built with PyTorch.
- Training loop with tqdm progress bar and logging of loss/accuracy.
- Validation after each epoch and optional test‑set evaluation.
- Model checkpoint saved to disk.
- Simple logging setup.

Usage example::

    python -m training.train --config config.json
    # or with explicit arguments
    python -m training.train --epochs 10 --batch-size 64 --lr 0.001

"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
import torchvision
import torchvision.transforms as transforms
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Model definition
# ---------------------------------------------------------------------------

class SimpleCNN(nn.Module):
    """A tiny CNN for MNIST (28x28 grayscale)."""

    def __init__(self, num_classes: int = 10) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 7 * 7, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.classifier(x)
        return x

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def get_data_loaders(batch_size: int, val_split: float = 0.1) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """Create train/validation/test loaders for MNIST.

    Args:
        batch_size: Batch size for all loaders.
        val_split: Fraction of the training set to use for validation.
    """
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))
    ])

    full_train = torchvision.datasets.MNIST(root="./data", train=True, download=True, transform=transform)
    test_set = torchvision.datasets.MNIST(root="./data", train=False, download=True, transform=transform)

    val_len = int(len(full_train) * val_split)
    train_len = len(full_train) - val_len
    train_set, val_set = random_split(full_train, [train_len, val_len])

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)

    return train_loader, val_loader, test_loader


def evaluate(model: nn.Module, loader: DataLoader, criterion: nn.Module, device: torch.device) -> Tuple[float, float]:
    """Run evaluation on a dataset.

    Returns:
        (average_loss, accuracy)
    """
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    with torch.no_grad():
        for inputs, targets in loader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            running_loss += loss.item() * inputs.size(0)
            _, preds = torch.max(outputs, 1)
            correct += (preds == targets).sum().item()
            total += targets.size(0)
    avg_loss = running_loss / total
    acc = correct / total
    return avg_loss, acc


def save_checkpoint(state: Dict[str, Any], checkpoint_dir: Path) -> None:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / "model_latest.pth"
    torch.save(state, path)
    logging.info(f"Model checkpoint saved to {path}")

# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train(config: Dict[str, Any]) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logging.info(f"Using device: {device}")

    # Hyper‑parameters
    batch_size = config.get("batch_size", 64)
    epochs = config.get("epochs", 10)
    lr = config.get("learning_rate", 1e-3)
    optimizer_name = config.get("optimizer", "adam").lower()
    model_dir = Path(config.get("output_dir", "./output"))

    # Data
    train_loader, val_loader, test_loader = get_data_loaders(batch_size)

    # Model, loss, optimizer
    model = SimpleCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    if optimizer_name == "sgd":
        optimizer = optim.SGD(model.parameters(), lr=lr, momentum=0.9)
    else:  # default Adam
        optimizer = optim.Adam(model.parameters(), lr=lr)

    # Training
    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        correct = 0
        total = 0
        prog_bar = tqdm(train_loader, desc=f"Epoch {epoch}/{epochs}", unit="batch")
        for inputs, targets in prog_bar:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item() * inputs.size(0)
            _, preds = torch.max(outputs, 1)
            correct += (preds == targets).sum().item()
            total += targets.size(0)
            prog_bar.set_postfix(loss=loss.item())

        avg_train_loss = epoch_loss / total
        train_acc = correct / total
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)
        logging.info(
            f"Epoch [{epoch}/{epochs}] - Train loss: {avg_train_loss:.4f}, "
            f"Train acc: {train_acc:.4f}, Val loss: {val_loss:.4f}, Val acc: {val_acc:.4f}"
        )
        # Save checkpoint after each epoch
        checkpoint_state = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "train_loss": avg_train_loss,
            "val_loss": val_loss,
        }
        save_checkpoint(checkpoint_state, model_dir)

    # Final evaluation on test set (optional)
    if config.get("evaluate_test", True):
        test_loss, test_acc = evaluate(model, test_loader, criterion, device)
        logging.info(f"Test loss: {test_loss:.4f}, Test accuracy: {test_acc:.4f}")
        # Save final model
        final_path = model_dir / "model_final.pth"
        torch.save(model.state_dict(), final_path)
        logging.info(f"Final model saved to {final_path}")

# ---------------------------------------------------------------------------
# Argument parsing / configuration handling
# ---------------------------------------------------------------------------

def load_config_from_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def merge_configs(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result = base.copy()
    result.update({k: v for k, v in overrides.items() if v is not None})
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Train a simple CNN on MNIST.")
    parser.add_argument("--config", type=str, help="Path to JSON configuration file.")
    parser.add_argument("--batch-size", type=int, help="Batch size.")
    parser.add_argument("--epochs", type=int, help="Number of training epochs.")
    parser.add_argument("--learning-rate", type=float, help="Learning rate.")
    parser.add_argument("--optimizer", type=str, choices=["adam", "sgd"], help="Optimizer type.")
    parser.add_argument("--output-dir", type=str, help="Directory to save model checkpoints.")
    parser.add_argument("--evaluate-test", action="store_true", help="Evaluate on the test set after training.")
    args = parser.parse_args()

    # Base configuration (defaults)
    config: Dict[str, Any] = {}

    # Load from file if provided
    if args.config:
        file_cfg = load_config_from_file(args.config)
        config = merge_configs(config, file_cfg)

    # Override with CLI arguments
    cli_cfg = {
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "optimizer": args.optimizer,
        "output_dir": args.output_dir,
        "evaluate_test": args.evaluate_test,
    }
    config = merge_configs(config, cli_cfg)

    # Logging setup
    log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.info("Configuration: %s", json.dumps(config, indent=2))
    train(config)

if __name__ == "__main__":
    main()
