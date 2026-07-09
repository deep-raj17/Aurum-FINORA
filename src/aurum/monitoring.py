"""Simple distribution-shift and model-performance monitoring."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field


class DriftReport(BaseModel):
    psi: float
    mean_shift_z: float
    volatility_ratio: float
    drift_detected: bool
    alerts: list[str] = Field(default_factory=list)


def population_stability_index(
    reference: list[float], current: list[float], bins: int = 10
) -> float:
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    boundaries = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(boundaries) < 3:
        return 0.0
    boundaries[0], boundaries[-1] = -np.inf, np.inf
    ref_counts = np.histogram(ref, bins=boundaries)[0] / len(ref)
    cur_counts = np.histogram(cur, bins=boundaries)[0] / len(cur)
    ref_counts = np.maximum(ref_counts, 1e-6)
    cur_counts = np.maximum(cur_counts, 1e-6)
    return float(np.sum((cur_counts - ref_counts) * np.log(cur_counts / ref_counts)))


def detect_drift(reference: list[float], current: list[float]) -> DriftReport:
    if len(reference) < 20 or len(current) < 10:
        raise ValueError("drift detection needs at least 20 reference and 10 current values")
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    ref_std = max(float(np.std(ref, ddof=1)), 1e-12)
    psi = population_stability_index(reference, current)
    mean_shift = abs(float(np.mean(cur) - np.mean(ref))) / ref_std
    volatility_ratio = float(np.std(cur, ddof=1) / ref_std)
    alerts = []
    if psi > 0.25:
        alerts.append("Population stability index exceeds 0.25")
    if mean_shift > 2:
        alerts.append("Mean shifted by more than two reference standard deviations")
    if not 0.5 <= volatility_ratio <= 2:
        alerts.append("Volatility changed by more than 2x")
    return DriftReport(
        psi=psi,
        mean_shift_z=mean_shift,
        volatility_ratio=volatility_ratio,
        drift_detected=bool(alerts),
        alerts=alerts,
    )
