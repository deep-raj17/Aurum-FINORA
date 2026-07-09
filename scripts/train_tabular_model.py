"""Train and persist a chronological XGBoost/LightGBM FINORA model."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--engine", choices=["xgboost", "lightgbm"], required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--features", required=True, help="Comma-separated feature columns")
    parser.add_argument("--output", type=Path, default=Path("artifacts/tabular"))
    parser.add_argument("--gpu", choices=["auto", "on", "off"], default="auto")
    args = parser.parse_args()

    frame = (
        pd.read_parquet(args.dataset)
        if args.dataset.suffix.lower() == ".parquet"
        else pd.read_csv(args.dataset)
    )
    features = [value.strip() for value in args.features.split(",") if value.strip()]
    required = [*features, args.target]
    if missing := [column for column in required if column not in frame]:
        raise SystemExit(f"missing columns: {missing}")
    clean = frame[required].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 100:
        raise SystemExit("at least 100 complete chronological rows are required")
    split = int(len(clean) * 0.8)
    train, test = clean.iloc[:split], clean.iloc[split:]
    use_gpu = args.gpu != "off"
    if args.engine == "xgboost":
        from xgboost import XGBRegressor

        model = XGBRegressor(
            objective="reg:squarederror",
            n_estimators=500,
            max_depth=5,
            learning_rate=0.03,
            subsample=0.85,
            colsample_bytree=0.85,
            tree_method="hist",
            device="cuda" if use_gpu else "cpu",
            random_state=17,
        )
        try:
            model.fit(train[features], train[args.target])
        except Exception:
            if args.gpu == "on":
                raise
            model.set_params(device="cpu")
            model.fit(train[features], train[args.target])
    else:
        from lightgbm import LGBMRegressor

        parameters = {
            "n_estimators": 500,
            "num_leaves": 31,
            "learning_rate": 0.03,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "random_state": 17,
            "verbosity": -1,
            "device_type": "gpu" if use_gpu else "cpu",
        }
        model = LGBMRegressor(**parameters)
        try:
            model.fit(train[features], train[args.target])
        except Exception:
            if args.gpu == "on":
                raise
            parameters["device_type"] = "cpu"
            model = LGBMRegressor(**parameters)
            model.fit(train[features], train[args.target])

    prediction = np.asarray(model.predict(test[features]), dtype=float)
    actual = test[args.target].to_numpy(dtype=float)
    args.output.mkdir(parents=True, exist_ok=True)
    model_path = args.output / f"{args.engine}-{args.target}.json"
    if args.engine == "xgboost":
        model.save_model(model_path)
    else:
        model.booster_.save_model(str(model_path))
    importance = dict(
        zip(features, np.asarray(model.feature_importances_, dtype=float).tolist(), strict=True)
    )
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "engine": args.engine,
        "target": args.target,
        "features": features,
        "train_rows": len(train),
        "test_rows": len(test),
        "chronological_split": True,
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "model_path": str(model_path),
        "rmse": float(np.sqrt(np.mean((actual - prediction) ** 2))),
        "mae": float(np.mean(np.abs(actual - prediction))),
        "feature_importance": importance,
        "intended_tasks": [
            "tabular forecasting",
            "risk prediction",
            "crash probability",
            "drawdown prediction",
            "residual correction",
        ],
    }
    (args.output / f"{args.engine}-{args.target}-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
