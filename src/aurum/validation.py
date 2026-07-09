"""Leakage-resistant chronological validation and calibration metrics."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from .models import ValidationMetrics

Predictor = Callable[[np.ndarray], tuple[float, float]]


def walk_forward_validate(
    values: np.ndarray,
    predictor: Predictor,
    *,
    min_train_size: int = 20,
    horizon: int = 1,
    embargo: int | None = None,
) -> ValidationMetrics:
    """Evaluate one-step forecasts using expanding windows and an explicit purge.

    ``predictor`` returns (mean, standard deviation). The default purge is one
    forecast horizon. This is intentionally conservative for overlapping labels.
    """
    x = np.asarray(values, dtype=float)
    purge = horizon if embargo is None else embargo
    actual: list[float] = []
    predicted: list[float] = []
    sigmas: list[float] = []
    previous: list[float] = []
    for test_idx in range(min_train_size + purge - 1, len(x), horizon):
        # Include the information available at the forecast origin. With a
        # horizon/purge of H, the final training value is exactly H periods
        # before the target.
        train_end = test_idx - purge + 1
        if train_end < min_train_size:
            continue
        mean, sigma = predictor(x[:train_end])
        actual.append(float(x[test_idx]))
        predicted.append(float(mean))
        sigmas.append(max(float(sigma), 1e-12))
        previous.append(float(x[train_end - 1]))
    if not actual:
        raise ValueError("insufficient observations for walk-forward validation")
    y = np.asarray(actual)
    yhat = np.asarray(predicted)
    prev = np.asarray(previous)
    errors = y - yhat
    coverage_error = []
    for level, z in ((0.8, 1.2815515655), (0.95, 1.9599639845)):
        covered = np.abs(errors) <= z * np.asarray(sigmas)
        coverage_error.append(abs(float(covered.mean()) - level))
    actual_direction = np.sign(y - prev)
    predicted_direction = np.sign(yhat - prev)
    return ValidationMetrics(
        mae=float(np.mean(np.abs(errors))),
        rmse=float(np.sqrt(np.mean(errors**2))),
        mape=float(np.mean(np.abs(errors / np.maximum(np.abs(y), 1e-12)))),
        directional_accuracy=float(np.mean(actual_direction == predicted_direction)),
        calibration_ece=float(np.mean(coverage_error)),
        observations=len(y),
    )
