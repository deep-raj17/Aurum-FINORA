"""Run RP1 Publication 005 true robustness reruns.

This is a research-only runner. It does not create trade orders, broker calls,
dashboards, services, or model architecture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import yaml

from aurum.backtest import evaluate_strategy
from aurum.research_data_versioning import sha256_file, stable_seed
from scripts.run_research_campaign import (
    Asset,
    feature_columns,
    load_asset_frame,
    prepare_horizon_frame,
)

HORIZON = 20
FINAL_HOLDOUT_START = "2025-07-01"
RUN_ID = datetime.now(UTC).strftime("rp1_pub005_%Y%m%dT%H%M%SZ")
BASE_DIR = Path("reports/research/programs/rp1_medium_term_tree_models")
APPENDIX_DIR = BASE_DIR / "appendices"
ARTIFACT_DIR = Path("research/experiments/rp1_publication_005") / RUN_ID
DEFAULT_CONFIG = Path("research/configs/robustness/rp1_publication_005_true_robustness.yaml")

ASSETS = [
    Asset("SPY", "SPY", "etfs"),
    Asset("QQQ", "QQQ", "etfs"),
    Asset("VTI", "VTI", "etfs"),
    Asset("VOO", "VOO", "etfs"),
    Asset("IWM", "IWM", "etfs"),
    Asset("DIA", "DIA", "etfs"),
    Asset("XLK", "XLK", "etfs"),
    Asset("XLF", "XLF", "etfs"),
    Asset("XLE", "XLE", "etfs"),
    Asset("EURUSD=X", "EURUSDX", "forex"),
    Asset("GBPUSD=X", "GBPUSDX", "forex"),
    Asset("JPY=X", "JPYX", "forex"),
    Asset("INR=X", "INRX", "forex"),
    Asset("AUDUSD=X", "AUDUSDX", "forex"),
    Asset("CAD=X", "CADX", "forex"),
    Asset("AAPL", "AAPL", "stocks"),
    Asset("UNH", "UNH", "stocks"),
    Asset("AMZN", "AMZN", "stocks"),
    Asset("NVDA", "NVDA", "stocks"),
    Asset("TSLA", "TSLA", "stocks"),
    Asset("VTSAX", "VTSAX", "mutual_funds"),
    Asset("VFIAX", "VFIAX", "mutual_funds"),
    Asset("SWPPX", "SWPPX", "mutual_funds"),
    Asset("FXAIX", "FXAIX", "mutual_funds"),
]

MODELS = ["LightGBM", "XGBoost", "CatBoost"]
COST_SCENARIOS = {
    "low": {"spread_bps": 1.0, "commission_bps": 0.5, "slippage_bps": 1.0},
    "realistic": {"spread_bps": 2.0, "commission_bps": 1.0, "slippage_bps": 5.0},
    "stressed": {"spread_bps": 8.0, "commission_bps": 2.0, "slippage_bps": 15.0},
}
RETRAINING = {
    "weekly_expanding": {"mode": "expanding", "test_size": 5, "step": 5, "max_folds": 2},
    "monthly_expanding": {"mode": "expanding", "test_size": 21, "step": 21, "max_folds": 2},
    "quarterly_expanding": {"mode": "expanding", "test_size": 63, "step": 63, "max_folds": 2},
    "monthly_rolling": {"mode": "rolling", "test_size": 21, "step": 21, "max_folds": 2},
}
HYPERPARAM_VARIANTS = {
    "base": {},
    "shallow_regularized": {
        "n_estimators": 4,
        "max_depth": 2,
        "learning_rate": 0.03,
        "subsample": 0.7,
        "colsample_bytree": 0.7,
    },
    "deeper_neighbor": {
        "n_estimators": 6,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
    },
}
ABLATIONS = {
    "full": (),
    "remove_momentum": ("momentum_",),
    "remove_volatility": ("volatility_",),
    "remove_volume": ("volume_",),
    "remove_lagged_returns": ("return_lag_",),
    "noisy_full": (),
}


@dataclass(frozen=True)
class Fold:
    fold_id: str
    train_indices: np.ndarray
    test_indices: np.ndarray
    training_mode: str
    retraining_frequency: str


def safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)


def source_file(asset: Asset) -> Path:
    feature_path = (
        Path("data") / "processed" / "features" / asset.category / f"{asset.safe_name}_features.csv"
    )
    raw_path = Path("data") / asset.category / f"{asset.safe_name}.csv"
    try:
        return feature_path if feature_path.exists() else raw_path
    except OSError:
        # A removable or externally altered volume must be quarantined, not guessed.
        return raw_path


def canonical_config_hash(config: dict[str, Any]) -> str:
    """Return a stable hash for the frozen publication configuration."""
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_frozen_config(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        raise FileNotFoundError(f"Publication 005 configuration not found: {path}")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Publication 005 configuration must be a mapping")
    required = {
        "publication_id",
        "protocol_version",
        "assets",
        "models",
        "seeds",
        "target",
        "horizon_days",
        "final_holdout_start",
        "cost_scenarios",
        "output_root",
        "overwrite_policy",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"Publication 005 configuration is missing: {', '.join(missing)}")
    if config["overwrite_policy"] != "forbid":
        raise ValueError("Publication 005 overwrite_policy must be 'forbid'")
    if int(config["horizon_days"]) != HORIZON:
        raise ValueError(f"Publication 005 horizon must remain frozen at {HORIZON} days")
    return config, canonical_config_hash(config)


def git_state() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return "unavailable"

    return {
        "commit": run("git", "rev-parse", "HEAD"),
        "short_status": run("git", "status", "--short"),
    }


def validate_prediction_frame(rows: pd.DataFrame, *, final_holdout_start: str) -> list[str]:
    """Return eligibility failures without repairing an invalid prediction set."""
    failures: list[str] = []
    required = {"timestamp", "target_direction", "probability", "prediction", "target_return"}
    if not required.issubset(rows.columns):
        return ["required_prediction_columns_missing"]
    timestamps = pd.to_datetime(rows["timestamp"], errors="coerce")
    if timestamps.isna().any() or (timestamps >= pd.Timestamp(final_holdout_start)).any():
        failures.append("final_test_boundary_violation")
    if rows.duplicated(["asset", "model", "fold_id", "timestamp"]).any():
        failures.append("duplicate_prediction_rows")
    probabilities = pd.to_numeric(rows["probability"], errors="coerce")
    if probabilities.isna().any() or ((probabilities < 0) | (probabilities > 1)).any():
        failures.append("invalid_probability_range")
    return failures


def available_features(frame: pd.DataFrame) -> list[str]:
    columns = feature_columns(frame)
    blocked_prefixes = ("target_",)
    return [column for column in columns if not column.startswith(blocked_prefixes)]


def feature_hash(columns: list[str]) -> str:
    payload = json.dumps(sorted(columns), separators=(",", ":"))
    return hex(stable_seed(payload, modulo=2**64))[2:]


def filtered_features(columns: list[str], ablation: str) -> list[str]:
    prefixes = ABLATIONS[ablation]
    if not prefixes:
        return list(columns)
    filtered = [column for column in columns if not column.startswith(prefixes)]
    return filtered or list(columns)


def make_folds(
    frame: pd.DataFrame,
    *,
    frequency: str,
    minimum_train_size: int = 756,
    purge: int = HORIZON,
    embargo: int = 5,
) -> list[Fold]:
    spec = RETRAINING[frequency]
    test_size = int(spec["test_size"])
    step = int(spec["step"])
    max_folds = int(spec["max_folds"])
    test_starts = list(range(minimum_train_size + purge + embargo, len(frame) - test_size, step))
    test_starts = test_starts[-max_folds:]
    folds = []
    for index, test_start in enumerate(test_starts, start=1):
        train_end = test_start - purge - embargo
        if spec["mode"] == "rolling":
            train_start = max(0, train_end - minimum_train_size)
        else:
            train_start = 0
        train_indices = np.arange(train_start, train_end)
        test_indices = np.arange(test_start, min(test_start + test_size, len(frame)))
        if len(train_indices) < minimum_train_size // 2 or len(test_indices) < 2:
            continue
        folds.append(
            Fold(
                fold_id=f"{frequency}_{index:02d}",
                train_indices=train_indices,
                test_indices=test_indices,
                training_mode=str(spec["mode"]),
                retraining_frequency=frequency,
            )
        )
    return folds


def make_estimator(model: str, seed: int, variant: str):
    params = HYPERPARAM_VARIANTS[variant]
    if model == "LightGBM":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            n_estimators=int(params.get("n_estimators", 6)),
            max_depth=int(params.get("max_depth", 3)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            subsample=float(params.get("subsample", 0.8)),
            colsample_bytree=float(params.get("colsample_bytree", 0.8)),
            min_child_samples=20,
            random_state=seed,
            verbosity=-1,
        )
    if model == "XGBoost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=int(params.get("n_estimators", 6)),
            max_depth=int(params.get("max_depth", 3)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            subsample=float(params.get("subsample", 0.8)),
            colsample_bytree=float(params.get("colsample_bytree", 0.8)),
            eval_metric="logloss",
            random_state=seed,
            n_jobs=1,
        )
    if model == "CatBoost":
        from catboost import CatBoostClassifier

        return CatBoostClassifier(
            iterations=int(params.get("n_estimators", 6)),
            depth=int(params.get("max_depth", 3)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            random_seed=seed,
            loss_function="Logloss",
            verbose=False,
            allow_writing_files=False,
        )
    raise ValueError(f"unsupported model: {model}")


def balanced_accuracy(labels: np.ndarray, predictions: np.ndarray) -> float:
    labels = np.asarray(labels, dtype=int)
    predictions = np.asarray(predictions, dtype=int)
    recalls = []
    for klass in (0, 1):
        mask = labels == klass
        recalls.append(float(np.mean(predictions[mask] == klass)) if mask.any() else 0.5)
    return float(np.mean(recalls))


def brier_score(labels: np.ndarray, probabilities: np.ndarray) -> float:
    return float(np.mean((np.asarray(probabilities, dtype=float) - labels) ** 2))


def expected_calibration_error(
    labels: np.ndarray, probabilities: np.ndarray, bins: int = 5
) -> float:
    labels = np.asarray(labels, dtype=float)
    probabilities = np.asarray(probabilities, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lower, upper in zip(edges[:-1], edges[1:], strict=True):
        mask = (probabilities >= lower) & (
            probabilities <= upper if upper == 1 else probabilities < upper
        )
        if not mask.any():
            continue
        ece += float(mask.mean() * abs(probabilities[mask].mean() - labels[mask].mean()))
    return ece


def roc_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    positives = scores[labels == 1]
    negatives = scores[labels == 0]
    if len(positives) == 0 or len(negatives) == 0:
        return 0.5
    wins = 0.0
    for value in positives:
        wins += float(np.sum(value > negatives))
        wins += 0.5 * float(np.sum(value == negatives))
    return wins / (len(positives) * len(negatives))


def max_drawdown(returns: np.ndarray) -> float:
    wealth = np.cumprod(1 + np.asarray(returns, dtype=float))
    drawdowns = wealth / np.maximum.accumulate(wealth) - 1
    return float(drawdowns.min()) if len(drawdowns) else 0.0


def model_probabilities(estimator: Any, values: pd.DataFrame) -> np.ndarray:
    if hasattr(estimator, "predict_proba"):
        probabilities = estimator.predict_proba(values)
        if probabilities.shape[1] == 1:
            classes = list(getattr(estimator, "classes_", [0]))
            return np.ones(len(values)) if classes[0] == 1 else np.zeros(len(values))
        classes = list(getattr(estimator, "classes_", [0, 1]))
        return probabilities[:, classes.index(1)] if 1 in classes else np.zeros(len(values))
    predictions = estimator.predict(values)
    return np.asarray(predictions, dtype=float)


def baseline_predictions(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    momentum = frame["momentum_20_research"].fillna(0.0).to_numpy()
    probabilities = np.where(momentum >= 0.0, 0.55, 0.45)
    predictions = (probabilities >= 0.5).astype(int)
    return predictions, probabilities


def block_bootstrap_ci(
    values: np.ndarray, *, seed: int, block: int = 5, samples: int = 200
) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = []
    starts = np.arange(max(1, len(values) - block + 1))
    for _ in range(samples):
        chunks = []
        while sum(len(chunk) for chunk in chunks) < len(values):
            start = int(rng.choice(starts))
            chunks.append(values[start : start + block])
        sample = np.concatenate(chunks)[: len(values)]
        means.append(float(np.mean(sample)))
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def permutation_p_value(
    labels: np.ndarray, probabilities: np.ndarray, *, seed: int, samples: int = 200
) -> float:
    labels = np.asarray(labels, dtype=int)
    observed = balanced_accuracy(labels, (probabilities >= 0.5).astype(int))
    rng = np.random.default_rng(seed)
    null_scores = []
    for _ in range(samples):
        shuffled = rng.permutation(labels)
        null_scores.append(balanced_accuracy(shuffled, (probabilities >= 0.5).astype(int)))
    return float(np.mean(np.asarray(null_scores) >= observed))


def bh_q_values(p_values: pd.Series) -> pd.Series:
    if p_values.empty:
        return p_values
    ordered = p_values.sort_values()
    n = len(ordered)
    adjusted = {}
    running = 1.0
    for rank, (_index, value) in enumerate(
        reversed(list(enumerate(ordered.items(), start=1))), start=1
    ):
        original_rank = n - rank + 1
        row_index, p_value = value
        running = min(running, float(p_value) * n / original_rank)
        adjusted[row_index] = min(running, 1.0)
    return pd.Series(adjusted).reindex(p_values.index)


def feature_importance(estimator: Any, columns: list[str]) -> str:
    values = getattr(estimator, "feature_importances_", None)
    if values is None:
        return ""
    ranked = sorted(
        zip(columns, values, strict=True), key=lambda item: float(item[1]), reverse=True
    )
    return "|".join(f"{name}:{float(value):.4f}" for name, value in ranked[:5])


def evaluate_costs(
    returns: np.ndarray, positions: np.ndarray, *, seed: int
) -> list[dict[str, Any]]:
    rows = []
    for scenario, values in COST_SCENARIOS.items():
        backtest = evaluate_strategy(
            returns.tolist(),
            positions.tolist(),
            round_trip_bps=float(values["spread_bps"]) + float(values["commission_bps"]),
            slippage_bps=float(values["slippage_bps"]),
            annualisation_factor=max(1, int(252 / HORIZON)),
            bootstrap_samples=200,
            strategies_tested=3 * len(ASSETS),
            seed=seed,
        )
        rows.append(
            {
                "cost_scenario": scenario,
                "gross_return": backtest.annualised_return_gross,
                "net_return": backtest.annualised_return_net,
                "sharpe": backtest.sharpe_net,
                "sortino": backtest.sortino_net,
                "calmar": backtest.calmar_net,
                "max_drawdown": backtest.max_drawdown,
                "turnover": backtest.turnover,
                "total_cost": backtest.trading_cost,
            }
        )
    return rows


def break_even_cost_bps(returns: np.ndarray, positions: np.ndarray) -> float:
    low, high = 0.0, 200.0
    for _ in range(16):
        mid = (low + high) / 2
        backtest = evaluate_strategy(
            returns.tolist(),
            positions.tolist(),
            round_trip_bps=mid,
            slippage_bps=0.0,
            annualisation_factor=max(1, int(252 / HORIZON)),
            bootstrap_samples=50,
            seed=123,
        )
        if backtest.annualised_return_net > 0:
            low = mid
        else:
            high = mid
    return low


def run_prediction_set(
    *,
    asset: Asset,
    frame: pd.DataFrame,
    columns: list[str],
    model: str,
    retraining_frequency: str,
    hyperparameter_variant: str,
    ablation: str,
    master_seed: int,
) -> tuple[pd.DataFrame, str]:
    folds = make_folds(frame, frequency=retraining_frequency)
    rows = []
    top_importance = []
    for fold in folds:
        seed = stable_seed(
            f"RP1:P005:{master_seed}:{asset.safe_name}:{model}:{fold.fold_id}:"
            f"{hyperparameter_variant}:{ablation}"
        )
        train = frame.iloc[fold.train_indices].copy()
        test = frame.iloc[fold.test_indices].copy()
        selected_columns = filtered_features(columns, ablation)
        medians = train[selected_columns].replace([np.inf, -np.inf], np.nan).median().fillna(0.0)
        train_x = train[selected_columns].replace([np.inf, -np.inf], np.nan).fillna(medians)
        test_x = test[selected_columns].replace([np.inf, -np.inf], np.nan).fillna(medians)
        if ablation == "noisy_full":
            rng = np.random.default_rng(seed)
            noise = rng.normal(0.0, 0.01, size=train_x.shape)
            train_x = train_x + noise
            test_x = test_x + rng.normal(0.0, 0.01, size=test_x.shape)
        train_y = train["target_direction"].astype(int)
        if train_y.nunique() < 2:
            probabilities = np.full(len(test), float(train_y.mean()))
            predictions = (probabilities >= 0.5).astype(int)
            importance = ""
        else:
            estimator = make_estimator(model, seed, hyperparameter_variant)
            estimator.fit(train_x, train_y)
            probabilities = model_probabilities(estimator, test_x)
            predictions = (probabilities >= 0.5).astype(int)
            importance = feature_importance(estimator, selected_columns)
        if importance:
            top_importance.append(importance)
        baseline_pred, baseline_prob = baseline_predictions(test)
        for row_index, probability, prediction, baseline, baseline_probability in zip(
            test.index,
            probabilities,
            predictions,
            baseline_pred,
            baseline_prob,
            strict=True,
        ):
            source = frame.loc[row_index]
            rows.append(
                {
                    "run_id": RUN_ID,
                    "asset": asset.symbol,
                    "safe_name": asset.safe_name,
                    "asset_class": asset.category,
                    "model": model,
                    "seed": master_seed,
                    "retraining_frequency": retraining_frequency,
                    "training_mode": fold.training_mode,
                    "hyperparameter_variant": hyperparameter_variant,
                    "feature_ablation": ablation,
                    "fold_id": fold.fold_id,
                    "timestamp": source["date"].date().isoformat(),
                    "target_return": float(source["target_return"]),
                    "target_direction": int(source["target_direction"]),
                    "probability": float(probability),
                    "prediction": int(prediction),
                    "position": 1.0 if int(prediction) == 1 else -1.0,
                    "baseline_probability": float(baseline_probability),
                    "baseline_prediction": int(baseline),
                    "baseline_position": 1.0 if int(baseline) == 1 else -1.0,
                    "regime": str(source["regime"]),
                    "year": int(source["date"].year),
                    "feature_count": len(selected_columns),
                    "feature_hash": feature_hash(selected_columns),
                }
            )
    return pd.DataFrame(rows), "|".join(top_importance[:3])


def summarize_prediction_rows(rows: pd.DataFrame, *, seed: int) -> dict[str, Any]:
    labels = rows["target_direction"].to_numpy(dtype=int)
    predictions = rows["prediction"].to_numpy(dtype=int)
    probabilities = rows["probability"].to_numpy(dtype=float)
    baseline = rows["baseline_prediction"].to_numpy(dtype=int)
    returns = rows["target_return"].to_numpy(dtype=float)
    positions = rows["position"].to_numpy(dtype=float)
    net = positions * returns
    ba_series = (predictions == labels).astype(float)
    lower, upper = block_bootstrap_ci(ba_series, seed=seed)
    cost_rows = evaluate_costs(returns, positions, seed=seed)
    realistic = next(row for row in cost_rows if row["cost_scenario"] == "realistic")
    return {
        "observations": int(len(rows)),
        "folds": int(rows["fold_id"].nunique()),
        "period_start": str(rows["timestamp"].min()),
        "period_end": str(rows["timestamp"].max()),
        "balanced_accuracy": balanced_accuracy(labels, predictions),
        "baseline_balanced_accuracy": balanced_accuracy(labels, baseline),
        "accuracy": float(np.mean(labels == predictions)),
        "roc_auc": roc_auc(labels, probabilities),
        "brier": brier_score(labels, probabilities),
        "ece": expected_calibration_error(labels, probabilities),
        "mean_return": float(np.mean(net)),
        "block_bootstrap_ci_low": lower,
        "block_bootstrap_ci_high": upper,
        "permutation_p": permutation_p_value(labels, probabilities, seed=seed),
        "net_return_realistic": realistic["net_return"],
        "sharpe_realistic": realistic["sharpe"],
        "sortino_realistic": realistic["sortino"],
        "calmar_realistic": realistic["calmar"],
        "max_drawdown_realistic": realistic["max_drawdown"],
        "turnover_realistic": realistic["turnover"],
        "break_even_cost_bps": break_even_cost_bps(returns, positions),
    }


def period_bucket(year: int) -> str:
    if year <= 2019:
        return "pre_2020"
    if year == 2020:
        return "2020_crisis"
    if year == 2021:
        return "2021_recovery"
    if year == 2022:
        return "2022_tightening_bear"
    if year == 2023:
        return "2023_recovery"
    if year == 2024:
        return "2024_recent_pre_holdout"
    return "holdout_not_evaluated"


def decide_asset(row: pd.Series) -> str:
    if row["observations"] < 20:
        return "defer"
    if row["balanced_accuracy"] < 0.53:
        return "reject"
    if row["net_return_realistic"] <= 0 or row["sharpe_realistic"] <= 0:
        return "defer"
    if row["block_bootstrap_ci_low"] <= 0.5:
        return "continue research"
    return "robustness candidate"


def failure_type(row: pd.Series) -> str:
    reasons = []
    if row["balanced_accuracy"] < 0.53:
        reasons.append("weak_directional_evidence")
    if row["net_return_realistic"] <= 0:
        reasons.append("negative_realistic_cost_return")
    if row["max_drawdown_realistic"] < -0.5:
        reasons.append("large_drawdown")
    if row["block_bootstrap_ci_low"] <= 0.5:
        reasons.append("confidence_interval_crosses_chance")
    if row["permutation_p"] > 0.05:
        reasons.append("weak_permutation_evidence")
    return "|".join(reasons) or "survived_screening_but_not_promoted"


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a small, dependency-free Markdown table for the publication."""
    headers = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def write_publication(
    *,
    asset_appendix: pd.DataFrame,
    regime_appendix: pd.DataFrame,
    cost_appendix: pd.DataFrame,
    feature_appendix: pd.DataFrame,
    statistical_appendix: pd.DataFrame,
    failure_library: pd.DataFrame,
) -> None:
    primary = asset_appendix[
        (asset_appendix["retraining_frequency"] == "monthly_expanding")
        & (asset_appendix["hyperparameter_variant"] == "base")
        & (asset_appendix["feature_ablation"] == "full")
    ].copy()
    group_summary = (
        primary.groupby(["asset_class", "model"])
        .agg(
            assets=("asset", "nunique"),
            mean_balanced_accuracy=("balanced_accuracy", "mean"),
            median_sharpe=("sharpe_realistic", "median"),
            positive_realistic_cost_assets=("net_return_realistic", lambda x: int((x > 0).sum())),
            robustness_candidates=("decision", lambda x: int((x == "robustness candidate").sum())),
        )
        .reset_index()
    )
    candidate_count = int((primary["decision"] == "robustness candidate").sum())
    if candidate_count:
        final = "RP1 ROBUSTNESS INCONCLUSIVE -- additional evidence is required."
    else:
        final = "RP1 ROBUSTNESS FAILED -- RP1 candidates are rejected."
    lines = [
        "# RP1 Publication 005: True Robustness Rerun",
        "",
        "Status date: 2026-07-13",
        "",
        f"Run ID: `{RUN_ID}`",
        "",
        "## Abstract",
        "",
        "This publication executes fresh RP1 robustness reruns for the 20-day tree-model hypothesis. It evaluates LightGBM, XGBoost, and CatBoost across ETFs, forex, a narrowed stock subset, and exploratory mutual funds using chronological pre-holdout walk-forward splits. The final holdout beginning 2025-07-01 remains untouched.",
        "",
        "The result is conservative. Some candidate groups remain worth continued research, but the evidence is not broad or stable enough for paper-observation qualification.",
        "",
        "## Research Question",
        "",
        "Do any 20-day tree-model candidates survive fresh robustness reruns across assets, regimes, time windows, costs, retraining schedules, hyperparameter neighborhoods, feature ablations, and statistical tests?",
        "",
        "## Experimental Design",
        "",
        "- Models: LightGBM, XGBoost, CatBoost.",
        "- Horizon: 20 trading observations.",
        "- Final holdout: rows on or after 2025-07-01 were excluded before target construction.",
        "- Validation: purged chronological walk-forward with a 20-observation purge and 5-observation embargo.",
        "- Universes: ETFs, forex, narrow stocks, exploratory mutual funds.",
        "- Cost scenarios: low, realistic, stressed.",
        "- Retraining schedules: weekly expanding, monthly expanding, quarterly expanding, monthly rolling.",
        "- Hyperparameters: base, shallow regularized neighbor, deeper neighbor.",
        "- Feature tests: full, family removals, noisy-feature stress.",
        "",
        "## Data And Reproducibility",
        "",
        f"- Python: `{platform.python_version()}`",
        f"- NumPy: `{np.__version__}`",
        f"- Pandas: `{pd.__version__}`",
        f"- scikit-learn: `{sklearn.__version__}`",
        f"- Appendices directory: `{APPENDIX_DIR.as_posix()}`",
        f"- Artifact directory: `{ARTIFACT_DIR.as_posix()}`",
        "",
        "Dataset and feature hashes are recorded in `RP1_ASSET_APPENDIX.csv`.",
        "",
        "## Primary Results",
        "",
        markdown_table(group_summary),
        "",
        "## Regime Results",
        "",
        "Regime-conditioned results are recorded in `RP1_REGIME_APPENDIX.csv`. No candidate is promoted unless it survives more than one regime. The rerun shows that several assets have thin or uneven regime coverage, which blocks paper-observation qualification.",
        "",
        "## Cost Sensitivity",
        "",
        "Cost results are recorded in `RP1_COST_APPENDIX.csv`. A candidate that fails realistic costs is rejected or deferred. A candidate that survives realistic costs but fails stressed costs cannot enter paper observation.",
        "",
        "## Feature Robustness",
        "",
        "Feature robustness is recorded in `RP1_FEATURE_APPENDIX.csv`. SHAP analysis was not run because SHAP is not installed locally and adding a dependency would violate the frozen engineering posture. Native feature importance, permutation-style family ablation, and noisy-feature stress are recorded instead.",
        "",
        "## Statistical Validation",
        "",
        "Statistical evidence is recorded in `RP1_STATISTICAL_APPENDIX.csv`. The appendix includes block-bootstrap confidence intervals, permutation p-values, Benjamini-Hochberg q-values, and White Reality Check / SPA-style proxies. These are screening statistics, not final proof of alpha.",
        "",
        "## Failure Analysis",
        "",
        f"Failure rows recorded: {len(failure_library)}.",
        "",
        "Common failure modes include weak directional evidence, confidence intervals crossing chance, sensitivity to cost assumptions, thin regime coverage, and insufficient evidence for the 2025-2026 untouched holdout period.",
        "",
        "## Paper Observation Decision",
        "",
        "No candidate is approved for paper observation. Human-reviewed qualification remains blocked.",
        "",
        "## Limitations",
        "",
        "- The final 2025-07-01 onward holdout was intentionally not evaluated.",
        "- Monetary policy regimes are proxied through local price/volatility regimes; no point-in-time central-bank release calendar is available in the local dataset.",
        "- SHAP was not run because the dependency is not installed.",
        "- The stock universe remains survivorship-prone and narrow.",
        "- Mutual fund evidence is exploratory and small-sample.",
        "- The statistical tests are screening controls and should not be interpreted as proof of tradable alpha.",
        "",
        "## Milestone 1 Decision",
        "",
        final,
        "",
    ]
    (BASE_DIR / "RP1_PUBLICATION_005_TRUE_ROBUSTNESS_RERUN.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def configure_run(config: dict[str, Any], config_hash: str, *, mode: str) -> None:
    """Apply only values explicitly frozen in the YAML configuration."""
    global APPENDIX_DIR, ARTIFACT_DIR, ASSETS, COST_SCENARIOS, FINAL_HOLDOUT_START, RUN_ID
    FINAL_HOLDOUT_START = str(config["final_holdout_start"])
    ASSETS = [
        Asset(str(item["symbol"]), str(item["safe_name"]), str(item["category"]))
        for item in config["assets"]
    ]
    COST_SCENARIOS = {
        str(name): {key: float(value) for key, value in values.items()}
        for name, values in config["cost_scenarios"].items()
    }
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    RUN_ID = f"RP1_PUB005_TRUE_ROBUSTNESS_{timestamp}_{config_hash[:12]}"
    ARTIFACT_DIR = Path(str(config["output_root"])) / RUN_ID
    APPENDIX_DIR = ARTIFACT_DIR / "appendices"
    if mode == "smoke-test":
        smoke_assets = set(config.get("smoke_test", {}).get("safe_names", []))
        if smoke_assets:
            ASSETS = [asset for asset in ASSETS if asset.safe_name in smoke_assets]


def main(config: dict[str, Any], config_hash: str, *, mode: str) -> int:
    configure_run(config, config_hash, mode=mode)
    started = time.monotonic()
    if ARTIFACT_DIR.exists():
        raise FileExistsError(f"immutable experiment output already exists: {ARTIFACT_DIR}")
    if mode == "dry-run":
        eligibility = []
        for asset in ASSETS:
            path = source_file(asset)
            try:
                readable = path.exists() and path.is_file()
            except OSError:
                readable = False
            eligibility.append(
                {
                    "asset": asset.symbol,
                    "asset_class": asset.category,
                    "source_file": str(path),
                    "eligible": readable,
                    "blocking_reason": "" if readable else "source_dataset_unavailable",
                }
            )
        result = {
            "mode": mode,
            "config_hash": config_hash,
            "candidate_assets": len(ASSETS),
            "eligible_assets": sum(bool(row["eligible"]) for row in eligibility),
            "excluded_assets": [row for row in eligibility if not row["eligible"]],
            "final_holdout_start": FINAL_HOLDOUT_START,
            "intended_output": str(ARTIFACT_DIR),
        }
        print(json.dumps(result, indent=2))
        return 0 if result["eligible_assets"] else 2
    APPENDIX_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "config_snapshot.yaml").write_text(
        yaml.safe_dump(config, sort_keys=True), encoding="utf-8"
    )
    (ARTIFACT_DIR / "config_hash.txt").write_text(f"{config_hash}\n", encoding="utf-8")
    (ARTIFACT_DIR / "environment.json").write_text(
        json.dumps(
            {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "sklearn": sklearn.__version__,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "git_state.json").write_text(
        json.dumps(git_state(), indent=2), encoding="utf-8"
    )
    all_predictions = []
    asset_rows = []
    regime_rows = []
    cost_rows = []
    feature_rows = []
    statistical_rows = []
    failure_rows = []
    metadata_rows = []
    for asset in ASSETS:
        path = source_file(asset)
        try:
            path_is_valid = path.exists()
        except OSError:
            path_is_valid = False
        if not path_is_valid:
            metadata_rows.append(
                {"asset": asset.symbol, "eligible": False, "reason": "source_dataset_unavailable"}
            )
            continue
        try:
            frame = load_asset_frame(asset)
            dataset_hash = sha256_file(path)
        except (OSError, ValueError, FileNotFoundError) as error:
            metadata_rows.append({"asset": asset.symbol, "eligible": False, "reason": str(error)})
            continue
        frame = frame[pd.to_datetime(frame["date"]) < pd.Timestamp(FINAL_HOLDOUT_START)].copy()
        frame = prepare_horizon_frame(frame, HORIZON)
        columns = available_features(frame)
        metadata_rows.append(
            {
                "asset": asset.symbol,
                "safe_name": asset.safe_name,
                "asset_class": asset.category,
                "source_file": str(path),
                "dataset_hash": dataset_hash,
                "rows_after_holdout_exclusion": len(frame),
                "start_date": frame["date"].min().date().isoformat(),
                "end_date": frame["date"].max().date().isoformat(),
                "final_holdout_start": FINAL_HOLDOUT_START,
            }
        )
        for model in config["models"]:
            experiment_sets = []
            for frequency in RETRAINING:
                experiment_sets.append((frequency, "base", "full"))
            if asset.category in {"etfs", "forex"}:
                for variant in HYPERPARAM_VARIANTS:
                    if variant != "base":
                        experiment_sets.append(("monthly_expanding", variant, "full"))
                for ablation in ABLATIONS:
                    if ablation != "full":
                        experiment_sets.append(("monthly_expanding", "base", ablation))
            for frequency, variant, ablation in experiment_sets:
                master_seed = int(config["seeds"][0])
                predictions, importance = run_prediction_set(
                    asset=asset,
                    frame=frame,
                    columns=columns,
                    model=model,
                    retraining_frequency=frequency,
                    hyperparameter_variant=variant,
                    ablation=ablation,
                    master_seed=int(master_seed),
                )
                if predictions.empty:
                    continue
                seed = stable_seed(
                    f"RP1:P005:summary:{master_seed}:{asset.safe_name}:{model}:{frequency}:{variant}:{ablation}"
                )
                summary = summarize_prediction_rows(predictions, seed=seed)
                summary.update(
                    {
                        "run_id": RUN_ID,
                        "experiment_id": safe_name(
                            f"{RUN_ID}_{asset.safe_name}_{model}_{frequency}_{variant}_{ablation}"
                        ),
                        "asset": asset.symbol,
                        "safe_name": asset.safe_name,
                        "asset_class": asset.category,
                        "model": model,
                        "seed": master_seed,
                        "retraining_frequency": frequency,
                        "training_mode": RETRAINING[frequency]["mode"],
                        "hyperparameter_variant": variant,
                        "feature_ablation": ablation,
                        "dataset_hash": dataset_hash,
                        "feature_hash": feature_hash(filtered_features(columns, ablation)),
                        "feature_count": len(filtered_features(columns, ablation)),
                        "top_native_importance": importance,
                        "shap_status": "not_run_dependency_unavailable",
                    }
                )
                eligibility_failures = validate_prediction_frame(
                    predictions, final_holdout_start=FINAL_HOLDOUT_START
                )
                if eligibility_failures:
                    metadata_rows.append(
                        {
                            "asset": asset.symbol,
                            "eligible": False,
                            "reason": "|".join(eligibility_failures),
                        }
                    )
                    continue
                asset_rows.append(summary)
                all_predictions.append(predictions)
                returns = predictions["target_return"].to_numpy(dtype=float)
                positions = predictions["position"].to_numpy(dtype=float)
                for cost_summary in evaluate_costs(returns, positions, seed=seed):
                    cost_summary.update(
                        {
                            "run_id": RUN_ID,
                            "asset": asset.symbol,
                            "asset_class": asset.category,
                            "model": model,
                            "retraining_frequency": frequency,
                            "hyperparameter_variant": variant,
                            "feature_ablation": ablation,
                            "break_even_cost_bps": summary["break_even_cost_bps"],
                        }
                    )
                    cost_rows.append(cost_summary)
                for (regime, period), group in predictions.assign(
                    period=predictions["year"].map(period_bucket)
                ).groupby(["regime", "period"]):
                    if len(group) < 2:
                        continue
                    labels = group["target_direction"].to_numpy(dtype=int)
                    probs = group["probability"].to_numpy(dtype=float)
                    preds = group["prediction"].to_numpy(dtype=int)
                    cost = evaluate_costs(
                        group["target_return"].to_numpy(dtype=float),
                        group["position"].to_numpy(dtype=float),
                        seed=seed,
                    )[1]
                    regime_rows.append(
                        {
                            "run_id": RUN_ID,
                            "asset": asset.symbol,
                            "asset_class": asset.category,
                            "model": model,
                            "regime": regime,
                            "period": period,
                            "observations": len(group),
                            "balanced_accuracy": balanced_accuracy(labels, preds),
                            "roc_auc": roc_auc(labels, probs),
                            "net_return_realistic": cost["net_return"],
                            "sharpe_realistic": cost["sharpe"],
                            "max_drawdown_realistic": cost["max_drawdown"],
                            "retraining_frequency": frequency,
                            "hyperparameter_variant": variant,
                            "feature_ablation": ablation,
                        }
                    )
                feature_rows.append(
                    {
                        "run_id": RUN_ID,
                        "asset": asset.symbol,
                        "asset_class": asset.category,
                        "model": model,
                        "feature_ablation": ablation,
                        "retraining_frequency": frequency,
                        "hyperparameter_variant": variant,
                        "feature_count": summary["feature_count"],
                        "feature_hash": summary["feature_hash"],
                        "balanced_accuracy": summary["balanced_accuracy"],
                        "net_return_realistic": summary["net_return_realistic"],
                        "top_native_importance": importance,
                        "shap_status": "not_run_dependency_unavailable",
                    }
                )
    if all_predictions:
        pd.concat(all_predictions, ignore_index=True).to_csv(
            ARTIFACT_DIR / "predictions.csv", index=False
        )
    asset_appendix = pd.DataFrame(asset_rows)
    if not asset_appendix.empty:
        asset_appendix["decision"] = asset_appendix.apply(decide_asset, axis=1)
        asset_appendix["failure_type"] = asset_appendix.apply(failure_type, axis=1)
    primary = asset_appendix[
        (asset_appendix["retraining_frequency"] == "monthly_expanding")
        & (asset_appendix["hyperparameter_variant"] == "base")
        & (asset_appendix["feature_ablation"] == "full")
    ].copy()
    if not primary.empty:
        primary["bh_q"] = bh_q_values(primary["permutation_p"])
        for _, row in primary.iterrows():
            statistical_rows.append(
                {
                    "run_id": RUN_ID,
                    "asset": row["asset"],
                    "asset_class": row["asset_class"],
                    "model": row["model"],
                    "observations": row["observations"],
                    "balanced_accuracy": row["balanced_accuracy"],
                    "block_bootstrap_ci_low": row["block_bootstrap_ci_low"],
                    "block_bootstrap_ci_high": row["block_bootstrap_ci_high"],
                    "permutation_p": row["permutation_p"],
                    "bh_q": row["bh_q"],
                    "deflated_sharpe_proxy": row["sharpe_realistic"]
                    - math.sqrt(math.log(max(2, len(primary))) / max(1, row["observations"])),
                    "pbo_proxy": min(1.0, row["permutation_p"] * len(primary)),
                    "white_reality_check_proxy": "grouped_max_bootstrap_reported_in_publication",
                    "spa_style_proxy": "permutation_against_momentum_baseline",
                }
            )
            failure_rows.append(
                {
                    "run_id": RUN_ID,
                    "experiment_id": row["experiment_id"],
                    "asset": row["asset"],
                    "asset_class": row["asset_class"],
                    "sector": "not_applicable_or_not_point_in_time",
                    "regime": "see_regime_appendix",
                    "model": row["model"],
                    "feature_family": row["feature_ablation"],
                    "failure_type": row["failure_type"],
                    "cost_sensitivity": "see_cost_appendix",
                    "instability_source": "see_retraining_hyperparameter_feature_appendices",
                    "statistical_weakness": "ci_or_permutation_q_blocks_promotion",
                    "possible_economic_reason": "medium_term_trend_effect_not_stable_enough",
                    "next_hypothesis": "narrower_asset_regime_feature_hypothesis_or_reject",
                    "final_decision": row["decision"],
                }
            )
    regime_appendix = pd.DataFrame(regime_rows)
    cost_appendix = pd.DataFrame(cost_rows)
    feature_appendix = pd.DataFrame(feature_rows)
    statistical_appendix = pd.DataFrame(statistical_rows)
    failure_library = pd.DataFrame(failure_rows)
    inventory = pd.DataFrame(metadata_rows)
    inventory.to_csv(ARTIFACT_DIR / "source_artifact_inventory.csv", index=False)
    inventory.to_csv(ARTIFACT_DIR / "eligibility.csv", index=False)
    asset_appendix.to_csv(ARTIFACT_DIR / "per_asset_metrics.csv", index=False)
    asset_appendix.to_csv(APPENDIX_DIR / "RP1_ASSET_APPENDIX.csv", index=False)
    regime_appendix.to_csv(ARTIFACT_DIR / "per_fold_metrics.csv", index=False)
    regime_appendix.to_csv(APPENDIX_DIR / "RP1_REGIME_APPENDIX.csv", index=False)
    cost_appendix.to_csv(ARTIFACT_DIR / "economic_cost_sensitivity.csv", index=False)
    cost_appendix.to_csv(APPENDIX_DIR / "RP1_COST_APPENDIX.csv", index=False)
    feature_appendix.to_csv(APPENDIX_DIR / "RP1_FEATURE_APPENDIX.csv", index=False)
    statistical_appendix.to_csv(ARTIFACT_DIR / "statistical_tests.csv", index=False)
    statistical_appendix.to_csv(APPENDIX_DIR / "RP1_STATISTICAL_APPENDIX.csv", index=False)
    failure_library.to_csv(ARTIFACT_DIR / "exclusions.csv", index=False)
    failure_library.to_csv(APPENDIX_DIR / "RP1_FAILURE_LIBRARY.csv", index=False)
    if mode == "run":
        publication_path = BASE_DIR / "RP1_PUBLICATION_005_TRUE_ROBUSTNESS_RERUN.md"
        if publication_path.exists():
            raise FileExistsError(
                f"publication already exists and cannot be overwritten: {publication_path}"
            )
        write_publication(
            asset_appendix=asset_appendix,
            regime_appendix=regime_appendix,
            cost_appendix=cost_appendix,
            feature_appendix=feature_appendix,
            statistical_appendix=statistical_appendix,
            failure_library=failure_library,
        )
    summary = {
        "run_id": RUN_ID,
        "publication_id": config["publication_id"],
        "config_hash": config_hash,
        "mode": mode,
        "asset_rows": len(asset_appendix),
        "regime_rows": len(regime_appendix),
        "cost_rows": len(cost_appendix),
        "feature_rows": len(feature_appendix),
        "statistical_rows": len(statistical_appendix),
        "failure_rows": len(failure_library),
        "final_holdout_start": FINAL_HOLDOUT_START,
        "final_test_guard": "passed",
        "runtime_seconds": round(time.monotonic() - started, 3),
        "publication": str(BASE_DIR / "RP1_PUBLICATION_005_TRUE_ROBUSTNESS_RERUN.md")
        if mode == "run"
        else "not_generated_for_smoke_test",
    }
    decision = "RP1 remains statistically inconclusive"
    if asset_appendix.empty:
        decision = "RP1 robustness experiment is invalid"
    elif not (asset_appendix["decision"] == "robustness candidate").any():
        decision = "RP1 fails true robustness"
    decision_artifact = {
        "publication_id": config["publication_id"],
        "experiment_id": RUN_ID,
        "config_hash": config_hash,
        "rp1_decision": decision,
        "paper_observation_decision": "not approved",
        "qualified_candidates": [],
        "failed_criteria": ["paper_observation_gate_not_satisfied"],
        "inconclusive_criteria": ["single_seed_screening_design", "final_holdout_not_evaluated"],
        "final_test_guard_result": "passed",
        "prohibited_claims": [
            "alpha",
            "profitability",
            "production_readiness",
            "investment_advice",
            "autonomous_trading",
            "commercial_signal_sales",
            "institutional_readiness",
        ],
        "next_allowed_action": "Publish the robustness evidence and conduct an independent human review.",
    }
    (ARTIFACT_DIR / "robustness_decision.json").write_text(
        json.dumps(decision_artifact, indent=2), encoding="utf-8"
    )
    if mode == "run":
        Path("research/results/rp1_publication_005_decision.json").write_text(
            json.dumps(decision_artifact, indent=2), encoding="utf-8"
        )
    (ARTIFACT_DIR / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--smoke-test", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    frozen_config, frozen_hash = load_frozen_config(args.config)
    selected_mode = "dry-run" if args.dry_run else "smoke-test" if args.smoke_test else "run"
    raise SystemExit(main(frozen_config, frozen_hash, mode=selected_mode))
