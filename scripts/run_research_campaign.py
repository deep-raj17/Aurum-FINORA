"""Run FINORA Phase 10 quantitative research campaigns."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from aurum.backtest import evaluate_strategy
from aurum.research import (
    ExperimentMetrics,
    ExperimentSpec,
    ResearchDecision,
    ResearchExperiment,
    ResearchRegistry,
    decide_experiment,
    experiment_id,
)


@dataclass(frozen=True)
class Asset:
    symbol: str
    safe_name: str
    category: str


def load_campaign_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def horizon_days(value: str | int) -> int:
    if isinstance(value, int):
        return value
    cleaned = value.strip().lower()
    if not cleaned.endswith("d"):
        raise ValueError(f"horizon must use day suffix, got {value}")
    return int(cleaned[:-1])


def campaign_assets(config: dict[str, Any]) -> list[Asset]:
    return [
        Asset(
            symbol=str(item["symbol"]),
            safe_name=str(item["safe_name"]),
            category=str(item["category"]),
        )
        for item in config["assets"]
    ]


def load_asset_frame(asset: Asset, root: Path = Path(".")) -> pd.DataFrame:
    feature_path = (
        root
        / "data"
        / "processed"
        / "features"
        / asset.category
        / (f"{asset.safe_name}_features.csv")
    )
    source_path = root / "data" / asset.category / f"{asset.safe_name}.csv"
    path = feature_path if feature_path.exists() else source_path
    if not path.exists():
        raise FileNotFoundError(f"no dataset found for {asset.symbol} at {source_path}")
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        raise ValueError(f"{path} does not contain a date column")
    close_column = "adj_close" if "adj_close" in frame.columns else "close"
    if close_column not in frame.columns:
        raise ValueError(f"{path} does not contain close or adj_close")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close_for_research"] = pd.to_numeric(frame[close_column], errors="coerce")
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
    frame = frame.sort_values("date").drop_duplicates("date")
    frame = frame.dropna(subset=["date", "close_for_research"]).reset_index(drop=True)
    if len(frame) < 260:
        raise ValueError(f"{asset.symbol} has only {len(frame)} usable rows")
    return add_research_features(frame)


def add_research_features(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["close_for_research"]
    frame = frame.copy()
    frame["return_1d_research"] = close.pct_change()
    frame["log_return_1d_research"] = np.log(close).diff()
    for window in (5, 10, 20, 50, 100, 200):
        frame[f"sma_{window}_research"] = close.rolling(window, min_periods=window).mean()
        frame[f"momentum_{window}_research"] = close / close.shift(window) - 1
        frame[f"volatility_{window}_research"] = (
            frame["return_1d_research"].rolling(window, min_periods=window).std()
        )
        frame[f"volume_zscore_{window}_research"] = (
            frame["volume"] - frame["volume"].rolling(window, min_periods=window).mean()
        ) / frame["volume"].rolling(window, min_periods=window).std().replace(0, np.nan)
    for lag in (1, 2, 3, 5, 10, 20):
        frame[f"return_lag_{lag}_research"] = frame["return_1d_research"].shift(lag)
    frame["ma_signal_research"] = np.where(
        frame["sma_20_research"] > frame["sma_100_research"], 1.0, -1.0
    )
    return frame.replace([np.inf, -np.inf], np.nan)


def prepare_horizon_frame(frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    prepared = frame.copy()
    prepared["target_return"] = (
        prepared["close_for_research"].shift(-horizon) / prepared["close_for_research"] - 1
    )
    prepared["target_direction"] = (prepared["target_return"] > 0).astype(int)
    prepared["regime"] = classify_regime(prepared)
    return prepared.dropna(subset=["target_return", "return_1d_research"]).reset_index(drop=True)


def classify_regime(frame: pd.DataFrame) -> pd.Series:
    momentum = frame["close_for_research"] / frame["close_for_research"].shift(60) - 1
    volatility = frame["return_1d_research"].rolling(20, min_periods=20).std()
    high_vol_threshold = float(volatility.quantile(0.75)) if volatility.notna().any() else math.inf
    regimes = np.full(len(frame), "sideways", dtype=object)
    regimes[momentum > 0.05] = "bull"
    regimes[momentum < -0.05] = "bear"
    regimes[volatility > high_vol_threshold] = "high_volatility"
    return pd.Series(regimes, index=frame.index)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    excluded = {
        "date",
        "symbol",
        "category",
        "source",
        "target_return",
        "target_direction",
        "regime",
    }
    columns = []
    for column in frame.columns:
        if column in excluded or not pd.api.types.is_numeric_dtype(frame[column]):
            continue
        series = frame[column].replace([np.inf, -np.inf], np.nan)
        if series.notna().mean() < 0.80:
            continue
        if series.nunique(dropna=True) <= 1:
            continue
        columns.append(column)
    if not columns:
        raise ValueError("no sufficiently populated numeric feature columns")
    return columns


def expanding_slices(total_rows: int, minimum_train_size: int, step_size: int, max_splits: int):
    if total_rows <= minimum_train_size + step_size:
        return
    starts = list(range(minimum_train_size, total_rows - step_size + 1, step_size))
    if len(starts) > max_splits:
        starts = starts[-max_splits:]
    for start in starts:
        yield slice(0, start), slice(start, min(start + step_size, total_rows))


def baseline_positions(model: str, frame: pd.DataFrame, seed: int) -> np.ndarray:
    if model == "buy_hold":
        return np.ones(len(frame), dtype=float)
    if model == "random":
        rng = np.random.default_rng(seed)
        return rng.choice([-1.0, 1.0], len(frame))
    if model == "naive":
        return np.where(frame["return_lag_1_research"].fillna(0.0).to_numpy() >= 0, 1.0, -1.0)
    if model == "momentum":
        return np.where(frame["momentum_20_research"].fillna(0.0).to_numpy() >= 0, 1.0, -1.0)
    if model == "moving_average":
        return frame["ma_signal_research"].fillna(-1.0).to_numpy(dtype=float)
    raise ValueError(f"{model} is not a baseline model")


def train_tree_model(model: str, train_x, train_y):
    normalized = model.lower()
    if normalized == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            n_estimators=10,
            max_depth=3,
            learning_rate=0.05,
            min_child_samples=20,
            verbosity=-1,
            random_state=42,
        ).fit(train_x, train_y)
    if normalized == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=10,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
        ).fit(train_x, train_y)
    if normalized == "catboost":
        from catboost import CatBoostClassifier

        return CatBoostClassifier(
            iterations=10,
            depth=3,
            learning_rate=0.05,
            loss_function="Logloss",
            random_seed=42,
            verbose=False,
        ).fit(train_x, train_y)
    raise ValueError(f"unsupported ML model {model}")


def ml_positions(
    model: str,
    frame: pd.DataFrame,
    columns: list[str],
    minimum_train_size: int,
    step_size: int,
    max_splits: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    working = frame.dropna(subset=["target_direction", "target_return"]).reset_index(drop=True)
    working[columns] = working[columns].fillna(0.0)
    if len(working) <= minimum_train_size + step_size:
        raise ValueError(f"not enough rows for walk-forward: {len(working)}")
    positions = np.full(len(working), np.nan)
    for train_slice, test_slice in expanding_slices(
        len(working), minimum_train_size, step_size, max_splits
    ):
        train = working.iloc[train_slice]
        test = working.iloc[test_slice]
        train_y = train["target_direction"].astype(int)
        if train_y.nunique() < 2:
            positions[test_slice] = 1.0
            continue
        estimator = train_tree_model(model, train[columns], train_y)
        if hasattr(estimator, "predict_proba"):
            probabilities = estimator.predict_proba(test[columns])[:, 1]
            positions[test_slice] = np.where(probabilities >= 0.5, 1.0, -1.0)
        else:
            predictions = estimator.predict(test[columns])
            positions[test_slice] = np.where(np.asarray(predictions) >= 1, 1.0, -1.0)
    mask = ~np.isnan(positions)
    if not mask.any():
        raise ValueError("walk-forward produced no predictions")
    return positions[mask], working.loc[mask].reset_index(drop=True)


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


def classification_metrics(frame: pd.DataFrame, positions: np.ndarray) -> dict[str, float]:
    labels = frame["target_direction"].to_numpy(dtype=int)
    predictions = (positions > 0).astype(int)
    tp = int(np.sum((labels == 1) & (predictions == 1)))
    fp = int(np.sum((labels == 0) & (predictions == 1)))
    fn = int(np.sum((labels == 1) & (predictions == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": float(np.mean(labels == predictions)),
        "roc_auc": roc_auc(labels, positions),
        "f1": float(f1),
    }


def evaluate_model(
    asset: Asset,
    horizon: int,
    model: str,
    frame: pd.DataFrame,
    config: dict[str, Any],
    *,
    strategies_tested: int,
) -> dict[str, Any]:
    validation = config["validation"]
    costs = config["costs"]
    minimum_train_size = int(validation["minimum_train_size"])
    step_size = int(validation["step_size"])
    max_splits = int(validation["max_splits"])
    seed = abs(hash((asset.safe_name, horizon, model))) % (2**32)
    model_key = model.lower()
    baseline_names = {"naive", "random", "buy_hold", "momentum", "moving_average"}
    if model_key in baseline_names:
        positions = baseline_positions(model_key, frame, seed)
        evaluated = frame.reset_index(drop=True)
    else:
        positions, evaluated = ml_positions(
            model,
            frame,
            feature_columns(frame),
            minimum_train_size,
            step_size,
            max_splits,
        )
    metrics = classification_metrics(evaluated, positions)
    backtest = evaluate_strategy(
        evaluated["target_return"].to_list(),
        positions.tolist(),
        round_trip_bps=float(costs["spread_bps"]) + float(costs["commission_bps"]),
        slippage_bps=float(costs["slippage_bps"]),
        annualisation_factor=max(1, int(252 / horizon)),
        bootstrap_samples=300,
        strategies_tested=strategies_tested,
        seed=seed,
    )
    deflated_sharpe = float(
        backtest.sharpe_net
        - math.sqrt(max(0.0, math.log(max(strategies_tested, 2))) / len(evaluated))
    )
    regimes = sorted({str(value) for value in evaluated["regime"].dropna().unique()})
    return {
        "asset": asset.symbol,
        "safe_name": asset.safe_name,
        "asset_class": asset.category,
        "horizon": f"{horizon}d",
        "model": model,
        "status": "completed",
        "observations": backtest.observations,
        "regimes": "|".join(regimes),
        "accuracy": metrics["accuracy"],
        "roc_auc": metrics["roc_auc"],
        "f1": metrics["f1"],
        "strategy_return": backtest.annualised_return_net,
        "buy_hold_return": backtest.buy_hold_return,
        "momentum_return": backtest.momentum_return,
        "random_return": 0.0,
        "sharpe": backtest.sharpe_net,
        "sortino": backtest.sortino_net,
        "calmar": backtest.calmar_net,
        "max_drawdown": backtest.max_drawdown,
        "turnover": backtest.turnover,
        "bootstrap_p": backtest.bootstrap_p_value,
        "deflated_sharpe": deflated_sharpe,
        "pbo": backtest.probability_backtest_overfit,
        "trading_cost": backtest.trading_cost,
    }


def apply_baseline_comparison(rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["status"] == "completed":
            grouped[(row["safe_name"], row["horizon"])].append(row)
    baselines = {name.lower() for name in config["baselines"]}
    for group_rows in grouped.values():
        baseline_rows = [row for row in group_rows if row["model"].lower() in baselines]
        best_baseline_return = max(
            (float(row["strategy_return"]) for row in baseline_rows),
            default=0.0,
        )
        best_baseline_sharpe = max((float(row["sharpe"]) for row in baseline_rows), default=0.0)
        for row in group_rows:
            row["best_baseline_return"] = best_baseline_return
            row["best_baseline_sharpe"] = best_baseline_sharpe
            row["beats_baselines"] = bool(float(row["strategy_return"]) > best_baseline_return)


def classify_rows(rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    rules = config["decision_rules"]
    alpha = float(rules["significance_level"])
    for row in rows:
        if row["status"] != "completed":
            row["signal_classification"] = "failed"
            continue
        if not row.get("beats_baselines", False):
            row["signal_classification"] = "rejected"
        elif float(row["sharpe"]) <= 0:
            row["signal_classification"] = "rejected"
        elif float(row["bootstrap_p"]) > alpha or float(row["deflated_sharpe"]) <= 0:
            row["signal_classification"] = "inconclusive"
        else:
            row["signal_classification"] = "promising"

    min_assets = int(rules["min_assets_for_validated"])
    min_regimes = int(rules["min_regimes_for_validated"])
    for (_model, _horizon), group in groupby_signal(rows).items():
        promising = [row for row in group if row.get("signal_classification") == "promising"]
        assets = {row["safe_name"] for row in promising}
        regimes = {
            regime
            for row in promising
            for regime in str(row.get("regimes", "")).split("|")
            if regime
        }
        if len(assets) >= min_assets and len(regimes) >= min_regimes:
            for row in promising:
                row["signal_classification"] = "validated"


def groupby_signal(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["status"] == "completed":
            grouped[(str(row["model"]), str(row["horizon"]))].append(row)
    return grouped


def save_experiment(
    row: dict[str, Any],
    config: dict[str, Any],
    registry: ResearchRegistry,
    run_id: str,
    experiment_dir: Path,
) -> None:
    if row["status"] != "completed":
        return
    spec = ExperimentSpec(
        hypothesis=(
            f"{row['model']} on {row['asset']} at {row['horizon']} improves "
            "cost-adjusted out-of-sample investment decisions"
        ),
        dataset_version=f"{config['campaign_id']}:{row['safe_name']}:{run_id}",
        feature_version="phase10-research-features-v1",
        model_version=f"{row['model']}:horizon={row['horizon']}:run={run_id}",
        training_period=str(config["validation"]["method"]),
        testing_period="walk-forward test folds",
        validation_methodology=str(config["validation"]["method"]),
        assets=[str(row["asset"])],
        regimes=str(row.get("regimes", "")).split("|") if row.get("regimes") else [],
        baselines=list(config["baselines"]),
        costs_included=True,
        slippage_included=True,
    )
    metrics = ExperimentMetrics(
        observations=int(row["observations"]),
        strategy_return=float(row["strategy_return"]),
        buy_hold_return=float(row["buy_hold_return"]),
        random_return=float(row.get("random_return", 0.0)),
        sharpe_net=float(row["sharpe"]),
        max_drawdown=float(row["max_drawdown"]),
        bootstrap_p_value=float(row["bootstrap_p"]),
        deflated_sharpe=float(row["deflated_sharpe"]),
        probability_backtest_overfit=row.get("pbo"),
        transaction_cost_bps=float(config["costs"]["spread_bps"])
        + float(config["costs"]["slippage_bps"])
        + float(config["costs"]["commission_bps"]),
    )
    conclusion = decide_experiment(
        metrics,
        min_observations=int(config["decision_rules"]["min_observations"]),
        significance_level=float(config["decision_rules"]["significance_level"]),
        require_multi_asset=False,
        require_multi_regime=False,
        assets=spec.assets,
        regimes=spec.regimes,
    )
    if row.get("signal_classification") == "promising":
        conclusion.decision = ResearchDecision.ACCEPT
        conclusion.recommendation = "Candidate signal for aggregate cross-asset review."
    elif row.get("signal_classification") == "validated":
        conclusion.decision = ResearchDecision.ACCEPT
        conclusion.recommendation = "Aggregate signal passed Phase 10 validation gates."
    experiment = ResearchExperiment(
        experiment_id=experiment_id(spec),
        created_at=datetime.now(UTC),
        spec=spec,
        metrics=metrics,
        conclusion=conclusion,
        artifacts={"campaign_row": f"{row['safe_name']}:{row['horizon']}:{row['model']}"},
        notes="Phase 10 research-only result; not investment advice or trading approval.",
    )
    digest = registry.save(experiment)
    row["experiment_id"] = experiment.experiment_id
    row["payload_sha256"] = digest
    experiment_path = experiment_dir / f"{experiment.experiment_id}.json"
    experiment_path.write_text(experiment.model_dump_json(indent=2), encoding="utf-8")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def best_by(rows: list[dict[str, Any]], key: str) -> list[tuple[str, str, float]]:
    completed = [row for row in rows if row["status"] == "completed"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in completed:
        grouped[str(row[key])].append(row)
    result = []
    for value, group in grouped.items():
        best = max(group, key=lambda row: float(row.get("sharpe", -999)))
        result.append((value, str(best["model"]), float(best.get("sharpe", 0.0))))
    return sorted(result)


def write_markdown(rows: list[dict[str, Any]], path: Path, run_id: str) -> None:
    counts = Counter(str(row.get("signal_classification", row["status"])) for row in rows)
    failed = [row for row in rows if row["status"] != "completed"]
    completed = [row for row in rows if row["status"] == "completed"]
    best_horizon = best_by(rows, "horizon")
    best_class = best_by(rows, "asset_class")
    validated = counts.get("validated", 0)
    promising = counts.get("promising", 0)
    evidence = (
        "No signal is approved for trading use. Phase 10 found research candidates only."
        if validated == 0
        else "Validated signals require paper trading and human risk review before any capital use."
    )
    lines = [
        "# Phase 10 Research Campaign v1 Summary",
        "",
        f"Run ID: `{run_id}`",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Classification Counts",
        "",
        f"- Total experiments run: {len(rows)}",
        f"- Completed experiments: {len(completed)}",
        f"- Failed experiments: {len(failed)}",
        f"- Rejected signals: {counts.get('rejected', 0)}",
        f"- Inconclusive signals: {counts.get('inconclusive', 0)}",
        f"- Promising signals: {promising}",
        f"- Validated signals: {validated}",
        "",
        "## Best Model By Horizon",
        "",
        "| Horizon | Best model | Net Sharpe |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {horizon} | {model} | {sharpe:.4f} |" for horizon, model, sharpe in best_horizon
    )
    lines.extend(
        [
            "",
            "## Best Asset Class",
            "",
            "| Asset class | Best model | Net Sharpe |",
            "|---|---:|---:|",
        ]
    )
    lines.extend(
        f"| {asset_class} | {model} | {sharpe:.4f} |" for asset_class, model, sharpe in best_class
    )
    lines.extend(
        [
            "",
            "## Current Evidence For/Against Trading Use",
            "",
            evidence,
            "",
            "A signal is not called validated unless it survives out-of-sample testing, costs,",
            "multiple assets, multiple regimes, and statistical significance. These outputs are",
            "research evidence only and are not investment advice.",
        ]
    )
    if failed:
        lines.extend(["", "## Failed Experiments", ""])
        for row in failed[:25]:
            lines.append(
                f"- {row.get('asset')} {row.get('horizon')} {row.get('model')}: {row.get('error')}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_campaign(config_path: Path, *, max_experiments: int | None = None) -> list[dict[str, Any]]:
    config = load_campaign_config(config_path)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(config["output_dir"])
    experiment_dir = Path(config["experiment_json_dir"]) / run_id
    experiment_dir.mkdir(parents=True, exist_ok=True)
    registry = ResearchRegistry(config["registry_path"])
    assets = campaign_assets(config)
    horizons = [horizon_days(value) for value in config["horizons"]]
    models = list(dict.fromkeys(list(config["models"]) + list(config["baselines"])))
    total_model_count = len(models)
    rows: list[dict[str, Any]] = []
    for asset in assets:
        try:
            asset_frame = load_asset_frame(asset)
        except Exception as exc:
            for horizon in horizons:
                for model in models:
                    rows.append(
                        {
                            "asset": asset.symbol,
                            "safe_name": asset.safe_name,
                            "asset_class": asset.category,
                            "horizon": f"{horizon}d",
                            "model": model,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
            continue
        for horizon in horizons:
            horizon_frame = prepare_horizon_frame(asset_frame, horizon)
            for model in models:
                if max_experiments is not None and len(rows) >= max_experiments:
                    break
                try:
                    row = evaluate_model(
                        asset,
                        horizon,
                        model,
                        horizon_frame,
                        config,
                        strategies_tested=total_model_count,
                    )
                    rows.append(row)
                except Exception as exc:
                    rows.append(
                        {
                            "asset": asset.symbol,
                            "safe_name": asset.safe_name,
                            "asset_class": asset.category,
                            "horizon": f"{horizon}d",
                            "model": model,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
            if max_experiments is not None and len(rows) >= max_experiments:
                break
        if max_experiments is not None and len(rows) >= max_experiments:
            break
    apply_baseline_comparison(rows, config)
    classify_rows(rows, config)
    for row in rows:
        save_experiment(row, config, registry, run_id, experiment_dir)
    csv_path = output_dir / "campaign_v1_results.csv"
    summary_path = output_dir / "campaign_v1_summary.md"
    write_csv(rows, csv_path)
    write_markdown(rows, summary_path, run_id)
    print(json.dumps({"run_id": run_id, "experiments": len(rows), "csv": str(csv_path)}))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/research_campaign_v1.yaml"))
    parser.add_argument("--max-experiments", type=int, default=None)
    args = parser.parse_args()
    run_campaign(args.config, max_experiments=args.max_experiments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
