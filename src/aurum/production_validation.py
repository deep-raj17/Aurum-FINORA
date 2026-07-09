"""Phase 3 calibration datasets, regime validation, and trading evaluation."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import date
from enum import StrEnum

import numpy as np
from pydantic import BaseModel, Field, model_validator

from .backtest import BacktestResult, evaluate_strategy


class MarketRegime(StrEnum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high-volatility"
    CRISIS = "crisis"


class WindowMode(StrEnum):
    EXPANDING = "expanding"
    ROLLING = "rolling"


class CalibrationRecord(BaseModel):
    origin: date
    target_date: date
    actual: float
    prediction: float
    lower: float
    upper: float
    previous: float
    regime: MarketRegime

    @model_validator(mode="after")
    def valid(self) -> CalibrationRecord:
        if self.origin >= self.target_date:
            raise ValueError("target date must follow forecast origin")
        if self.lower > self.upper:
            raise ValueError("calibration bounds are reversed")
        return self


class CalibrationDataset(BaseModel):
    name: str
    version: str
    records: list[CalibrationRecord] = Field(min_length=1)
    source_hashes: list[str] = Field(min_length=1)

    @property
    def dataset_hash(self) -> str:
        payload = self.model_dump_json(exclude_none=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def write_jsonl(self, path) -> str:
        from pathlib import Path

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        lines = [record.model_dump_json() for record in self.records]
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.dataset_hash


class EvaluationMetrics(BaseModel):
    observations: int
    mae: float
    rmse: float
    mape: float
    directional_accuracy: float
    interval_coverage: float
    calibration_ece: float


class ProductionValidationReport(BaseModel):
    dataset_name: str
    dataset_version: str
    dataset_hash: str
    window_mode: WindowMode
    overall: EvaluationMetrics
    regimes: dict[MarketRegime, EvaluationMetrics]
    strategy: BacktestResult


def classify_regime(history: Sequence[float], annualisation: int = 252) -> MarketRegime:
    values = np.asarray(history, dtype=float)
    if len(values) < 20 or np.any(values <= 0):
        raise ValueError("regime classification requires at least 20 positive levels")
    returns = np.diff(np.log(values[-60:]))
    volatility = float(np.std(returns, ddof=1) * np.sqrt(annualisation))
    drawdown = float(values[-1] / np.max(values[-60:]) - 1)
    annual_return = float(np.mean(returns) * annualisation)
    if drawdown <= -0.2 or volatility >= 0.5:
        return MarketRegime.CRISIS
    if volatility >= 0.25:
        return MarketRegime.HIGH_VOLATILITY
    if annual_return >= 0.1:
        return MarketRegime.BULL
    if annual_return <= -0.1:
        return MarketRegime.BEAR
    return MarketRegime.SIDEWAYS


class ConformalCalibrator:
    def __init__(self, coverage: float = 0.8) -> None:
        if not 0 < coverage < 1:
            raise ValueError("coverage must be between zero and one")
        self.coverage = coverage
        self.radius: float | None = None

    def fit(self, actual: Sequence[float], predicted: Sequence[float]) -> float:
        y, yhat = np.asarray(actual), np.asarray(predicted)
        if y.shape != yhat.shape or len(y) < 5:
            raise ValueError("conformal calibration requires at least five aligned residuals")
        residuals = np.abs(y - yhat)
        level = min(1.0, np.ceil((len(y) + 1) * self.coverage) / len(y))
        self.radius = float(np.quantile(residuals, level, method="higher"))
        return self.radius

    def interval(self, predictions: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
        if self.radius is None:
            raise RuntimeError("calibrator must be fitted before interval generation")
        values = np.asarray(predictions, dtype=float)
        return values - self.radius, values + self.radius


Predictor = Callable[[np.ndarray, int], tuple[float, float, float]]


def walk_forward_records(
    values: Sequence[float],
    dates: Sequence[date],
    predictor: Predictor,
    *,
    horizon: int = 1,
    minimum_train_size: int = 60,
    mode: WindowMode = WindowMode.EXPANDING,
    rolling_window: int = 252,
) -> list[CalibrationRecord]:
    series = np.asarray(values, dtype=float)
    if len(series) != len(dates) or list(dates) != sorted(dates):
        raise ValueError("values and dates must be aligned and chronological")
    if mode is WindowMode.ROLLING and rolling_window < minimum_train_size:
        raise ValueError("rolling window cannot be shorter than minimum training size")
    records = []
    for target_index in range(minimum_train_size + horizon - 1, len(series), horizon):
        train_end = target_index - horizon + 1
        train_start = 0 if mode is WindowMode.EXPANDING else max(0, train_end - rolling_window)
        train = series[train_start:train_end]
        prediction, lower, upper = predictor(train, horizon)
        records.append(
            CalibrationRecord(
                origin=dates[train_end - 1],
                target_date=dates[target_index],
                actual=float(series[target_index]),
                prediction=float(prediction),
                lower=float(lower),
                upper=float(upper),
                previous=float(series[train_end - 1]),
                regime=classify_regime(series[:train_end].tolist()),
            )
        )
    if not records:
        raise ValueError("insufficient observations for walk-forward evaluation")
    return records


def _metrics(records: Sequence[CalibrationRecord]) -> EvaluationMetrics:
    actual = np.asarray([row.actual for row in records])
    prediction = np.asarray([row.prediction for row in records])
    previous = np.asarray([row.previous for row in records])
    covered = np.asarray([row.lower <= row.actual <= row.upper for row in records])
    errors = actual - prediction
    nonzero = np.abs(actual) > np.finfo(float).eps
    nominal = 0.8
    return EvaluationMetrics(
        observations=len(records),
        mae=float(np.mean(np.abs(errors))),
        rmse=float(np.sqrt(np.mean(errors**2))),
        mape=float(np.mean(np.abs(errors[nonzero] / actual[nonzero]))) if np.any(nonzero) else 0.0,
        directional_accuracy=float(
            np.mean(np.sign(actual - previous) == np.sign(prediction - previous))
        ),
        interval_coverage=float(np.mean(covered)),
        calibration_ece=abs(float(np.mean(covered)) - nominal),
    )


def evaluate_calibration_dataset(
    dataset: CalibrationDataset,
    *,
    window_mode: WindowMode,
    round_trip_bps: float = 10,
    slippage_bps: float = 5,
) -> ProductionValidationReport:
    regime_metrics = {
        regime: _metrics(rows)
        for regime in MarketRegime
        if (rows := [record for record in dataset.records if record.regime is regime])
    }
    actual = np.asarray([row.actual for row in dataset.records])
    previous = np.asarray([row.previous for row in dataset.records])
    returns = (actual / previous - 1).tolist()
    positions = [float(np.sign(row.prediction - row.previous)) for row in dataset.records]
    return ProductionValidationReport(
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        dataset_hash=dataset.dataset_hash,
        window_mode=window_mode,
        overall=_metrics(dataset.records),
        regimes=regime_metrics,
        strategy=evaluate_strategy(
            returns,
            positions,
            round_trip_bps=round_trip_bps,
            slippage_bps=slippage_bps,
        ),
    )
