from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from ta import add_all_ta_features

RAW_DIR = Path("data/raw/yahoo")
OUT_DIR = Path("data/processed/features")


def clean_price_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").drop_duplicates("date")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    return df


def add_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["return_1d"] = df["close"].pct_change()
    df["log_return_1d"] = np.log(df["close"] / df["close"].shift(1))

    for window in [5, 10, 20, 50, 100, 200]:
        df[f"sma_{window}"] = df["close"].rolling(window).mean()
        df[f"ema_{window}"] = df["close"].ewm(span=window, adjust=False).mean()
        df[f"volatility_{window}"] = df["return_1d"].rolling(window).std()
        df[f"volume_sma_{window}"] = df["volume"].rolling(window).mean()

    for lag in [1, 2, 3, 5, 10, 20]:
        df[f"close_lag_{lag}"] = df["close"].shift(lag)
        df[f"return_lag_{lag}"] = df["return_1d"].shift(lag)

    df["target_return_1d"] = df["close"].shift(-1) / df["close"] - 1
    df["target_direction_1d"] = (df["target_return_1d"] > 0).astype(int)

    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_of_month"] = df["date"].dt.day
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["month"] = df["date"].dt.month
    df["quarter"] = df["date"].dt.quarter
    df["year"] = df["date"].dt.year

    return df


def add_ta_library_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df = add_all_ta_features(
        df,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        fillna=False,
    )

    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_price_data(df)
    df = add_basic_features(df)
    df = add_time_features(df)
    df = add_ta_library_features(df)

    df = df.replace([np.inf, -np.inf], np.nan)
    required_cols = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "return_1d",
        "target_return_1d",
        "target_direction_1d",
    ]

    df = df.dropna(subset=required_cols).reset_index(drop=True)
    return df


def process_file(path: Path) -> None:
    category = path.parent.name
    symbol = path.stem

    df = pd.read_parquet(path)
    features = build_features(df)

    out_dir = OUT_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)

    features.to_parquet(out_dir / f"{symbol}_features.parquet", index=False)
    features.to_csv(out_dir / f"{symbol}_features.csv", index=False)

    print(f"[OK] {category}/{symbol}: {features.shape}")


def main() -> None:
    files: list[Path] = []

    for category in ["stocks", "etfs", "indices", "crypto", "forex"]:
        files.extend((RAW_DIR / category).glob("*.parquet"))

    if not files:
        print("No parquet files found.")
        return

    for path in files:
        process_file(path)

    print("Feature engineering complete.")


if __name__ == "__main__":
    main()
