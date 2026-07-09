"""Interpretable Tier-0/Tier-1 forecasting with honest model selection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

import numpy as np

from .models import ForecastRequest, ForecastResult, Interval, ModelScore
from .validation import walk_forward_validate


def _innovation_sigma(x: np.ndarray) -> float:
    differences = np.diff(x)
    if len(differences) < 2:
        return 0.0
    return float(np.std(differences, ddof=1))


def random_walk(x: np.ndarray) -> tuple[float, float]:
    return float(x[-1]), _innovation_sigma(x)


def drift(x: np.ndarray) -> tuple[float, float]:
    slope = (x[-1] - x[0]) / max(len(x) - 1, 1)
    fitted_steps = np.diff(x) - slope
    sigma = float(np.std(fitted_steps, ddof=1)) if len(fitted_steps) > 1 else 0.0
    return float(x[-1] + slope), sigma


def ar1(x: np.ndarray) -> tuple[float, float]:
    lagged, current = x[:-1], x[1:]
    design = np.column_stack((np.ones(len(lagged)), lagged))
    intercept, phi = np.linalg.lstsq(design, current, rcond=None)[0]
    phi = float(np.clip(phi, -0.999, 0.999))
    fitted = intercept + phi * lagged
    residuals = current - fitted
    sigma = float(np.std(residuals, ddof=2)) if len(residuals) > 2 else 0.0
    return float(intercept + phi * x[-1]), sigma


def historical_mean(x: np.ndarray) -> tuple[float, float]:
    window = x[-min(len(x), 60) :]
    return float(np.mean(window)), float(np.std(window, ddof=1))


def robust_drift(x: np.ndarray) -> tuple[float, float]:
    differences = np.diff(x)
    slope = float(np.median(differences))
    residuals = differences - slope
    median_absolute_deviation = float(np.median(np.abs(residuals - np.median(residuals))))
    sigma = 1.4826 * median_absolute_deviation
    return float(x[-1] + slope), sigma


def holt_linear(x: np.ndarray) -> tuple[float, float]:
    """Dependency-free Holt linear trend with conservative fixed smoothing."""
    alpha, beta = 0.35, 0.10
    level = float(x[0])
    trend = float(x[1] - x[0])
    residuals: list[float] = []
    for value in x[1:]:
        prediction = level + trend
        residuals.append(float(value - prediction))
        previous_level = level
        level = alpha * float(value) + (1 - alpha) * prediction
        trend = beta * (level - previous_level) + (1 - beta) * trend
    sigma = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
    return level + trend, sigma


def ridge_autoregression(x: np.ndarray, lags: int = 5) -> tuple[float, float]:
    """Regularized lag model (Tier 2) using deterministic closed-form ridge."""
    if len(x) <= lags + 2:
        return ar1(x)
    scale = max(float(np.std(x, ddof=1)), 1e-12)
    normalized = (x - np.mean(x)) / scale
    features = np.array([normalized[index - lags : index][::-1] for index in range(lags, len(x))])
    target = normalized[lags:]
    design = np.column_stack((np.ones(len(features)), features))
    penalty = np.eye(design.shape[1]) * 0.5
    penalty[0, 0] = 0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target)
    fitted = design @ coefficients
    residual_sigma = float(np.std(target - fitted, ddof=design.shape[1]))
    next_features = normalized[-lags:][::-1]
    prediction = float(np.r_[1.0, next_features] @ coefficients)
    return float(prediction * scale + np.mean(x)), residual_sigma * scale


def ridge_feature_importance(x: np.ndarray, lags: int = 5) -> dict[str, float]:
    if len(x) <= lags + 2:
        return {}
    scale = max(float(np.std(x, ddof=1)), 1e-12)
    normalized = (x - np.mean(x)) / scale
    features = np.array([normalized[index - lags : index][::-1] for index in range(lags, len(x))])
    target = normalized[lags:]
    design = np.column_stack((np.ones(len(features)), features))
    penalty = np.eye(design.shape[1]) * 0.5
    penalty[0, 0] = 0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target)[1:]
    magnitude = np.abs(coefficients)
    total = float(magnitude.sum()) or 1.0
    return {f"lag_{index + 1}": float(value / total) for index, value in enumerate(magnitude)}


@dataclass(frozen=True)
class Candidate:
    name: str
    predictor: Callable[[np.ndarray], tuple[float, float]]
    tier: int = 0
    importance: Callable[[np.ndarray], dict[str, float]] | None = None


CANDIDATES = (
    Candidate("random_walk", random_walk, 0),
    Candidate("historical_mean_60", historical_mean, 0),
    Candidate("drift", drift, 0),
    Candidate("robust_drift", robust_drift, 1),
    Candidate("holt_linear", holt_linear, 1),
    Candidate("ar1_ols", ar1, 1),
    Candidate("ridge_ar_5", ridge_autoregression, 2, ridge_feature_importance),
)


def project(
    predictor: Callable[[np.ndarray], tuple[float, float]],
    history: np.ndarray,
    horizon: int,
) -> tuple[float, float]:
    """Recursively project a one-step model and scale innovation uncertainty."""
    projected = np.asarray(history, dtype=float).copy()
    sigma = 0.0
    mean = float(projected[-1])
    for _ in range(horizon):
        mean, sigma = predictor(projected)
        projected = np.append(projected, mean)
    return float(mean), float(sigma * np.sqrt(horizon))


class ForecastEngine:
    def __init__(self, min_train_size: int = 20) -> None:
        self.min_train_size = min_train_size

    def forecast(self, request: ForecastRequest) -> ForecastResult:
        x = np.asarray(request.values, dtype=float)
        if len(x) <= min(self.min_train_size, max(10, len(x) // 2)) + request.horizon:
            raise ValueError(
                "insufficient history for a purge equal to the forecast horizon; "
                "provide more observations or shorten the horizon"
            )
        scores: list[ModelScore] = []
        for candidate in CANDIDATES:
            horizon_predictor = partial(project, candidate.predictor, horizon=request.horizon)
            metrics = walk_forward_validate(
                x,
                horizon_predictor,
                min_train_size=min(self.min_train_size, max(10, len(x) // 2)),
                horizon=request.horizon,
            )
            scores.append(
                ModelScore(
                    name=candidate.name,
                    metrics=metrics,
                    tier=candidate.tier,
                    feature_importance=candidate.importance(x) if candidate.importance else {},
                )
            )
        winner = min(scores, key=lambda item: item.metrics.rmse)
        predictor = next(c.predictor for c in CANDIDATES if c.name == winner.name)
        point, horizon_sigma = project(predictor, x, request.horizon)
        intervals = [
            Interval(
                level=0.8,
                lower=point - 1.2815515655 * horizon_sigma,
                upper=point + 1.2815515655 * horizon_sigma,
            ),
            Interval(
                level=0.95,
                lower=point - 1.9599639845 * horizon_sigma,
                upper=point + 1.9599639845 * horizon_sigma,
            ),
        ]
        baseline, _ = random_walk(x)
        return ForecastResult(
            target=request.target,
            horizon=request.horizon,
            frequency=request.frequency,
            model_used=winner.name,
            baseline_result=baseline,
            point_forecast=float(point),
            intervals=intervals,
            distribution_assumption="Gaussian innovations; variance scales with square-root of horizon",
            validation=winner.metrics,
            candidates=scores,
            regime_assumption="Recent data-generating process remains locally stable",
            key_risks=[
                "Structural breaks are not represented by historical residual variance",
                "Gaussian intervals may understate fat-tail risk",
            ],
            invalidation_conditions=[
                "A detected regime break or material change in volatility",
                "Selected model no longer beats the random-walk baseline out of sample",
            ],
        )
