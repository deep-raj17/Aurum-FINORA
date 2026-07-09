"""Shared, serialisable contracts used across FINORA capability layers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Confidence(StrEnum):
    HIGH = "H"
    MEDIUM = "M"
    LOW = "L"


class Citation(BaseModel):
    origin: str
    published_at: datetime
    confidence: Confidence = Confidence.MEDIUM
    relevance: float = Field(ge=0, le=1)
    excerpt: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def label(self) -> str:
        return (
            f"[SOURCE: {self.origin} | DATE: {self.published_at.date().isoformat()} | "
            f"CONFIDENCE: {self.confidence.value} | RELEVANCE: {self.relevance:.2f}]"
        )


class Interval(BaseModel):
    level: float = Field(gt=0, lt=1)
    lower: float
    upper: float

    @model_validator(mode="after")
    def ordered(self) -> Interval:
        if self.lower > self.upper:
            raise ValueError("lower interval bound must not exceed upper bound")
        return self


class ForecastRequest(BaseModel):
    target: str
    values: list[float] = Field(min_length=20)
    dates: list[date]
    horizon: int = Field(default=1, ge=1, le=252)
    frequency: str = "daily"
    forecast_start: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def aligned(self) -> ForecastRequest:
        if len(self.values) != len(self.dates):
            raise ValueError("values and dates must have equal length")
        if self.dates != sorted(self.dates) or len(set(self.dates)) != len(self.dates):
            raise ValueError("dates must be unique and chronologically sorted")
        if self.dates[-1] >= self.forecast_start.date():
            raise ValueError("all observations must be prior to forecast_start")
        return self


class ValidationMetrics(BaseModel):
    mae: float
    rmse: float
    mape: float = 0.0
    directional_accuracy: float
    calibration_ece: float
    observations: int


class ModelScore(BaseModel):
    name: str
    metrics: ValidationMetrics
    tier: int = 0
    feature_importance: dict[str, float] = Field(default_factory=dict)


class ForecastResult(BaseModel):
    target: str
    horizon: int
    frequency: str
    model_used: str
    baseline_result: float
    point_forecast: float
    intervals: list[Interval]
    distribution_assumption: str
    validation: ValidationMetrics
    candidates: list[ModelScore]
    regime_assumption: str
    key_risks: list[str]
    invalidation_conditions: list[str]


class RiskMetrics(BaseModel):
    var_99_10d: float
    cvar_99_10d: float
    max_drawdown: float
    drawdown_duration: int
    annualised_volatility: float
    observations: int
    skewness: float = 0.0
    excess_kurtosis: float = 0.0
    beta: float | None = None
    liquidity_adjusted_var: float | None = None
    stress_loss: float | None = None


class Scenario(BaseModel):
    name: str
    probability: float = Field(ge=0, le=1)
    assumptions: list[str]
    expected_range: Interval
    triggers: list[str] = Field(default_factory=list)


class AuditBlock(BaseModel):
    model_version: str
    data_sources_used: list[str]
    retrieval_timestamp: datetime
    forecast_start: datetime
    forecast_end: date
    confidence_level: Confidence
    hallucination_risk: Confidence
    human_review_needed: str
    regulatory_flags: list[str]
    limitations: list[str]
    run_id: str = ""
    input_hash: str = ""
    code_version: str = ""


class AnalysisReport(BaseModel):
    executive_summary: str
    forecast: ForecastResult
    risk: RiskMetrics
    scenarios: list[Scenario]
    citations: list[Citation]
    what_would_change_this_view: list[str]
    audit: AuditBlock
    metadata: dict[str, Any] = Field(default_factory=dict)
