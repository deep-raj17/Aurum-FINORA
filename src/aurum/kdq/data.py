"""Chronological KD datasets, stable tokenization, and soft-label serialization."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from .config import KDQConfig
from .contracts import KDQBatch
from .teachers import TeacherEnsemble, TeacherInput


def stable_tokenize(text: str, vocab_size: int, max_length: int) -> tuple[list[int], list[int]]:
    token_ids = []
    for token in text.lower().split()[:max_length]:
        digest = hashlib.sha256(token.encode()).digest()
        token_ids.append(2 + int.from_bytes(digest[:4], "big") % (vocab_size - 2))
    mask = [1] * len(token_ids)
    padding = max_length - len(token_ids)
    return token_ids + [0] * padding, mask + [0] * padding


def build_distilled_sample(
    raw: TeacherInput,
    *,
    target_return: float,
    target_volatility: float,
    ensemble: TeacherEnsemble,
    config: KDQConfig,
) -> KDQBatch:
    if len(raw.time_series) != config.sequence_length:
        raise ValueError(f"time-series length {len(raw.time_series)} != {config.sequence_length}")
    if len(raw.time_series[0]) != config.time_features:
        raise ValueError("time feature width does not match model configuration")
    if len(raw.tabular) != config.tabular_features:
        raise ValueError("tabular feature width does not match model configuration")
    ids, mask = stable_tokenize(raw.text, config.vocab_size, config.max_text_length)
    return KDQBatch(
        sample_id=raw.sample_id,
        timestamp=raw.timestamp,
        time_series=raw.time_series,
        text_ids=ids,
        text_mask=mask,
        tabular=raw.tabular,
        target_return=target_return,
        target_volatility=target_volatility,
        soft_labels=ensemble.generate(raw),
        evidence_ids=[
            hashlib.sha256(evidence.encode()).hexdigest()[:16] for evidence in raw.evidence
        ],
    )


def write_jsonl(samples: Iterable[KDQBatch], path: str | Path) -> str:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with destination.open("w", encoding="utf-8") as handle:
        for sample in sorted(samples, key=lambda item: item.timestamp):
            line = sample.model_dump_json()
            handle.write(line + "\n")
            digest.update((line + "\n").encode())
    return digest.hexdigest()


def read_jsonl(path: str | Path) -> list[KDQBatch]:
    with Path(path).open(encoding="utf-8") as handle:
        samples = [KDQBatch.model_validate_json(line) for line in handle if line.strip()]
    if samples != sorted(samples, key=lambda item: item.timestamp):
        raise ValueError("KD dataset must be chronologically sorted")
    return samples


def synthetic_teacher_inputs(
    config: KDQConfig, count: int = 96, seed: int = 42
) -> list[tuple[TeacherInput, float, float]]:
    rng = np.random.default_rng(seed)
    results = []
    for index in range(count):
        returns = rng.normal(0.0002, 0.01, config.sequence_length + 1)
        levels = 100 * np.exp(np.cumsum(returns))
        time_features = np.column_stack(
            (
                levels[:-1],
                returns[:-1],
                np.abs(returns[:-1]),
                np.sin(np.arange(config.sequence_length) / 5),
                np.cos(np.arange(config.sequence_length) / 5),
                np.full(config.sequence_length, index / max(count, 1)),
            )
        )[:, : config.time_features]
        if time_features.shape[1] < config.time_features:
            time_features = np.pad(
                time_features,
                ((0, 0), (0, config.time_features - time_features.shape[1])),
            )
        tabular = rng.normal(size=config.tabular_features).tolist()
        text = "strong profit growth" if index % 3 == 0 else "neutral financial update"
        raw = TeacherInput(
            sample_id=f"synthetic-{index:05d}",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=index),
            time_series=time_features.tolist(),
            text=text,
            tabular=tabular,
            evidence=[f"synthetic evidence {index}"],
        )
        results.append((raw, float(returns[-1]), float(np.std(returns[-10:]))))
    return results
