from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from torch.utils.data import DataLoader, TensorDataset, random_split

from models.lstm_transformer import LSTMTransformerClassifier

DATA_DIR = Path("data/processed/ml")
CHECKPOINT_PATH = Path("checkpoints/best_lstm_transformer.pt")
OUTPUT_DIR = Path("outputs/evaluation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 128
SEED = 42


def load_test_data():
    x = torch.tensor(np.load(DATA_DIR / "X.npy"), dtype=torch.float32)
    y = torch.tensor(np.load(DATA_DIR / "y.npy"), dtype=torch.long)

    dataset = TensorDataset(x, y)

    train_size = int(len(dataset) * 0.8)
    val_size = int(len(dataset) * 0.1)
    test_size = len(dataset) - train_size - val_size

    _, _, test_ds = random_split(
        dataset,
        [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(SEED),
    )

    return DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False)


@torch.no_grad()
def evaluate():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Device:", device)

    checkpoint = torch.load(CHECKPOINT_PATH, map_location=device)
    input_dim = checkpoint["input_dim"]

    model = LSTMTransformerClassifier(input_dim=input_dim).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    loader = load_test_data()

    all_labels = []
    all_preds = []
    all_probs = []

    for x, y in loader:
        x = x.to(device)

        logits = model(x)
        probs = torch.softmax(logits, dim=1)[:, 1]
        preds = torch.argmax(logits, dim=1)

        all_labels.extend(y.numpy())
        all_preds.extend(preds.cpu().numpy())
        all_probs.extend(probs.cpu().numpy())

    acc = accuracy_score(all_labels, all_preds)
    auc = roc_auc_score(all_labels, all_probs)
    cm = confusion_matrix(all_labels, all_preds)
    report = classification_report(all_labels, all_preds)

    print("=" * 60)
    print("Accuracy:", acc)
    print("ROC-AUC:", auc)
    print("Confusion Matrix:")
    print(cm)
    print("Classification Report:")
    print(report)

    pd.DataFrame(
        {
            "y_true": all_labels,
            "y_pred": all_preds,
            "prob_up": all_probs,
        }
    ).to_csv(OUTPUT_DIR / "predictions.csv", index=False)

    with open(OUTPUT_DIR / "metrics.txt", "w", encoding="utf-8") as f:
        f.write(f"Accuracy: {acc}\n")
        f.write(f"ROC-AUC: {auc}\n\n")
        f.write("Confusion Matrix:\n")
        f.write(str(cm))
        f.write("\n\nClassification Report:\n")
        f.write(report)

    print("Saved evaluation outputs to:", OUTPUT_DIR)


if __name__ == "__main__":
    evaluate()
