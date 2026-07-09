"""Installed CLI for the seeded, offline FINORA demonstration."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import numpy as np

from .models import ForecastRequest
from .pipeline import FinoraPipeline


def main() -> None:
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0003, 0.01, 180)
    values = (100 * np.exp(np.cumsum(returns))).tolist()
    end = date.today() - timedelta(days=1)
    dates = [end - timedelta(days=len(values) - 1 - index) for index in range(len(values))]
    request = ForecastRequest(
        target="SYNTHETIC_INDEX",
        values=values,
        dates=dates,
        horizon=5,
        forecast_start=datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC),
    )
    report = FinoraPipeline().run(request)
    print(json.dumps(report.model_dump(mode="json"), indent=2))
