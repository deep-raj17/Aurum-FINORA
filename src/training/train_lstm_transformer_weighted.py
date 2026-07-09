from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.utils.class_weight import compute_class_weight
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, TensorDataset, random_split
from tqdm import tqdm

from models.lstm_transformer import LSTMTransformerClassifier

DATA_DIR = Path("data/processed/ml")
CHECKPOINT_DIR = Path("checkpoints")
CHECKPOINT_DIR.mkdir(exist_ok=True)

BATCH_SIZE = 64
EPOCHS = 20
LR = 1e-4
WEIGHT_DECAY = 1e-4
SEED = 42


def load_data():
    X = np.load(DATA_DIR / "X.npy")
    y = np.load(DATA_DIR / "y.npy")

    X = torch.tensor(X, dtype=torch.float32)
    y = torch.tensor(y, dtype=torch.long)

    dataset = TensorDataset(X, y)

    train_size = int(len(dataset) * 0.8)
    val_size = int(len(dataset) * 0.1)
    test_size = len(dataset) - train_size - val_size

    train_ds, val_ds, test_ds = random_split(
        dataset,
        [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(SEED),
    )

    return train_ds, val_ds, test_ds


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()

    losses = []
    labels = []
    preds = []
    probs = []

    for x, y in loader:
        x = x.to(device)
        y = y.to(device)

        logits = model(x)
        loss = criterion(logits, y)

        losses.append(loss.item())

        p = torch.softmax(logits, dim=1)[:, 1]

        labels.extend(y.cpu().numpy())
        preds.extend(torch.argmax(logits, dim=1).cpu().numpy())
        probs.extend(p.cpu().numpy())

    return (
        np.mean(losses),
        accuracy_score(labels, preds),
        roc_auc_score(labels, probs),
    )


def train_epoch(model, loader, criterion, optimizer, scaler, device):
    model.train()

    losses = []
    labels = []
    preds = []

    for x, y in tqdm(loader, leave=False):
        x = x.to(device)
        y = y.to(device)

        optimizer.zero_grad(set_to_none=True)

        with torch.cuda.amp.autocast(enabled=device == "cuda"):
            logits = model(x)
            loss = criterion(logits, y)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()

        losses.append(loss.item())

        labels.extend(y.cpu().numpy())
        preds.extend(torch.argmax(logits, dim=1).cpu().numpy())

    return (
        np.mean(losses),
        accuracy_score(labels, preds),
    )


def main():
    torch.manual_seed(SEED)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Device:", device)

    train_ds, val_ds, test_ds = load_data()

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE)

    sample_x, _ = train_ds[0]
    input_dim = sample_x.shape[-1]

    model = LSTMTransformerClassifier(input_dim=input_dim).to(device)

    train_labels = np.array([train_ds[i][1].item() for i in range(len(train_ds))])

    weights = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(train_labels),
        y=train_labels,
    )

    weights = torch.tensor(weights, dtype=torch.float32, device=device)

    print("Class weights:", weights)

    criterion = nn.CrossEntropyLoss(weight=weights)

    optimizer = AdamW(
        model.parameters(),
        lr=LR,
        weight_decay=WEIGHT_DECAY,
    )

    scheduler = CosineAnnealingLR(optimizer, T_max=EPOCHS)

    scaler = torch.cuda.amp.GradScaler(enabled=device == "cuda")

    best_auc = 0.0

    for epoch in range(EPOCHS):
        train_loss, train_acc = train_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            scaler,
            device,
        )

        val_loss, val_acc, val_auc = evaluate(
            model,
            val_loader,
            criterion,
            device,
        )

        scheduler.step()

        print(
            f"Epoch {epoch + 1:02d}/{EPOCHS} "
            f"| Train Loss {train_loss:.4f} "
            f"| Train Acc {train_acc:.4f} "
            f"| Val Loss {val_loss:.4f} "
            f"| Val Acc {val_acc:.4f} "
            f"| Val AUC {val_auc:.4f}"
        )

        if val_auc > best_auc:
            best_auc = val_auc

            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "input_dim": input_dim,
                    "val_auc": val_auc,
                },
                CHECKPOINT_DIR / "best_lstm_transformer_weighted.pt",
            )

            print("Saved best model.")

    test_loss, test_acc, test_auc = evaluate(
        model,
        test_loader,
        criterion,
        device,
    )

    print("=" * 70)
    print("Test Accuracy :", test_acc)
    print("Test ROC-AUC  :", test_auc)
    print("Best Val AUC  :", best_auc)


if __name__ == "__main__":
    main()
