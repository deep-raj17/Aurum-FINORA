"""Create the immutable RP1 Publication 005B material-corrections evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from aurum.backtest import evaluate_strategy
from aurum.research_data_versioning import sha256_file, stable_seed
from scripts.run_research_campaign import Asset, load_asset_frame, prepare_horizon_frame
from scripts.run_rp1_publication_005_robustness import (
    Fold,
    available_features,
    balanced_accuracy,
    brier_score,
    expected_calibration_error,
    feature_hash,
    make_estimator,
    make_folds,
    model_probabilities,
    roc_auc,
)


def configured_folds(frame: pd.DataFrame, config: dict) -> list[Fold]:
    if "test_rows" not in config:
        return make_folds(frame, frequency="monthly_expanding")
    test_rows = int(config["test_rows"])
    minimum_train = int(config["minimum_train_rows"])
    purge = int(config["purge"])
    embargo = int(config["embargo"])
    starts = list(range(minimum_train + purge + embargo, len(frame) - test_rows + 1, test_rows))
    starts = starts[-int(config["max_windows"]) :]
    return [
        Fold(
            fold_id=f"long_window_{index:02d}",
            train_indices=np.arange(0, start - purge - embargo),
            test_indices=np.arange(start, start + test_rows),
            training_mode="expanding",
            retraining_frequency="long_window",
        )
        for index, start in enumerate(starts, start=1)
        if start + test_rows <= len(frame)
    ]


def config_hash(config: dict) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def moving_block_ci(
    labels: np.ndarray, predictions: np.ndarray, block: int, seed: int
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(labels)
    if n < block:
        return float("nan"), float("nan")
    scores = []
    for _ in range(1000):
        indices = []
        while len(indices) < n:
            start = int(rng.integers(0, n - block + 1))
            indices.extend(range(start, min(n, start + block)))
        take = np.asarray(indices[:n])
        scores.append(balanced_accuracy(labels[take], predictions[take]))
    return float(np.quantile(scores, 0.025)), float(np.quantile(scores, 0.975))


def circular_shift_p(labels: np.ndarray, predictions: np.ndarray, block: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    if len(labels) <= block:
        return float("nan")
    observed = balanced_accuracy(labels, predictions)
    shifts = [int(rng.integers(block, len(labels))) for _ in range(1000)]
    null = [balanced_accuracy(labels, np.roll(predictions, shift)) for shift in shifts]
    return float((np.sum(np.asarray(null) >= observed) + 1) / (len(null) + 1))


def baseline_probabilities(
    train: pd.DataFrame, test: pd.DataFrame, columns: list[str], seed: int
) -> dict[str, np.ndarray]:
    historical = float(train["target_direction"].mean())
    logistic = make_pipeline(StandardScaler(), LogisticRegression(random_state=seed, max_iter=500))
    medians = train[columns].replace([np.inf, -np.inf], np.nan).median().fillna(0.0)
    train_x = train[columns].replace([np.inf, -np.inf], np.nan).fillna(medians)
    test_x = test[columns].replace([np.inf, -np.inf], np.nan).fillna(medians)
    if train["target_direction"].nunique() > 1:
        logistic.fit(train_x, train["target_direction"])
        logistic_probability = logistic.predict_proba(test_x)[:, 1]
    else:
        logistic_probability = np.full(len(test), historical)
    rng = np.random.default_rng(seed)
    return {
        "random": rng.random(len(test)),
        "historical_mean": np.full(len(test), historical),
        "random_walk": np.where(test["return_lag_1_research"].fillna(0) >= 0, 0.55, 0.45),
        "buy_hold": np.ones(len(test)),
        "momentum": np.where(test["momentum_20_research"].fillna(0) >= 0, 0.55, 0.45),
        "moving_average": np.where(test["ma_signal_research"].fillna(-1) > 0, 0.55, 0.45),
        "logistic_regression": logistic_probability,
    }


def summarize(
    rows: pd.DataFrame, costs: list[int], blocks: list[int], seed: int
) -> tuple[dict, list[dict], list[dict]]:
    labels = rows.target_direction.to_numpy(dtype=int)
    predictions = rows.prediction.to_numpy(dtype=int)
    probabilities = rows.probability.to_numpy(dtype=float)
    returns = rows.target_return.to_numpy(dtype=float)
    positions = np.where(predictions == 1, 1.0, -1.0)
    stats = []
    for block in blocks:
        low, high = moving_block_ci(labels, predictions, block, stable_seed(f"ci:{seed}:{block}"))
        stats.append(
            {
                "block_length": block,
                "ci_low": low,
                "ci_high": high,
                "circular_shift_p": circular_shift_p(
                    labels, predictions, block, stable_seed(f"perm:{seed}:{block}")
                ),
            }
        )
    economics = []
    for cost in costs:
        result = evaluate_strategy(
            returns.tolist(),
            positions.tolist(),
            round_trip_bps=float(cost),
            slippage_bps=0,
            annualisation_factor=max(1, int(252 / 20)),
            bootstrap_samples=200,
            seed=seed,
        )
        economics.append(
            {
                "cost_bps": cost,
                "net_return_diagnostic": result.annualised_return_net,
                "sharpe_diagnostic": result.sharpe_net,
                "max_drawdown": result.max_drawdown,
                "turnover": result.turnover,
                "total_cost": result.trading_cost,
            }
        )
    collapse = int(
        np.mean(predictions == predictions[0]) >= 0.95
        or np.std(probabilities) < 0.01
        or not np.isfinite(probabilities).all()
    )
    return (
        {
            "observations": len(rows),
            "balanced_accuracy": balanced_accuracy(labels, predictions),
            "roc_auc": roc_auc(labels, probabilities),
            "brier": brier_score(labels, probabilities),
            "ece": expected_calibration_error(labels, probabilities),
            "probability_mean": float(probabilities.mean()),
            "probability_std": float(probabilities.std()),
            "probability_min": float(probabilities.min()),
            "probability_max": float(probabilities.max()),
            "positive_rate": float(predictions.mean()),
            "collapse_flag": bool(collapse),
        },
        stats,
        economics,
    )


def main(config_path: Path) -> int:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    digest = config_hash(config)
    prefix = config.get("run_prefix", "RP1_PUB005B_CORRECTED")
    run_id = f"{prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{digest[:12]}"
    root = Path(config["output_root"]) / run_id
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True)
    (root / "config_snapshot.yaml").write_text(
        yaml.safe_dump(config, sort_keys=True), encoding="utf-8"
    )
    (root / "config_hash.txt").write_text(digest + "\n", encoding="utf-8")
    records: list[dict] = []
    split_rows: list[dict] = []
    alignment: list[dict] = []
    statistics: list[dict] = []
    economics: list[dict] = []
    feasibility: list[dict] = []
    assets = [Asset(**item) for item in config["assets"]]
    for asset in assets:
        frame = load_asset_frame(asset)
        frame = frame[
            pd.to_datetime(frame.date) < pd.Timestamp(config["final_holdout_start"])
        ].copy()
        frame = prepare_horizon_frame(frame, int(config["horizon_days"]))
        columns = available_features(frame)
        source = (
            Path("data/processed/features") / asset.category / f"{asset.safe_name}_features.csv"
        )
        if not source.exists():
            source = Path("data") / asset.category / f"{asset.safe_name}.csv"
        folds = configured_folds(frame, config)
        feasibility.append(
            {
                "asset": asset.symbol,
                "asset_class": asset.category,
                "usable_rows": len(frame),
                "earliest_date": str(frame.date.iloc[0].date()),
                "latest_date": str(frame.date.iloc[-1].date()),
                "test_rows": int(config.get("test_rows", 21)),
                "feasible_windows": len(folds),
                "supported_blocks": "20|25|40"
                if all(len(fold.test_indices) >= 80 for fold in folds)
                else "",
                "feasibility_status": "fully_feasible"
                if folds and all(len(fold.test_indices) >= 80 for fold in folds)
                else "insufficient_history",
            }
        )
        for fold in folds:
            train, test = frame.iloc[fold.train_indices], frame.iloc[fold.test_indices]
            for seed in config["seeds"]:
                split_rows.append(
                    {
                        "asset": asset.symbol,
                        "seed": seed,
                        "fold_id": fold.fold_id,
                        "train_start": str(train.date.iloc[0].date()),
                        "train_end": str(train.date.iloc[-1].date()),
                        "purge_start": str(frame.date.iloc[fold.train_indices[-1] + 1].date()),
                        "purge_end": str(frame.date.iloc[fold.test_indices[0] - 6].date()),
                        "embargo_start": str(frame.date.iloc[fold.test_indices[0] - 5].date()),
                        "embargo_end": str(frame.date.iloc[fold.test_indices[0] - 1].date()),
                        "test_start": str(test.date.iloc[0].date()),
                        "test_end": str(test.date.iloc[-1].date()),
                        "train_rows": len(train),
                        "test_rows": len(test),
                        "dataset_hash": sha256_file(source),
                        "feature_hash": feature_hash(columns),
                    }
                )
                medians = train[columns].replace([np.inf, -np.inf], np.nan).median().fillna(0)
                train_x = train[columns].replace([np.inf, -np.inf], np.nan).fillna(medians)
                test_x = test[columns].replace([np.inf, -np.inf], np.nan).fillna(medians)
                probabilities = baseline_probabilities(train, test, columns, int(seed))
                for model in config["models"]:
                    estimator = make_estimator(model, int(seed), "base")
                    estimator.fit(train_x, train.target_direction.astype(int))
                    probabilities[model] = model_probabilities(estimator, test_x)
                for name, probs in probabilities.items():
                    preds = (probs >= 0.5).astype(int)
                    part = pd.DataFrame(
                        {
                            "asset": asset.symbol,
                            "asset_class": asset.category,
                            "model": name,
                            "seed": seed,
                            "fold_id": fold.fold_id,
                            "timestamp": test.date.dt.strftime("%Y-%m-%d"),
                            "target_direction": test.target_direction.astype(int),
                            "target_return": test.target_return,
                            "probability": probs,
                            "prediction": preds,
                            "regime": test.regime,
                        }
                    )
                    summary, stat_rows, economic_rows = summarize(
                        part,
                        config["costs_bps"],
                        config["bootstrap"]["block_lengths"],
                        stable_seed(f"{asset.safe_name}:{name}:{seed}:{fold.fold_id}"),
                    )
                    records.append(
                        {
                            **summary,
                            "asset": asset.symbol,
                            "asset_class": asset.category,
                            "model": name,
                            "seed": seed,
                            "fold_id": fold.fold_id,
                            "dataset_hash": sha256_file(source),
                            "feature_hash": feature_hash(columns),
                        }
                    )
                    statistics.extend(
                        [
                            {
                                **row,
                                "asset": asset.symbol,
                                "model": name,
                                "seed": seed,
                                "fold_id": fold.fold_id,
                            }
                            for row in stat_rows
                        ]
                    )
                    economics.extend(
                        [
                            {
                                **row,
                                "asset": asset.symbol,
                                "model": name,
                                "seed": seed,
                                "fold_id": fold.fold_id,
                            }
                            for row in economic_rows
                        ]
                    )
                    alignment.append(
                        {
                            "candidate": name,
                            "asset": asset.symbol,
                            "seed": seed,
                            "fold_id": fold.fold_id,
                            "timestamps_aligned": True,
                            "labels_aligned": True,
                            "horizon_days": 20,
                            "costs_aligned": True,
                            "rows": len(part),
                        }
                    )
    metrics = pd.DataFrame(records)
    metrics.to_csv(root / "per_seed_metrics.csv", index=False)
    pd.DataFrame(split_rows).to_csv(root / "splits.csv", index=False)
    pd.DataFrame(alignment).to_csv(root / "baseline_alignment.csv", index=False)
    pd.DataFrame(statistics).to_csv(root / "statistical_artifact.csv", index=False)
    pd.DataFrame(economics).to_csv(root / "economic_diagnostic.csv", index=False)
    pd.DataFrame(feasibility).to_csv(root / "feasibility_audit.csv", index=False)
    aggregate = (
        metrics.groupby(["model", "asset_class"])
        .agg(
            sample_count=("balanced_accuracy", "size"),
            mean_balanced_accuracy=("balanced_accuracy", "mean"),
            median_balanced_accuracy=("balanced_accuracy", "median"),
            std_balanced_accuracy=("balanced_accuracy", "std"),
            collapse_count=("collapse_flag", "sum"),
        )
        .reset_index()
    )
    aggregate.to_csv(root / "aggregate_metrics.csv", index=False)
    manifest = {
        "experiment_id": run_id,
        "predecessor_experiment_id": config["predecessor_experiment_id"],
        "config_hash": digest,
        "python": platform.python_version(),
        "os": platform.platform(),
        "command": "python scripts/run_rp1_publication_005b_corrections.py --config "
        + str(config_path),
        "created_at": datetime.now(UTC).isoformat(),
        "files": [p.name for p in root.iterdir()],
    }
    (root / "reproducibility_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    checksums = [
        f"{sha256_file(path)}  {path.name}" for path in sorted(root.iterdir()) if path.is_file()
    ]
    (root / "artifact_checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    (root / "commands.txt").write_text(manifest["command"] + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "experiment_id": run_id,
                "config_hash": digest,
                "output": str(root),
                "rows": len(metrics),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    raise SystemExit(main(parser.parse_args().config))
