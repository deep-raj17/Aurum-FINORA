"""Chronological multi-stage KD/QAT trainer with governed artifacts."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

try:
    import torch
    from torch import Tensor
    from torch.utils.data import DataLoader, Dataset
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install aurum-finora[kdq] to train FINORA-KD-Q") from exc

from .config import KDQConfig, TrainingConfig
from .contracts import KDQBatch
from .losses import distillation_loss
from .model import FINORAStudentModel


class DistillationDataset(Dataset[dict[str, Tensor]]):
    def __init__(self, samples: list[KDQBatch]) -> None:
        self.samples = sorted(samples, key=lambda sample: sample.timestamp)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, Tensor]:
        sample = self.samples[index]
        return {
            "time_series": torch.tensor(sample.time_series, dtype=torch.float32),
            "text_ids": torch.tensor(sample.text_ids, dtype=torch.long),
            "text_mask": torch.tensor(sample.text_mask, dtype=torch.bool),
            "tabular": torch.tensor(sample.tabular, dtype=torch.float32),
            "target_return": torch.tensor(sample.target_return, dtype=torch.float32),
            "target_volatility": torch.tensor(sample.target_volatility, dtype=torch.float32),
            "teacher_forecast": torch.tensor(sample.soft_labels.forecast_mean, dtype=torch.float32),
            "teacher_quantiles": torch.tensor(
                sample.soft_labels.forecast_quantiles, dtype=torch.float32
            ),
            "teacher_sentiment": torch.tensor(
                sample.soft_labels.sentiment_probs, dtype=torch.float32
            ),
            "teacher_risk": torch.tensor(sample.soft_labels.risk_targets, dtype=torch.float32),
            "teacher_reasoning": torch.tensor(
                sample.soft_labels.reasoning_embedding, dtype=torch.float32
            ),
        }


@dataclass
class TrainingResult:
    artifact_dir: Path
    best_validation_loss: float
    epochs_completed: int
    history: list[dict[str, float]]
    model: FINORAStudentModel


def _device(config: TrainingConfig) -> torch.device:
    if config.device != "auto":
        return torch.device(config.device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _move(batch: dict[str, Tensor], device: torch.device) -> dict[str, Tensor]:
    return {name: value.to(device) for name, value in batch.items()}


def _evaluate(
    model: FINORAStudentModel,
    loader: DataLoader[dict[str, Tensor]],
    device: torch.device,
    config: TrainingConfig,
) -> float:
    model.eval()
    losses = []
    with torch.no_grad():
        for raw_batch in loader:
            batch = _move(raw_batch, device)
            outputs = model(
                batch["time_series"],
                batch["text_ids"],
                batch["text_mask"],
                batch["tabular"],
            )
            loss, _ = distillation_loss(
                outputs,
                batch,
                quantiles=model.config.quantiles,
                temperature=config.temperature,
                weights=config.weights,
            )
            losses.append(float(loss.detach().cpu()))
    return float(np.mean(losses)) if losses else float("inf")


def train_student(
    samples: list[KDQBatch],
    model_config: KDQConfig,
    training_config: TrainingConfig,
) -> TrainingResult:
    if len(samples) < 10:
        raise ValueError("at least 10 chronological samples are required")
    random.seed(training_config.seed)
    np.random.seed(training_config.seed)
    torch.manual_seed(training_config.seed)
    ordered = sorted(samples, key=lambda sample: sample.timestamp)
    split = int(len(ordered) * (1 - training_config.validation_fraction))
    if split < 2 or split >= len(ordered):
        raise ValueError("validation split produced an empty partition")
    train_loader = DataLoader(
        DistillationDataset(ordered[:split]),
        batch_size=training_config.batch_size,
        shuffle=False,
        drop_last=split % training_config.batch_size == 1 and split > 1,
    )
    validation_loader = DataLoader(
        DistillationDataset(ordered[split:]),
        batch_size=training_config.batch_size,
        shuffle=False,
    )
    device = _device(training_config)
    model = FINORAStudentModel(model_config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=training_config.learning_rate,
        weight_decay=training_config.weight_decay,
    )
    scaler = torch.amp.GradScaler(
        "cuda", enabled=training_config.mixed_precision and device.type == "cuda"
    )
    history: list[dict[str, float]] = []
    best_loss = float("inf")
    best_state: dict[str, Tensor] | None = None
    stale_epochs = 0
    epochs_completed = 0
    for epoch in range(training_config.epochs):
        model.train()
        training_losses = []
        for raw_batch in train_loader:
            batch = _move(raw_batch, device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(
                device_type=device.type,
                enabled=training_config.mixed_precision and device.type == "cuda",
            ):
                outputs = model(
                    batch["time_series"],
                    batch["text_ids"],
                    batch["text_mask"],
                    batch["tabular"],
                )
                loss, _ = distillation_loss(
                    outputs,
                    batch,
                    quantiles=model_config.quantiles,
                    temperature=training_config.temperature,
                    weights=training_config.weights,
                )
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), training_config.gradient_clip)
            scaler.step(optimizer)
            scaler.update()
            training_losses.append(float(loss.detach().cpu()))
        validation_loss = _evaluate(model, validation_loader, device, training_config)
        history.append(
            {
                "epoch": float(epoch + 1),
                "training_loss": float(np.mean(training_losses)),
                "validation_loss": validation_loss,
            }
        )
        epochs_completed = epoch + 1
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_state = {
                name: value.detach().cpu().clone() for name, value in model.state_dict().items()
            }
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= training_config.early_stopping_patience:
                break
    if best_state is None:
        raise RuntimeError("training did not produce a valid checkpoint")
    model.load_state_dict(best_state)
    model.cpu().eval()
    artifact_dir = save_artifact(
        model,
        model_config,
        training_config,
        history,
        ordered,
        best_loss,
    )
    return TrainingResult(
        artifact_dir=artifact_dir,
        best_validation_loss=best_loss,
        epochs_completed=epochs_completed,
        history=history,
        model=model,
    )


def save_artifact(
    model: FINORAStudentModel,
    model_config: KDQConfig,
    training_config: TrainingConfig,
    history: list[dict[str, float]],
    samples: list[KDQBatch],
    best_loss: float,
) -> Path:
    destination = Path(training_config.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    checkpoint = destination / "student-state.pt"
    torch.save(model.state_dict(), checkpoint)
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    data_hash = hashlib.sha256(
        "\n".join(sample.model_dump_json() for sample in samples).encode()
    ).hexdigest()
    teacher_versions = sorted(
        {
            f"{name}:{version}"
            for sample in samples
            for name, version in sample.soft_labels.teacher_versions.items()
        }
    )
    manifest: dict[str, Any] = {
        "model_name": model_config.model_name,
        "created_at": datetime.now(UTC).isoformat(),
        "model_config": model_config.model_dump(),
        "training_config": training_config.model_dump(),
        "parameter_summary": model.parameter_summary(),
        "best_validation_loss": best_loss,
        "checkpoint_sha256": checkpoint_hash,
        "dataset_sha256": data_hash,
        "teacher_versions": teacher_versions,
        "history": history,
        "deployment_status": "REQUIRES_HUMAN_VALIDATION",
        "limitations": [
            "Teacher quality bounds student quality",
            "Synthetic/offline teacher labels are not suitable for live capital",
            "Calibration must be revalidated by asset class and regime",
        ],
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (destination / "MODEL_CARD.md").write_text(_model_card(manifest), encoding="utf-8")
    return destination


def _model_card(manifest: dict[str, Any]) -> str:
    return f"""# FINORA-KD-Q model card

- Status: **{manifest["deployment_status"]}**
- Parameters: {manifest["parameter_summary"]["parameters"]:,}
- QAT enabled: {manifest["parameter_summary"]["qat_enabled"]}
- Best validation loss: {manifest["best_validation_loss"]:.8f}
- Checkpoint SHA-256: `{manifest["checkpoint_sha256"]}`
- Dataset SHA-256: `{manifest["dataset_sha256"]}`
- Teachers: {", ".join(manifest["teacher_versions"])}

## Intended use

Probabilistic financial research and decision support with retrieved evidence. This
artifact is not approved for autonomous trading or client distribution.

## Required validation

Walk-forward evaluation by asset class and regime, interval calibration, stress tests,
transaction-cost evaluation, bias review, and human model-risk sign-off.
"""
