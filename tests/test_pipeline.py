from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from aurum.governance import GovernanceError
from aurum.models import Citation, Confidence, ForecastRequest
from aurum.pipeline import FinoraPipeline


def make_request(size: int = 100, horizon: int = 2) -> ForecastRequest:
    rng = np.random.default_rng(7)
    values = (100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, size)))).tolist()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    dates = [start.date() - timedelta(days=size - index) for index in range(size)]
    return ForecastRequest(
        target="TEST",
        values=values,
        dates=dates,
        horizon=horizon,
        forecast_start=start,
    )


def test_pipeline_produces_intervals_scores_risk_and_audit() -> None:
    report = FinoraPipeline().run(make_request())
    assert {interval.level for interval in report.forecast.intervals} == {0.8, 0.95}
    assert len(report.forecast.candidates) == 7
    ridge = next(score for score in report.forecast.candidates if score.name == "ridge_ar_5")
    assert sum(ridge.feature_importance.values()) == pytest.approx(1)
    assert report.forecast.validation.observations > 0
    assert report.risk.observations == 99
    assert sum(item.probability for item in report.scenarios) == pytest.approx(1)
    assert report.audit.human_review_needed.startswith("Yes")
    assert report.audit.regulatory_flags


def test_future_evidence_is_rejected() -> None:
    request = make_request()
    citation = Citation(
        origin="Future News",
        published_at=request.forecast_start + timedelta(minutes=1),
        confidence=Confidence.HIGH,
        relevance=0.9,
        excerpt="This must not enter a backward-looking forecast.",
    )
    with pytest.raises(GovernanceError, match="lookahead"):
        FinoraPipeline().run(request, [citation])


def test_misaligned_dates_are_rejected() -> None:
    request = make_request().model_dump()
    request["dates"] = request["dates"][:-1]
    with pytest.raises(ValueError, match="equal length"):
        ForecastRequest.model_validate(request)
