"""Serializable batch and teacher-output contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, model_validator


class SoftLabels(BaseModel):
    forecast_mean: float
    forecast_quantiles: list[float] = Field(min_length=3)
    volatility: float = Field(ge=0)
    sentiment_probs: list[float] = Field(min_length=3)
    risk_targets: list[float] = Field(min_length=3)
    reasoning_embedding: list[float]
    retrieval_embedding: list[float] = Field(default_factory=list)
    teacher_versions: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def probabilities_and_quantiles(self) -> SoftLabels:
        if abs(sum(self.sentiment_probs) - 1) > 1e-4:
            raise ValueError("sentiment probabilities must sum to one")
        if self.forecast_quantiles != sorted(self.forecast_quantiles):
            raise ValueError("forecast quantiles must be ordered")
        return self


class KDQBatch(BaseModel):
    sample_id: str
    timestamp: datetime
    time_series: list[list[float]]
    text_ids: list[int]
    text_mask: list[int]
    tabular: list[float]
    target_return: float
    target_volatility: float = Field(ge=0)
    soft_labels: SoftLabels
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def aligned(self) -> KDQBatch:
        if len(self.text_ids) != len(self.text_mask):
            raise ValueError("text_ids and text_mask must align")
        if not self.time_series or not self.time_series[0]:
            raise ValueError("time_series cannot be empty")
        width = len(self.time_series[0])
        if any(len(row) != width for row in self.time_series):
            raise ValueError("time_series rows must have equal width")
        return self


class KDQInferenceRequest(BaseModel):
    time_series: list[list[float]]
    text: str
    tabular: list[float]
    evidence_ids: list[str] = Field(default_factory=list)


class KDQPrediction(BaseModel):
    model_name: str
    artifact_sha256: str
    forecast_mean: float
    forecast_quantiles: list[float]
    volatility: float
    sentiment_probabilities: list[float]
    var: float
    drawdown: float
    crash_probability: float
    modality_importance: dict[str, float]
    human_review_required: bool = True
