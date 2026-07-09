"""Slice-based forecast error and calibration disparity analysis."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from pydantic import BaseModel, Field


class BiasObservation(BaseModel):
    slice_name: str
    slice_value: str
    actual: float
    prediction: float
    lower: float
    upper: float


class SliceMetrics(BaseModel):
    observations: int
    mae: float
    rmse: float
    interval_coverage: float


class BiasReport(BaseModel):
    slices: dict[str, SliceMetrics]
    maximum_rmse_ratio: float
    maximum_coverage_gap: float
    passed: bool
    warnings: list[str] = Field(default_factory=list)


def evaluate_bias(
    observations: list[BiasObservation],
    *,
    minimum_slice_size: int = 20,
    maximum_rmse_ratio: float = 2.0,
    maximum_coverage_gap: float = 0.2,
) -> BiasReport:
    if not observations:
        raise ValueError("bias evaluation requires observations")
    grouped: dict[str, list[BiasObservation]] = defaultdict(list)
    for row in observations:
        grouped[f"{row.slice_name}={row.slice_value}"].append(row)
    metrics = {}
    warnings = []
    for name, rows in grouped.items():
        if len(rows) < minimum_slice_size:
            warnings.append(f"{name} has only {len(rows)} observations")
            continue
        actual = np.asarray([row.actual for row in rows])
        prediction = np.asarray([row.prediction for row in rows])
        errors = actual - prediction
        metrics[name] = SliceMetrics(
            observations=len(rows),
            mae=float(np.mean(np.abs(errors))),
            rmse=float(np.sqrt(np.mean(errors**2))),
            interval_coverage=float(
                np.mean([row.lower <= row.actual <= row.upper for row in rows])
            ),
        )
    if len(metrics) < 2:
        return BiasReport(
            slices=metrics,
            maximum_rmse_ratio=float("inf"),
            maximum_coverage_gap=1.0,
            passed=False,
            warnings=[*warnings, "at least two adequately sized slices are required"],
        )
    rmses = [metric.rmse for metric in metrics.values()]
    coverages = [metric.interval_coverage for metric in metrics.values()]
    rmse_ratio = max(rmses) / max(min(rmses), 1e-12)
    coverage_gap = max(coverages) - min(coverages)
    passed = (
        rmse_ratio <= maximum_rmse_ratio and coverage_gap <= maximum_coverage_gap and not warnings
    )
    return BiasReport(
        slices=metrics,
        maximum_rmse_ratio=rmse_ratio,
        maximum_coverage_gap=coverage_gap,
        passed=passed,
        warnings=warnings,
    )
