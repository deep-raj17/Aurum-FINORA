"""Artifact-verified FINORA-KD-Q inference."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

try:
    import torch
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install aurum-finora[kdq] for KD-Q inference") from exc

from .contracts import KDQInferenceRequest, KDQPrediction
from .data import stable_tokenize
from .export import load_artifact


class KDQPredictor:
    def __init__(self, artifact_dir: str | Path) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.manifest = json.loads(
            (self.artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
        checkpoint = self.artifact_dir / "student-state.pt"
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if digest != self.manifest["checkpoint_sha256"]:
            raise ValueError("KD-Q checkpoint hash does not match its manifest")
        self.model = load_artifact(self.artifact_dir)

    def predict(self, request: KDQInferenceRequest) -> KDQPrediction:
        config = self.model.config
        series = np.asarray(request.time_series, dtype=np.float32)
        if series.shape != (config.sequence_length, config.time_features):
            raise ValueError(
                f"time_series must have shape ({config.sequence_length}, {config.time_features})"
            )
        if len(request.tabular) != config.tabular_features:
            raise ValueError(f"tabular must contain {config.tabular_features} features")
        ids, mask = stable_tokenize(request.text, config.vocab_size, config.max_text_length)
        with torch.inference_mode():
            outputs = self.model(
                torch.tensor(series).unsqueeze(0),
                torch.tensor(ids, dtype=torch.long).unsqueeze(0),
                torch.tensor(mask, dtype=torch.bool).unsqueeze(0),
                torch.tensor(request.tabular, dtype=torch.float32).unsqueeze(0),
            )
        sentiment = torch.softmax(outputs["sentiment_logits"], dim=-1)[0].tolist()
        risk = outputs["risk"][0].tolist()
        importance = outputs["modality_importance"][0].tolist()
        return KDQPrediction(
            model_name=config.model_name,
            artifact_sha256=self.manifest["checkpoint_sha256"],
            forecast_mean=float(outputs["forecast_mean"][0]),
            forecast_quantiles=outputs["forecast_quantiles"][0].tolist(),
            volatility=float(outputs["volatility"][0]),
            sentiment_probabilities=sentiment,
            var=risk[0],
            drawdown=risk[1],
            crash_probability=risk[2],
            modality_importance=dict(
                zip(("time_series", "text", "tabular"), importance, strict=True)
            ),
        )
