"""Auditable lexical fallback for finance-text sentiment."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from importlib import import_module
from typing import Any

from pydantic import BaseModel, Field

POSITIVE = {"beat", "growth", "raised", "improved", "strong", "profit", "upgrade"}
NEGATIVE = {"miss", "decline", "lowered", "weak", "loss", "downgrade", "default"}


class SentimentResult(BaseModel):
    label: str
    probability: float = Field(ge=0, le=1)
    positive_hits: list[str]
    negative_hits: list[str]
    model: str = "auditable-finance-lexicon-v1"


class TextObservation(BaseModel):
    entity: str
    timestamp: datetime
    text: str
    source_type: str


class SentimentMomentum(BaseModel):
    entity: str
    one_day: float
    five_day: float
    twenty_day: float
    observations: int


class FilingComparison(BaseModel):
    current: SentimentResult
    prior: SentimentResult
    new_risk_terms: list[str]
    tone_divergence: bool


def analyse_sentiment(text: str) -> SentimentResult:
    """Auditable dependency-free fallback; production uses FinBERTSentimentAnalyzer."""
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    positive = sorted(tokens & POSITIVE)
    negative = sorted(tokens & NEGATIVE)
    net = len(positive) - len(negative)
    label = "Positive" if net > 0 else "Negative" if net < 0 else "Neutral"
    evidence = len(positive) + len(negative)
    probability = 0.5 if evidence == 0 else min(0.95, 0.55 + 0.1 * abs(net))
    return SentimentResult(
        label=label,
        probability=probability,
        positive_hits=positive,
        negative_hits=negative,
    )


class FinBERTSentimentAnalyzer:
    """ProsusAI FinBERT-compatible transformer sentiment inference.

    Supports batch inference, GPU/CPU fallback, and confidence scores.
    For RTX 4070 12GB VRAM, uses automatic device detection with CPU fallback.
    """

    def __init__(
        self,
        model_id: str = "ProsusAI/finbert",
        *,
        pipeline: Any | None = None,
        device: str | int = "auto",
        cache_dir: str | None = None,
        batch_size: int = 8,
    ) -> None:
        self.model_id = model_id
        self._pipeline = pipeline
        self.device = device
        self._cache_dir = cache_dir
        self.batch_size = batch_size

    def _detect_device(self) -> str | int:
        """Auto-detect GPU availability with CPU fallback."""
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return -1  # CPU

    def _load(self) -> Any:
        if self._pipeline is None:
            transformers = import_module("transformers")
            device = self._detect_device() if self.device == "auto" else self.device
            kwargs = {
                "task": "text-classification",
                "device": device,
                "top_k": None,
                "truncation": True,
            }
            if self._cache_dir:
                kwargs["model"] = transformers.AutoModelForSequenceClassification.from_pretrained(
                    self.model_id, cache_dir=self._cache_dir
                )
                kwargs["tokenizer"] = transformers.AutoTokenizer.from_pretrained(
                    self.model_id, cache_dir=self._cache_dir
                )
            else:
                kwargs["model"] = self.model_id
                kwargs["tokenizer"] = self.model_id
            self._pipeline = transformers.pipeline(**kwargs)
        return self._pipeline

    def analyse(self, text: str) -> SentimentResult:
        """Analyze single text for sentiment."""
        if not text.strip():
            raise ValueError("sentiment text cannot be empty")
        raw = self._load()(text, truncation=True)
        if raw and isinstance(raw[0], list):
            raw = raw[0]
        probabilities = {str(item["label"]).lower(): float(item["score"]) for item in raw}
        label_aliases = {
            "label_0": "positive",
            "label_1": "negative",
            "label_2": "neutral",
        }
        normalized = {
            label_aliases.get(label, label): score for label, score in probabilities.items()
        }
        if not {"positive", "negative", "neutral"} <= normalized.keys():
            raise RuntimeError("FinBERT output omitted required sentiment labels")
        winner = max(("positive", "negative", "neutral"), key=normalized.__getitem__)
        return SentimentResult(
            label=winner.title(),
            probability=normalized[winner],
            positive_hits=[],
            negative_hits=[],
            model=self.model_id,
        )

    def analyse_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Analyze multiple texts in batch for efficiency."""
        if not texts:
            return []
        cleaned = [text for text in texts if text.strip()]
        if not cleaned:
            raise ValueError("no non-empty texts provided for batch analysis")
        raw = self._load()(cleaned, truncation=True, batch_size=self.batch_size)
        results = []
        for item in raw:
            distribution = item
            if isinstance(item, dict):
                distribution = [item]
            elif item and isinstance(item[0], list):
                distribution = item[0]
            probabilities = {str(sub["label"]).lower(): float(sub["score"]) for sub in distribution}
            label_aliases = {
                "label_0": "positive",
                "label_1": "negative",
                "label_2": "neutral",
            }
            normalized = {
                label_aliases.get(label, label): score for label, score in probabilities.items()
            }
            if not {"positive", "negative", "neutral"} <= normalized.keys():
                raise RuntimeError("FinBERT output omitted required sentiment labels")
            winner = max(("positive", "negative", "neutral"), key=normalized.__getitem__)
            results.append(
                SentimentResult(
                    label=winner.title(),
                    probability=normalized[winner],
                    positive_hits=[],
                    negative_hits=[],
                    model=self.model_id,
                )
            )
        return results


def aggregate_sentiment(
    observations: list[TextObservation], as_of: datetime
) -> list[SentimentMomentum]:
    by_entity: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for observation in observations:
        if observation.timestamp > as_of:
            continue
        result = analyse_sentiment(observation.text)
        score = (
            result.probability
            if result.label == "Positive"
            else -result.probability
            if result.label == "Negative"
            else 0.0
        )
        by_entity[observation.entity].append((observation.timestamp, score))

    def window_mean(rows: list[tuple[datetime, float]], days: int) -> float:
        scores = [
            score
            for timestamp, score in rows
            if (as_of - timestamp).total_seconds() <= days * 86400
        ]
        return sum(scores) / len(scores) if scores else 0.0

    return [
        SentimentMomentum(
            entity=entity,
            one_day=window_mean(rows, 1),
            five_day=window_mean(rows, 5),
            twenty_day=window_mean(rows, 20),
            observations=len(rows),
        )
        for entity, rows in sorted(by_entity.items())
    ]


def compare_filings(current_text: str, prior_text: str) -> FilingComparison:
    current = analyse_sentiment(current_text)
    prior = analyse_sentiment(prior_text)
    risk_pattern = re.compile(r"\b(risk|uncertain|litigation|impairment|default|shortage)\w*\b")
    current_risks = set(risk_pattern.findall(current_text.lower()))
    prior_risks = set(risk_pattern.findall(prior_text.lower()))
    return FilingComparison(
        current=current,
        prior=prior,
        new_risk_terms=sorted(current_risks - prior_risks),
        tone_divergence=current.label != prior.label,
    )
