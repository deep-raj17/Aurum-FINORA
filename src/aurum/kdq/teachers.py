"""Pluggable production teachers and explicitly opt-in offline baselines."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

import numpy as np
from pydantic import BaseModel, Field

from aurum.sentiment import FinBERTSentimentAnalyzer, analyse_sentiment

from .contracts import SoftLabels


class TeacherInput(BaseModel):
    sample_id: str
    timestamp: datetime
    time_series: list[list[float]]
    text: str
    tabular: list[float]
    evidence: list[str] = Field(default_factory=list)


class ForecastTeacher(Protocol):
    version: str

    def predict(self, sample: TeacherInput) -> dict[str, Any]: ...


class SentimentTeacher(Protocol):
    version: str

    def predict(self, sample: TeacherInput) -> list[float]: ...


class RiskTeacher(Protocol):
    version: str

    def predict(self, sample: TeacherInput) -> list[float]: ...


class ReasoningTeacher(Protocol):
    version: str

    def embed(self, sample: TeacherInput, dimensions: int) -> list[float]: ...


def _stable_embedding(text: str, dimensions: int) -> list[float]:
    vector = np.zeros(dimensions, dtype=float)
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1 if digest[4] % 2 else -1
    norm = float(np.linalg.norm(vector)) or 1.0
    return (vector / norm).tolist()


class StatisticalForecastTeacher:
    """Offline replacement for Chronos/PatchTST/TFT in smoke and CI workflows."""

    version = "statistical-ensemble-surrogate-v1"

    def predict(self, sample: TeacherInput) -> dict[str, Any]:
        levels = np.asarray(sample.time_series, dtype=float)[:, 0]
        returns = np.diff(levels) / np.maximum(np.abs(levels[:-1]), 1e-12)
        recent = returns[-min(20, len(returns)) :]
        mean = float(np.mean(recent))
        sigma = float(np.std(recent, ddof=1)) if len(recent) > 1 else 0.0
        return {
            "mean": mean,
            "quantiles": [mean - 1.2816 * sigma, mean, mean + 1.2816 * sigma],
            "volatility": sigma,
        }


class LexicalSentimentTeacher:
    version = "auditable-finance-lexicon-v1"

    def predict(self, sample: TeacherInput) -> list[float]:
        result = analyse_sentiment(sample.text)
        residual = (1 - result.probability) / 2
        if result.label == "Positive":
            return [residual, residual, result.probability]
        if result.label == "Negative":
            return [result.probability, residual, residual]
        return [0.2, 0.6, 0.2]


class HistoricalRiskTeacher:
    version = "historical-risk-surrogate-v1"

    def predict(self, sample: TeacherInput) -> list[float]:
        levels = np.asarray(sample.time_series, dtype=float)[:, 0]
        returns = np.diff(levels) / np.maximum(np.abs(levels[:-1]), 1e-12)
        var = max(0.0, -float(np.quantile(returns, 0.05)))
        running_max = np.maximum.accumulate(levels)
        drawdown = max(0.0, -float(np.min(levels / running_max - 1)))
        crash_probability = float(np.mean(returns < -0.03))
        return [var, drawdown, crash_probability]


class HashedReasoningTeacher:
    version = "grounded-hashed-reasoning-v1"

    def embed(self, sample: TeacherInput, dimensions: int) -> list[float]:
        context = " ".join([sample.text, *sample.evidence])
        return _stable_embedding(context, dimensions)


class TeacherEnsemble:
    def __init__(
        self,
        forecast: ForecastTeacher | None = None,
        sentiment: SentimentTeacher | None = None,
        risk: RiskTeacher | None = None,
        reasoning: ReasoningTeacher | None = None,
        reasoning_size: int = 64,
        allow_offline_baselines: bool = False,
    ) -> None:
        missing = [
            name
            for name, teacher in {
                "forecast": forecast,
                "sentiment": sentiment,
                "risk": risk,
                "reasoning": reasoning,
            }.items()
            if teacher is None
        ]
        if missing and not allow_offline_baselines:
            raise ValueError(
                "production teacher ensemble requires explicit teachers: " + ", ".join(missing)
            )
        self.forecast = forecast or StatisticalForecastTeacher()
        self.sentiment = sentiment or LexicalSentimentTeacher()
        self.risk = risk or HistoricalRiskTeacher()
        self.reasoning = reasoning or HashedReasoningTeacher()
        self.reasoning_size = reasoning_size

    def generate(self, sample: TeacherInput) -> SoftLabels:
        forecast = self.forecast.predict(sample)
        return SoftLabels(
            forecast_mean=float(forecast["mean"]),
            forecast_quantiles=list(forecast["quantiles"]),
            volatility=float(forecast["volatility"]),
            sentiment_probs=self.sentiment.predict(sample),
            risk_targets=self.risk.predict(sample),
            reasoning_embedding=self.reasoning.embed(sample, self.reasoning_size),
            retrieval_embedding=_stable_embedding(" ".join(sample.evidence), self.reasoning_size),
            teacher_versions={
                "forecast": self.forecast.version,
                "sentiment": self.sentiment.version,
                "risk": self.risk.version,
                "reasoning": self.reasoning.version,
            },
            generated_at=datetime.now(UTC),
        )


class CallableTeacher:
    """Adapter for Chronos, FinBERT, XGBoost, BGE or an LLM inference callable."""

    def __init__(self, function: Any, version: str) -> None:
        self.function = function
        self.version = version

    def predict(self, sample: TeacherInput) -> Any:
        return self.function(sample)

    def embed(self, sample: TeacherInput, dimensions: int) -> list[float]:
        values = list(self.function(sample))
        if len(values) != dimensions:
            raise ValueError(
                f"teacher embedding has {len(values)} dimensions; expected {dimensions}"
            )
        return values


class ForecastEnsembleTeacher:
    """Adapts ProductionForecastEngine to the KD forecast teacher contract."""

    def __init__(self, engine: Any, version: str) -> None:
        self.engine = engine
        self.version = version

    def predict(self, sample: TeacherInput) -> dict[str, Any]:
        levels = np.asarray(sample.time_series, dtype=float)[:, 0]
        dates: list[date] = [
            (sample.timestamp - timedelta(days=len(levels) - index)).date()
            for index in range(len(levels))
        ]
        distribution, scores = self.engine.forecast(levels, dates, 1)
        quantiles = [float(distribution.quantiles[level][0]) for level in (0.1, 0.5, 0.9)]
        residual_scale = min((score.rmse for score in scores), default=0.0)
        return {
            "mean": float(distribution.mean[0]),
            "quantiles": quantiles,
            "volatility": max(0.0, float(residual_scale)),
        }


class FINORAMoETeacher:
    """Adapts an audited FINORA-MoE predictor to the KD-Q forecast contract.

    The predictor may expose ``predict_teacher`` or be directly callable. GPT-OSS
    is intentionally not accepted here; it remains a separate reasoning teacher.
    """

    def __init__(self, predictor: Any, version: str) -> None:
        self.predictor = predictor
        self.version = version

    def predict(self, sample: TeacherInput) -> dict[str, Any]:
        function = getattr(self.predictor, "predict_teacher", self.predictor)
        output = function(sample)
        required = {"mean", "quantiles", "volatility"}
        if not isinstance(output, dict) or not required.issubset(output):
            raise RuntimeError("FINORA-MoE teacher omitted forecast distillation outputs")
        quantiles = np.asarray(output["quantiles"], dtype=float)
        if quantiles.shape != (3,) or np.any(~np.isfinite(quantiles)):
            raise RuntimeError("FINORA-MoE teacher must return three finite quantiles")
        if np.any(np.diff(quantiles) < 0):
            raise RuntimeError("FINORA-MoE teacher quantiles must be ordered")
        mean = float(output["mean"])
        volatility = float(output["volatility"])
        if not np.isfinite(mean) or not np.isfinite(volatility) or volatility < 0:
            raise RuntimeError("FINORA-MoE teacher returned invalid forecast values")
        return {
            "mean": mean,
            "quantiles": quantiles.tolist(),
            "volatility": volatility,
        }


class FinBERTTeacher:
    version = "ProsusAI/finbert"

    def __init__(self, analyzer: FinBERTSentimentAnalyzer | None = None) -> None:
        self.analyzer = analyzer or FinBERTSentimentAnalyzer(self.version)

    def predict(self, sample: TeacherInput) -> list[float]:
        result = self.analyzer.analyse(sample.text)
        residual = max(0.0, 1 - result.probability)
        probabilities = {
            "Negative": [result.probability, residual / 2, residual / 2],
            "Neutral": [residual / 2, result.probability, residual / 2],
            "Positive": [residual / 2, residual / 2, result.probability],
        }
        return probabilities[result.label]


class TrainedRiskTeacher:
    """Adapts a fitted multi-output risk estimator; it never trains on inference data."""

    def __init__(self, estimator: Any, version: str) -> None:
        self.estimator = estimator
        self.version = version

    def predict(self, sample: TeacherInput) -> list[float]:
        values = np.asarray(
            self.estimator.predict(np.asarray(sample.tabular, dtype=float)[None, :])[0],
            dtype=float,
        )
        if values.shape != (3,) or not np.all(np.isfinite(values)):
            raise RuntimeError("risk teacher must return finite VaR, drawdown, crash probability")
        values[:2] = np.maximum(values[:2], 0)
        values[2] = np.clip(values[2], 0, 1)
        return values.tolist()


class GPTOSSFeatureTeacher:
    """Adapts audited GPT-OSS hidden-state extraction to the reasoning contract."""

    def __init__(self, extractor: Any, version: str = "openai/gpt-oss-20b") -> None:
        self.extractor = extractor
        self.version = version

    def embed(self, sample: TeacherInput, dimensions: int) -> list[float]:
        values = np.asarray(
            self.extractor(
                text=sample.text,
                evidence=sample.evidence,
                dimensions=dimensions,
            ),
            dtype=float,
        )
        if values.shape != (dimensions,) or not np.all(np.isfinite(values)):
            raise RuntimeError(f"GPT-OSS feature extractor must return {dimensions} finite values")
        norm = float(np.linalg.norm(values))
        if norm == 0:
            raise RuntimeError("GPT-OSS feature extractor returned a zero vector")
        return (values / norm).tolist()
