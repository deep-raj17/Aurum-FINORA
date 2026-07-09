from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset, random_split

FEATURE_DIR = Path("data/processed/features")
OUTPUT_DIR = Path("data/processed/ml")
SEQUENCE_LENGTH = 60
TARGET_COLUMN = "target_direction_1d"


class FinancialSequenceDataset(Dataset):
    def __init__(self, x: np.ndarray, y: np.ndarray):
        self.x = torch.tensor(x, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, idx: int):
        return self.x[idx], self.y[idx]


def load_feature_files(category: str = "stocks") -> pd.DataFrame:
    files = list((FEATURE_DIR / category).glob("*_features.parquet"))

    if not files:
        raise FileNotFoundError(f"No feature files found in {FEATURE_DIR / category}")

    frames = []

    for file in files:
        df = pd.read_parquet(file)
        df["asset_id"] = file.stem.replace("_features", "")
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


def prepare_numeric_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    drop_cols = [
        "date",
        "symbol",
        "category",
        "source",
        "asset_id",
        "target_return_1d",
        "target_direction_1d",
    ]

    feature_cols = [
        col for col in df.columns if col not in drop_cols and pd.api.types.is_numeric_dtype(df[col])
    ]

    df = df.copy()

    df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], np.nan)
    df[feature_cols] = df[feature_cols].ffill().bfill().fillna(0)

    df = df.dropna(subset=[TARGET_COLUMN]).copy()
    df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)

    return df, feature_cols


def build_sequences(
    df: pd.DataFrame,
    feature_cols: list[str],
    sequence_length: int = SEQUENCE_LENGTH,
) -> tuple[np.ndarray, np.ndarray]:
    x_all = []
    y_all = []

    print("Total rows after prepare_numeric_features:", len(df))
    print("Feature columns:", len(feature_cols))

    for asset_id, group in df.groupby("asset_id"):
        group = group.sort_values("date").reset_index(drop=True)

        print(f"{asset_id}: rows={len(group)}")

        if len(group) <= sequence_length:
            continue

        features = group[feature_cols].values
        targets = group[TARGET_COLUMN].values

        scaler = StandardScaler()
        features = scaler.fit_transform(features)

        for i in range(sequence_length, len(group)):
            x_all.append(features[i - sequence_length : i])
            y_all.append(targets[i])

    print("Total sequences created:", len(x_all))

    if len(x_all) == 0:
        raise ValueError("No sequences created. Check feature_cols, NaNs, or sequence_length.")

    return np.stack(x_all).astype(np.float32), np.array(y_all, dtype=np.int64)


def save_ml_arrays(x: np.ndarray, y: np.ndarray) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUTPUT_DIR / "X.npy", x)
    np.save(OUTPUT_DIR / "y.npy", y)

    metadata = {
        "samples": int(x.shape[0]),
        "sequence_length": int(x.shape[1]),
        "num_features": int(x.shape[2]),
        "target": TARGET_COLUMN,
    }

    pd.DataFrame([metadata]).to_csv(OUTPUT_DIR / "dataset_metadata.csv", index=False)


def build_dataset(category: str = "stocks") -> tuple[np.ndarray, np.ndarray]:
    df = load_feature_files(category)
    df, feature_cols = prepare_numeric_features(df)
    x, y = build_sequences(df, feature_cols)
    save_ml_arrays(x, y)

    print("Dataset built successfully.")
    print("X shape:", x.shape)
    print("y shape:", y.shape)
    print("Number of features:", len(feature_cols))

    return x, y


def create_dataloaders(
    x: np.ndarray,
    y: np.ndarray,
    batch_size: int = 64,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
):
    dataset = FinancialSequenceDataset(x, y)

    train_size = int(len(dataset) * train_ratio)
    val_size = int(len(dataset) * val_ratio)
    test_size = len(dataset) - train_size - val_size

    train_ds, val_ds, test_ds = random_split(
        dataset,
        [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(42),
    )

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, test_loader


def main() -> None:
    x, y = build_dataset(category="stocks")

    train_loader, val_loader, test_loader = create_dataloaders(x, y)

    xb, yb = next(iter(train_loader))

    print("Train batch X:", xb.shape)
    print("Train batch y:", yb.shape)


if __name__ == "__main__":
    main()
