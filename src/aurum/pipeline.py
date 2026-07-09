"""End-to-end deterministic FINORA forecast report assembly."""

from __future__ import annotations

from .config import Settings
from .forecasting import ForecastEngine
from .governance import build_audit, verify_temporal_grounding
from .models import AnalysisReport, Citation, ForecastRequest
from .risk import calculate_risk
from .scenarios import build_scenarios


class FinoraPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.forecaster = ForecastEngine(self.settings.min_train_size)

    def run(
        self, request: ForecastRequest, citations: list[Citation] | None = None
    ) -> AnalysisReport:
        evidence = list(citations or [])
        verify_temporal_grounding(evidence, request)
        forecast = self.forecaster.forecast(request)
        risk = calculate_risk(request.values, self.settings.annualisation_factor)
        interval_95 = next(item for item in forecast.intervals if item.level == 0.95)
        scenarios, probability_basis = build_scenarios(forecast)
        limitations = [
            "Scenario probabilities are calibration-adjusted policy priors, not posteriors",
            "Only Tier-0/Tier-1 models are active in the offline core",
            "Risk estimates are historical and may understate discontinuous losses",
        ]
        audit = build_audit(
            request,
            model_version=self.settings.model_version,
            citations=evidence,
            limitations=limitations,
        )
        summary = (
            f"{forecast.model_used} was selected by purged walk-forward RMSE for "
            f"{request.target}. The {request.horizon}-period estimate is "
            f"{forecast.point_forecast:.4f}, with a 95% interval of "
            f"[{interval_95.lower:.4f}, {interval_95.upper:.4f}]. "
            "This is probabilistic decision support, not a trade recommendation."
        )
        return AnalysisReport(
            executive_summary=summary,
            forecast=forecast,
            risk=risk,
            scenarios=scenarios,
            citations=evidence,
            what_would_change_this_view=forecast.invalidation_conditions,
            audit=audit,
            metadata={"scenario_probability_basis": probability_basis},
        )
