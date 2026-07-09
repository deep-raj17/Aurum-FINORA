"""Typed configuration for FINORA-KD-Q training and deployment."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class KDQConfig(BaseModel):
    model_name: str = "FINORA-KD-Q"
    time_features: int = Field(default=6, ge=1)
    tabular_features: int = Field(default=24, ge=1)
    vocab_size: int = Field(default=30_000, ge=128)
    max_text_length: int = Field(default=128, ge=8)
    sequence_length: int = Field(default=64, ge=8)
    patch_size: int = Field(default=8, ge=2)
    hidden_size: int = Field(default=128, ge=32)
    reasoning_size: int = Field(default=64, ge=16)
    attention_heads: int = Field(default=4, ge=1)
    encoder_layers: int = Field(default=2, ge=1)
    dropout: float = Field(default=0.1, ge=0, lt=1)
    sentiment_classes: int = 3
    quantiles: list[float] = Field(default_factory=lambda: [0.1, 0.5, 0.9])
    qat_enabled: bool = True

    @model_validator(mode="after")
    def compatible_dimensions(self) -> KDQConfig:
        if self.hidden_size % self.attention_heads:
            raise ValueError("hidden_size must be divisible by attention_heads")
        if self.sequence_length < self.patch_size:
            raise ValueError("sequence_length must be at least patch_size")
        if self.quantiles != sorted(self.quantiles):
            raise ValueError("quantiles must be sorted")
        return self


class LossWeights(BaseModel):
    forecast: float = 1.0
    forecast_distillation: float = 0.7
    quantile_distillation: float = 0.3
    sentiment_distillation: float = 0.5
    risk_distillation: float = 0.5
    uncertainty: float = 0.3
    volatility: float = 0.2
    calibration: float = 0.2
    reasoning: float = 0.1


class TrainingConfig(BaseModel):
    epochs: int = Field(default=10, ge=1)
    batch_size: int = Field(default=32, ge=1)
    learning_rate: float = Field(default=3e-4, gt=0)
    weight_decay: float = Field(default=1e-4, ge=0)
    gradient_clip: float = Field(default=1.0, gt=0)
    validation_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    early_stopping_patience: int = Field(default=3, ge=1)
    temperature: float = Field(default=2.0, gt=0)
    seed: int = 42
    device: str = "auto"
    mixed_precision: bool = True
    output_dir: str = "artifacts/finora-kdq"
    weights: LossWeights = Field(default_factory=LossWeights)
