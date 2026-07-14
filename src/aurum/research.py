"""Real-data research feature engineering and versioned evidence helpers."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from .data.contracts import MarketBar


class ResearchDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    INCONCLUSIVE = "inconclusive"


class ExperimentSpec(BaseModel):
    hypothesis: str
    dataset_version: str
    feature_version: str
    model_version: str
    training_period: str
    testing_period: str
    validation_methodology: str
    assets: list[str] = Field(default_factory=list)
    regimes: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=lambda: ["random", "buy_and_hold"])
    costs_included: bool = True
    slippage_included: bool = True


class ExperimentMetrics(BaseModel):
    observations: int
    strategy_return: float
    buy_hold_return: float
    random_return: float = 0.0
    sharpe_net: float
    max_drawdown: float
    bootstrap_p_value: float
    deflated_sharpe: float | None = None
    probability_backtest_overfit: float | None = None
    white_reality_check_p_value: float | None = None
    spa_p_value: float | None = None
    transaction_cost_bps: float = 0.0


class ExperimentConclusion(BaseModel):
    decision: ResearchDecision
    reasons: list[str]
    recommendation: str
    limitations: list[str] = Field(default_factory=list)


class ResearchExperiment(BaseModel):
    experiment_id: str
    created_at: datetime
    spec: ExperimentSpec
    metrics: ExperimentMetrics
    conclusion: ExperimentConclusion
    artifacts: dict[str, str] = Field(default_factory=dict)
    notes: str = ""


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


def experiment_id(spec: ExperimentSpec) -> str:
    payload = spec.model_dump_json()
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"exp-{digest[:16]}"


def decide_experiment(
    metrics: ExperimentMetrics,
    *,
    min_observations: int = 252,
    significance_level: float = 0.05,
    require_multi_asset: bool = True,
    require_multi_regime: bool = True,
    assets: Sequence[str] = (),
    regimes: Sequence[str] = (),
) -> ExperimentConclusion:
    reasons: list[str] = []
    limitations: list[str] = []

    if metrics.observations < min_observations:
        reasons.append(
            f"sample too small: {metrics.observations} observations below {min_observations}"
        )
    if metrics.strategy_return <= metrics.buy_hold_return:
        reasons.append("strategy does not beat buy and hold")
    if metrics.strategy_return <= metrics.random_return:
        reasons.append("strategy does not beat random baseline")
    if metrics.sharpe_net <= 0:
        reasons.append("net Sharpe is not positive")
    if metrics.bootstrap_p_value > significance_level:
        reasons.append("bootstrap test is not statistically significant")
    if metrics.white_reality_check_p_value is not None:
        if metrics.white_reality_check_p_value > significance_level:
            reasons.append("White Reality Check is not statistically significant")
    else:
        limitations.append("White Reality Check not computed")
    if metrics.spa_p_value is not None:
        if metrics.spa_p_value > significance_level:
            reasons.append("SPA test is not statistically significant")
    else:
        limitations.append("SPA test not computed")
    if metrics.deflated_sharpe is None:
        limitations.append("deflated Sharpe not computed")
    elif metrics.deflated_sharpe <= 0:
        reasons.append("deflated Sharpe is not positive")
    if metrics.probability_backtest_overfit is None:
        limitations.append("probability of backtest overfitting not computed")
    elif metrics.probability_backtest_overfit > 0.2:
        reasons.append("probability of backtest overfitting is too high")
    if require_multi_asset and len(set(assets)) < 2:
        reasons.append("strategy has not survived multiple assets")
    if require_multi_regime and len(set(regimes)) < 2:
        reasons.append("strategy has not survived multiple market regimes")

    if reasons:
        return ExperimentConclusion(
            decision=ResearchDecision.REJECT,
            reasons=reasons,
            recommendation="Reject as an investment signal until the failed evidence gates pass.",
            limitations=limitations,
        )
    if limitations:
        return ExperimentConclusion(
            decision=ResearchDecision.INCONCLUSIVE,
            reasons=["required statistical evidence is incomplete"],
            recommendation="Do not deploy; complete missing validation before promotion.",
            limitations=limitations,
        )
    return ExperimentConclusion(
        decision=ResearchDecision.ACCEPT,
        reasons=["strategy passed baseline, cost, regime, asset, and statistical gates"],
        recommendation="Candidate for paper trading with strict human review and risk limits.",
        limitations=[],
    )


class ResearchRegistry:
    """Append-only SQLite registry for quantitative research experiments."""

    def __init__(self, path: str | Path = "data/research/experiments.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_experiments (
                    experiment_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    hypothesis TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    feature_version TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL
                )
                """
            )

    def save(self, experiment: ResearchExperiment) -> str:
        payload = experiment.model_dump_json()
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO research_experiments (
                    experiment_id, created_at, hypothesis, dataset_version,
                    feature_version, model_version, decision, payload, payload_sha256
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment.experiment_id,
                    experiment.created_at.isoformat(),
                    experiment.spec.hypothesis,
                    experiment.spec.dataset_version,
                    experiment.spec.feature_version,
                    experiment.spec.model_version,
                    experiment.conclusion.decision.value,
                    payload,
                    digest,
                ),
            )
        return digest

    def get(self, experiment_id_: str) -> ResearchExperiment | None:
        row = self._connection.execute(
            "SELECT payload FROM research_experiments WHERE experiment_id = ?",
            (experiment_id_,),
        ).fetchone()
        return ResearchExperiment.model_validate_json(row["payload"]) if row else None

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT experiment_id, created_at, hypothesis, dataset_version,
                   feature_version, model_version, decision, payload_sha256
            FROM research_experiments
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
