"""Production forecasting adapters, validation, calibration, and ensembling.

Heavy model runtimes are imported only when their adapter is used. This keeps
the core service lean while ensuring a configured specialist either performs
real inference or fails explicitly--there are no surrogate predictions.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import import_module
from typing import Any, Protocol

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ForecastDistribution:
    model: str
    mean: np.ndarray
    quantiles: dict[float, np.ndarray]
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        mean = np.asarray(self.mean, dtype=float)
        if mean.ndim != 1 or not len(mean) or not np.all(np.isfinite(mean)):
            raise ValueError("forecast mean must be a finite one-dimensional array")
        previous: np.ndarray | None = None
        for level, values in sorted(self.quantiles.items()):
            candidate = np.asarray(values, dtype=float)
            if not 0 < level < 1 or candidate.shape != mean.shape:
                raise ValueError("quantiles must use levels in (0, 1) and match the horizon")
            if not np.all(np.isfinite(candidate)):
                raise ValueError("forecast quantiles must be finite")
            if previous is not None and np.any(candidate < previous):
                raise ValueError("forecast quantiles cross")
            previous = candidate


class ForecastSpecialist(Protocol):
    name: str

    def forecast(
        self, values: np.ndarray, dates: Sequence[date], horizon: int
    ) -> ForecastDistribution: ...


def _validate_series(
    values: np.ndarray, dates: Sequence[date], horizon: int, minimum: int
) -> np.ndarray:
    series = np.asarray(values, dtype=float)
    if series.ndim != 1 or len(series) != len(dates):
        raise ValueError("values and dates must be aligned one-dimensional sequences")
    if len(series) < minimum:
        raise ValueError(f"at least {minimum} observations are required")
    if horizon < 1:
        raise ValueError("horizon must be positive")
    if not np.all(np.isfinite(series)):
        raise ValueError("forecast input contains non-finite values")
    if list(dates) != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError("dates must be unique and chronologically sorted")
    return series


def _lag_matrix(series: np.ndarray, lags: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    rows: list[np.ndarray] = []
    targets: list[float] = []
    for index in range(lags, len(series) - horizon + 1):
        window = series[index - lags : index]
        differences = np.diff(window)
        rows.append(
            np.concatenate(
                (
                    window,
                    [
                        float(window.mean()),
                        float(window.std(ddof=1)),
                        float(differences.mean()),
                        float(differences.std(ddof=1)) if len(differences) > 1 else 0.0,
                    ],
                )
            )
        )
        targets.append(float(series[index + horizon - 1]))
    if not rows:
        raise ValueError("insufficient observations after lag and horizon construction")
    return np.vstack(rows), np.asarray(targets)


def _latest_features(series: np.ndarray, lags: int) -> np.ndarray:
    window = series[-lags:]
    differences = np.diff(window)
    return np.concatenate(
        (
            window,
            [
                float(window.mean()),
                float(window.std(ddof=1)),
                float(differences.mean()),
                float(differences.std(ddof=1)) if len(differences) > 1 else 0.0,
            ],
        )
    )[None, :]


class TreeQuantileSpecialist:
    """Direct multi-horizon XGBoost, LightGBM, or CatBoost quantile specialist."""

    def __init__(
        self,
        engine: str,
        *,
        lags: int = 30,
        quantiles: tuple[float, ...] = (0.1, 0.5, 0.9),
        random_state: int = 17,
        estimator_factory: Callable[[float], Any] | None = None,
    ) -> None:
        if engine not in {"xgboost", "lightgbm", "catboost"}:
            raise ValueError("engine must be xgboost, lightgbm, or catboost")
        if tuple(sorted(quantiles)) != quantiles or 0.5 not in quantiles:
            raise ValueError("quantiles must be ordered and include the median")
        self.engine = engine
        self.name = engine
        self.lags = lags
        self.quantiles = quantiles
        self.random_state = random_state
        self._estimator_factory = estimator_factory

    def _estimator(self, quantile: float) -> Any:
        if self._estimator_factory:
            return self._estimator_factory(quantile)
        if self.engine == "xgboost":
            module = import_module("xgboost")
            return module.XGBRegressor(
                objective="reg:quantileerror",
                quantile_alpha=quantile,
                n_estimators=350,
                max_depth=5,
                learning_rate=0.035,
                subsample=0.85,
                colsample_bytree=0.85,
                tree_method="hist",
                random_state=self.random_state,
                n_jobs=1,
            )
        if self.engine == "lightgbm":
            module = import_module("lightgbm")
            return module.LGBMRegressor(
                objective="quantile",
                alpha=quantile,
                n_estimators=350,
                num_leaves=31,
                learning_rate=0.035,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=self.random_state,
                n_jobs=1,
                verbosity=-1,
            )
        module = import_module("catboost")
        return module.CatBoostRegressor(
            loss_function=f"Quantile:alpha={quantile}",
            iterations=350,
            depth=6,
            learning_rate=0.035,
            random_seed=self.random_state,
            thread_count=1,
            verbose=False,
            allow_writing_files=False,
        )

    def forecast(
        self, values: np.ndarray, dates: Sequence[date], horizon: int
    ) -> ForecastDistribution:
        series = _validate_series(values, dates, horizon, self.lags + horizon + 20)
        predictions = {level: np.empty(horizon) for level in self.quantiles}
        feature_names = [f"lag_{lag}" for lag in range(self.lags, 0, -1)] + [
            "level_mean",
            "level_std",
            "change_mean",
            "change_std",
        ]
        importances: list[np.ndarray] = []
        for step in range(1, horizon + 1):
            features, target = _lag_matrix(series, self.lags, step)
            current = _latest_features(series, self.lags)
            for level in self.quantiles:
                estimator = self._estimator(level)
                estimator.fit(features, target)
                predictions[level][step - 1] = float(estimator.predict(current)[0])
                if level == 0.5 and hasattr(estimator, "feature_importances_"):
                    importances.append(np.asarray(estimator.feature_importances_, dtype=float))
        ordered = np.maximum.accumulate(
            np.vstack([predictions[level] for level in self.quantiles]), axis=0
        )
        predictions = {level: ordered[index] for index, level in enumerate(self.quantiles)}
        importance: dict[str, float] = {}
        if importances:
            average = np.mean(importances, axis=0)
            total = float(average.sum()) or 1.0
            importance = dict(zip(feature_names, (average / total).tolist(), strict=True))
        return ForecastDistribution(
            model=self.name,
            mean=predictions[0.5],
            quantiles=predictions,
            metadata={
                "strategy": "direct_multi_horizon_quantile_regression",
                "feature_importance": importance,
                "training_observations": len(series),
            },
        )


class Chronos2Specialist:
    """Zero-shot probabilistic adapter for Amazon Chronos-2.

    Supports lazy loading and configurable model cache directory.
    For RTX 4070 12GB VRAM, use smaller variants like amazon/chronos-t5-tiny.
    """

    name = "chronos-2"

    def __init__(
        self,
        model_id: str = "amazon/chronos-t5-tiny",
        *,
        device_map: str = "auto",
        pipeline: Any | None = None,
        cache_dir: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.device_map = device_map
        self._pipeline = pipeline
        self._cache_dir = cache_dir

    def _load(self) -> Any:
        if self._pipeline is None:
            chronos = import_module("chronos")
            pipeline_type = (
                chronos.Chronos2Pipeline
                if "chronos-2" in self.model_id.lower()
                else chronos.ChronosPipeline
            )
            kwargs = {"device_map": self.device_map}
            if self._cache_dir:
                kwargs["cache_dir"] = self._cache_dir
            self._pipeline = pipeline_type.from_pretrained(self.model_id, **kwargs)
        return self._pipeline

    def forecast(
        self, values: np.ndarray, dates: Sequence[date], horizon: int
    ) -> ForecastDistribution:
        series = _validate_series(values, dates, horizon, 20)
        pipeline = self._load()
        if not hasattr(pipeline, "predict_df"):
            torch = import_module("torch")
            samples = pipeline.predict(
                torch.tensor(series, dtype=torch.float32),
                prediction_length=horizon,
                num_samples=50,
            )
            sample_array = np.asarray(
                samples[0].detach().float().cpu() if hasattr(samples[0], "detach") else samples[0],
                dtype=float,
            )
            if sample_array.ndim != 2 or sample_array.shape[-1] != horizon:
                raise RuntimeError("Chronos returned an unexpected sample schema")
            quantiles = {
                level: np.quantile(sample_array, level, axis=0) for level in (0.1, 0.5, 0.9)
            }
            return ForecastDistribution(
                model=self.name,
                mean=quantiles[0.5],
                quantiles=quantiles,
                metadata={"model_id": self.model_id, "zero_shot": True},
            )
        frame = pd.DataFrame({"id": "series", "timestamp": dates, "target": series})
        output = pipeline.predict_df(
            frame,
            prediction_length=horizon,
            quantile_levels=[0.1, 0.5, 0.9],
            id_column="id",
            timestamp_column="timestamp",
            target="target",
        )
        required = {"predictions", "0.1", "0.5", "0.9"}
        if not required.issubset(output.columns) or len(output) != horizon:
            raise RuntimeError("Chronos returned an unexpected forecast schema")
        return ForecastDistribution(
            model=self.name,
            mean=output["predictions"].to_numpy(dtype=float),
            quantiles={
                level: output[str(level)].to_numpy(dtype=float) for level in (0.1, 0.5, 0.9)
            },
            metadata={"model_id": self.model_id, "zero_shot": True},
        )


class NeuralForecastSpecialist:
    """Train-and-predict adapter for FINORA neural forecasting experts."""

    SUPPORTED = {
        "patchtst": "PatchTST",
        "itransformer": "iTransformer",
        "tft": "TFT",
        "tide": "TiDE",
        # Retained for API/config compatibility, but no longer a primary FINORA-MoE expert.
        "nhits": "NHITS",
    }

    def __init__(
        self,
        architecture: str,
        *,
        input_size: int = 60,
        max_steps: int = 300,
        model_factory: Callable[..., Any] | None = None,
        forecast_factory: Callable[..., Any] | None = None,
    ) -> None:
        key = architecture.lower()
        if key not in self.SUPPORTED:
            raise ValueError(f"unsupported architecture: {architecture}")
        self.architecture = key
        self.name = key
        self.input_size = input_size
        self.max_steps = max_steps
        self._model_factory = model_factory
        self._forecast_factory = forecast_factory

    def forecast(
        self, values: np.ndarray, dates: Sequence[date], horizon: int
    ) -> ForecastDistribution:
        series = _validate_series(values, dates, horizon, self.input_size + horizon + 20)
        if self._model_factory is None:
            model_type = getattr(
                import_module("neuralforecast.models"), self.SUPPORTED[self.architecture]
            )
        else:
            model_type = self._model_factory
        loss = import_module("neuralforecast.losses.pytorch").MQLoss(level=[80])
        model_kwargs = {
            "h": horizon,
            "input_size": self.input_size,
            "loss": loss,
            "valid_loss": loss,
            "max_steps": self.max_steps,
            "scaler_type": "robust",
            "early_stop_patience_steps": 5,
            "val_check_steps": max(10, self.max_steps // 10),
            "random_seed": 17,
        }
        if self.architecture == "itransformer":
            # The common adapter currently supplies one target series. Multivariate
            # orchestration can raise this when expert inputs include related assets.
            model_kwargs["n_series"] = 1
        model = model_type(
            **model_kwargs,
        )
        forecast_type = self._forecast_factory
        if forecast_type is None:
            forecast_type = import_module("neuralforecast").NeuralForecast
        frequency = pd.infer_freq(pd.DatetimeIndex(dates)) or "D"
        engine = forecast_type(models=[model], freq=frequency)
        frame = pd.DataFrame(
            {"unique_id": "series", "ds": pd.to_datetime(list(dates)), "y": series}
        )
        validation_size = min(max(horizon * 2, 10), max(len(series) // 5, horizon))
        engine.fit(df=frame, val_size=validation_size)
        output = engine.predict().reset_index(drop=False)
        numeric = [
            column for column in output.columns if column not in {"unique_id", "ds", "index"}
        ]
        median_columns = [column for column in numeric if "median" in column.lower()]
        low_columns = [column for column in numeric if "lo-80" in column.lower()]
        high_columns = [column for column in numeric if "hi-80" in column.lower()]
        if not median_columns:
            median_columns = [
                column
                for column in numeric
                if column.lower() == self.name or column.lower().endswith("-median")
            ]
        if not median_columns or not low_columns or not high_columns or len(output) != horizon:
            raise RuntimeError("NeuralForecast returned an unexpected probabilistic schema")
        raw_quantiles = np.vstack(
            [
                output[low_columns[0]].to_numpy(dtype=float),
                output[median_columns[0]].to_numpy(dtype=float),
                output[high_columns[0]].to_numpy(dtype=float),
            ]
        )
        ordered = np.maximum.accumulate(raw_quantiles, axis=0)
        median = ordered[1]
        return ForecastDistribution(
            model=self.name,
            mean=median,
            quantiles={
                0.1: ordered[0],
                0.5: median,
                0.9: ordered[2],
            },
            metadata={
                "architecture": self.SUPPORTED[self.architecture],
                "validation_size": validation_size,
                "max_steps": self.max_steps,
            },
        )


@dataclass(frozen=True)
class SpecialistScore:
    name: str
    mae: float
    rmse: float
    directional_accuracy: float
    interval_coverage: float
    regime: str
    observations: int


def classify_volatility_regime(values: np.ndarray, window: int = 20) -> str:
    changes = np.diff(np.asarray(values, dtype=float))
    if len(changes) < window * 2:
        return "insufficient-history"
    recent = float(np.std(changes[-window:], ddof=1))
    history = np.array(
        [np.std(changes[index - window : index], ddof=1) for index in range(window, len(changes))]
    )
    low, high = np.quantile(history, [0.33, 0.67])
    return "low" if recent <= low else "high" if recent >= high else "normal"


class ProductionForecastEngine:
    """Leakage-resistant model selection plus conformal interval calibration."""

    def __init__(
        self,
        specialists: Sequence[ForecastSpecialist],
        *,
        minimum_train_size: int = 80,
        validation_windows: int = 8,
    ) -> None:
        if not specialists:
            raise ValueError("at least one forecasting specialist is required")
        self.specialists = list(specialists)
        self.minimum_train_size = minimum_train_size
        self.validation_windows = validation_windows

    def _evaluate(
        self,
        specialist: ForecastSpecialist,
        values: np.ndarray,
        dates: Sequence[date],
        horizon: int,
    ) -> tuple[SpecialistScore, np.ndarray]:
        starts = range(
            max(self.minimum_train_size, len(values) - self.validation_windows * horizon),
            len(values) - horizon + 1,
            horizon,
        )
        actual: list[float] = []
        predicted: list[float] = []
        previous: list[float] = []
        covered: list[bool] = []
        residuals: list[float] = []
        for stop in starts:
            result = specialist.forecast(values[:stop], dates[:stop], horizon)
            target = float(values[stop + horizon - 1])
            estimate = float(result.mean[horizon - 1])
            actual.append(target)
            predicted.append(estimate)
            previous.append(float(values[stop - 1]))
            residuals.append(abs(target - estimate))
            if 0.1 in result.quantiles and 0.9 in result.quantiles:
                covered.append(
                    float(result.quantiles[0.1][horizon - 1])
                    <= target
                    <= float(result.quantiles[0.9][horizon - 1])
                )
        if not actual:
            raise ValueError("insufficient observations for production model selection")
        y, yhat, prior = np.asarray(actual), np.asarray(predicted), np.asarray(previous)
        score = SpecialistScore(
            name=specialist.name,
            mae=float(np.mean(np.abs(y - yhat))),
            rmse=float(np.sqrt(np.mean((y - yhat) ** 2))),
            directional_accuracy=float(np.mean(np.sign(y - prior) == np.sign(yhat - prior))),
            interval_coverage=float(np.mean(covered)) if covered else 0.0,
            regime=classify_volatility_regime(values),
            observations=len(actual),
        )
        return score, np.asarray(residuals)

    def forecast(
        self, values: Sequence[float], dates: Sequence[date], horizon: int
    ) -> tuple[ForecastDistribution, list[SpecialistScore]]:
        series = _validate_series(
            np.asarray(values, dtype=float), dates, horizon, self.minimum_train_size + horizon
        )
        evaluations = [
            (specialist, *self._evaluate(specialist, series, dates, horizon))
            for specialist in self.specialists
        ]
        evaluations.sort(key=lambda item: (item[1].rmse, item[1].mae))
        winner, _, residuals = evaluations[0]
        result = winner.forecast(series, dates, horizon)
        correction = float(np.quantile(residuals, 0.8, method="higher"))
        low = result.quantiles.get(0.1, result.mean - correction)
        high = result.quantiles.get(0.9, result.mean + correction)
        calibrated_low = np.minimum(low, result.mean - correction)
        calibrated_high = np.maximum(high, result.mean + correction)
        calibrated = ForecastDistribution(
            model=result.model,
            mean=result.mean,
            quantiles={0.1: calibrated_low, 0.5: result.mean, 0.9: calibrated_high},
            metadata={
                **result.metadata,
                "selection": "walk_forward_rmse",
                "conformal_absolute_error_80": correction,
                "regime": classify_volatility_regime(series),
                "forecast_origin": (dates[-1] + timedelta(days=1)).isoformat(),
            },
        )
        return calibrated, [item[1] for item in evaluations]
