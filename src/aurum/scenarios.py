"""Evidence-linked scenario probability and range construction."""

from __future__ import annotations

from .models import ForecastResult, Interval, Scenario


def build_scenarios(forecast: ForecastResult) -> tuple[list[Scenario], str]:
    interval_95 = next(item for item in forecast.intervals if item.level == 0.95)
    width = interval_95.upper - interval_95.lower
    # Confidence is mechanically reduced when calibration error is high.
    calibration_penalty = min(0.15, forecast.validation.calibration_ece / 2)
    baseline_probability = 0.60 - calibration_penalty
    downside_probability = 0.25 + calibration_penalty
    upside_probability = 1 - baseline_probability - downside_probability
    scenarios = [
        Scenario(
            name="Baseline",
            probability=baseline_probability,
            assumptions=["Local regime stability", forecast.distribution_assumption],
            expected_range=interval_95,
        ),
        Scenario(
            name="Downside",
            probability=downside_probability,
            assumptions=["Adverse residual shock and volatility expansion"],
            triggers=["Regime break", "Volatility exceeds two times validation volatility"],
            expected_range=Interval(
                level=0.95,
                lower=interval_95.lower - 0.5 * width,
                upper=forecast.point_forecast,
            ),
        ),
        Scenario(
            name="Upside",
            probability=upside_probability,
            assumptions=["Favourable shock without a volatility break"],
            triggers=["Realised path persists above the upper 80% bound"],
            expected_range=Interval(
                level=0.95,
                lower=forecast.point_forecast,
                upper=interval_95.upper + 0.25 * width,
            ),
        ),
    ]
    basis = (
        "Policy prior (60/25/15) adjusted by half of walk-forward interval "
        f"calibration ECE ({forecast.validation.calibration_ece:.4f}), capped at 15pp"
    )
    return scenarios, basis
