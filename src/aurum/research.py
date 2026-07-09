"""Real-data research feature engineering and versioned evidence helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime

import numpy as np
import pandas as pd

from .data.contracts import MarketBar


def validate_and_frame_bars(bars: Sequence[MarketBar]) -> pd.DataFrame:
    """Validate ordered OHLCV observations and derive leak-safe historical features."""
    if len(bars) < 30:
        raise ValueError("research validation requires at least 30 market bars")
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    if len({bar.timestamp for bar in ordered}) != len(ordered):
        raise ValueError("market bars contain duplicate timestamps")
    frame = pd.DataFrame(
        {
            "timestamp": [bar.timestamp for bar in ordered],
            "open": [bar.open for bar in ordered],
            "high": [bar.high for bar in ordered],
            "low": [bar.low for bar in ordered],
            "close": [bar.adjusted_close or bar.close for bar in ordered],
            "volume": [bar.volume for bar in ordered],
        }
    )
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (frame["high"] < frame[["open", "close"]].max(axis=1)).any():
        raise ValueError("high price violates OHLC bounds")
    if (frame["low"] > frame[["open", "close"]].min(axis=1)).any():
        raise ValueError("low price violates OHLC bounds")
    if (frame["volume"] < 0).any():
        raise ValueError("volume cannot be negative")
    frame["return_1d"] = frame["close"].pct_change()
    frame["return_5d"] = frame["close"].pct_change(5)
    frame["volatility_20d"] = frame["return_1d"].rolling(20).std()
    frame["momentum_20d"] = frame["close"] / frame["close"].shift(20) - 1
    frame["volume_zscore_20d"] = (frame["volume"] - frame["volume"].rolling(20).mean()) / frame[
        "volume"
    ].rolling(20).std().replace(0, np.nan)
    return frame


def market_dataset_hash(bars: Sequence[MarketBar]) -> str:
    payload = [
        bar.model_dump(mode="json")
        for bar in sorted(bars, key=lambda observation: observation.timestamp)
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def research_version(provider: str, symbol: str, retrieved_at: datetime) -> str:
    return f"{provider}:{symbol}:{retrieved_at.isoformat()}"
