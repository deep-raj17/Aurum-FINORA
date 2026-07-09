"""Run a real-provider, walk-forward FINORA research validation."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

from aurum.data.connectors import (
    AlphaVantageConnector,
    FinnhubConnector,
    StooqConnector,
    TiingoConnector,
    YahooFinanceConnector,
)
from aurum.data.contracts import SyncRequest
from aurum.data.quality import MarketDataQualityEngine
from aurum.forecast_system import (
    Chronos2Specialist,
    NeuralForecastSpecialist,
    TreeQuantileSpecialist,
)
from aurum.production_validation import (
    CalibrationDataset,
    WindowMode,
    evaluate_calibration_dataset,
    walk_forward_records,
)
from aurum.research import market_dataset_hash, research_version, validate_and_frame_bars


def _connector(name: str):
    if name == "alpha-vantage":
        return AlphaVantageConnector()
    if name == "tiingo":
        return TiingoConnector()
    if name == "finnhub":
        return FinnhubConnector()
    if name == "yahoo":
        return YahooFinanceConnector()
    return StooqConnector()


def _specialist(name: str, lags: int):
    if name in {"xgboost", "lightgbm"}:
        return TreeQuantileSpecialist(name, lags=lags)
    if name == "chronos":
        return Chronos2Specialist(
            os.getenv("FINORA_CHRONOS_MODEL_ID", "amazon/chronos-t5-tiny"),
            cache_dir=os.getenv("FINORA_MODEL_CACHE_DIR"),
        )
    return NeuralForecastSpecialist(name, input_size=lags, max_steps=100)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        choices=["alpha-vantage", "tiingo", "finnhub", "yahoo", "stooq"],
        default="yahoo",
    )
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument(
        "--model",
        choices=["xgboost", "lightgbm", "chronos", "patchtst", "tft", "nhits"],
        default="xgboost",
    )
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--lags", type=int, default=30)
    parser.add_argument("--window", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--output", type=Path, default=Path("reports/research"))
    args = parser.parse_args()

    end = datetime.now(UTC) - timedelta(days=1)
    request = SyncRequest(
        symbol=args.symbol,
        start=end - timedelta(days=args.days),
        end=end,
    )
    result = _connector(args.provider).fetch(request)
    quality = MarketDataQualityEngine().validate(result.bars)
    quality.raise_if_rejected()
    frame = validate_and_frame_bars(result.bars)
    values = frame["close"].to_numpy(dtype=float)
    dates = [timestamp.date() for timestamp in frame["timestamp"]]
    model = _specialist(args.model, args.lags)

    def predict(train: np.ndarray, horizon: int) -> tuple[float, float, float]:
        training_dates = [date(2000, 1, 1) + timedelta(days=index) for index in range(len(train))]
        forecast = model.forecast(train, training_dates, horizon)
        return (
            float(forecast.mean[-1]),
            float(forecast.quantiles[0.1][-1]),
            float(forecast.quantiles[0.9][-1]),
        )

    mode = WindowMode(args.window)
    records = walk_forward_records(
        values,
        dates,
        predict,
        horizon=args.horizon,
        minimum_train_size=max(60, args.lags + args.horizon + 20),
        mode=mode,
        rolling_window=min(252, len(values)),
    )
    dataset_hash = market_dataset_hash(result.bars)
    dataset = CalibrationDataset(
        name=f"{args.provider}:{args.symbol}",
        version=research_version(args.provider, args.symbol, result.metadata.retrieved_at),
        records=records,
        source_hashes=[dataset_hash],
    )
    report = evaluate_calibration_dataset(dataset, window_mode=mode)
    args.output.mkdir(parents=True, exist_ok=True)
    stem = f"{args.provider}-{args.symbol}-{args.model}-{args.window}".lower()
    dataset.write_jsonl(args.output / f"{stem}-calibration.jsonl")
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "research_only": True,
        "provider": args.provider,
        "symbol": args.symbol,
        "model": args.model,
        "quality": quality.model_dump(mode="json"),
        "feature_columns": list(frame.columns),
        "source_dataset_hash": dataset_hash,
        "validation": report.model_dump(mode="json"),
        "claims": {
            "alpha": False,
            "reason": "Research output requires benchmark, cost, OOS and regime review",
        },
    }
    (args.output / f"{stem}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.output / f"{stem}.json"), "records": len(records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
