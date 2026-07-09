"""Immutable, content-addressed financial data lake with transformation lineage."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class LakeLayer(StrEnum):
    RAW = "raw"
    VALIDATED = "validated"
    NORMALIZED = "normalized"
    CLEANED = "cleaned"
    FEATURE_STORE = "feature_store"
    TRAINING_DATASET = "training_dataset"
    MODEL_INPUT = "model_input"
    INFERENCE_CACHE = "inference_cache"
    ANALYTICS_STORE = "analytics_store"


class QualityMetrics(BaseModel):
    row_count: int = Field(ge=0)
    missing_values: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    schema_valid: bool
    chronological: bool | None = None
    quality_score: float = Field(ge=0, le=1)


class DatasetManifest(BaseModel):
    dataset_id: str
    version: str
    layer: LakeLayer
    source: str
    created_at: datetime
    content_sha256: str
    byte_count: int = Field(ge=0)
    parent_sha256: str | None = None
    transformation: str | None = None
    transformation_version: str | None = None
    configuration_sha256: str | None = None
    quality: QualityMetrics
    metadata: dict[str, Any] = Field(default_factory=dict)


class LocalDataLake:
    """Thread-safe through atomic replacement; raw objects are never overwritten."""

    def __init__(self, root: str | Path = "data/lake") -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_identifier(value: str) -> str:
        if not value or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._"
            for character in value
        ):
            raise ValueError(f"unsafe dataset identifier: {value!r}")
        return value

    def write_raw(
        self,
        dataset_id: str,
        payload: bytes,
        *,
        source: str,
        quality: QualityMetrics,
        metadata: dict[str, Any] | None = None,
    ) -> DatasetManifest:
        return self._write(
            self._safe_identifier(dataset_id),
            LakeLayer.RAW,
            payload,
            source=source,
            quality=quality,
            metadata=metadata or {},
        )

    def write_derived(
        self,
        dataset_id: str,
        layer: LakeLayer,
        payload: bytes,
        *,
        parent: DatasetManifest,
        transformation: str,
        transformation_version: str,
        configuration: dict[str, Any],
        quality: QualityMetrics,
    ) -> DatasetManifest:
        if layer is LakeLayer.RAW:
            raise ValueError("derived datasets cannot target the raw layer")
        configuration_bytes = json.dumps(
            configuration, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        return self._write(
            self._safe_identifier(dataset_id),
            layer,
            payload,
            source=parent.source,
            quality=quality,
            parent_sha256=parent.content_sha256,
            transformation=transformation,
            transformation_version=transformation_version,
            configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
            metadata={"parent_version": parent.version},
        )

    def _write(
        self,
        dataset_id: str,
        layer: LakeLayer,
        payload: bytes,
        **manifest_fields: Any,
    ) -> DatasetManifest:
        digest = hashlib.sha256(payload).hexdigest()
        version = digest[:16]
        directory = self.root / layer.value / dataset_id / version
        data_path = directory / "data.bin"
        manifest_path = directory / "manifest.json"
        if data_path.exists():
            existing = self.load_manifest(layer, dataset_id, version)
            if data_path.read_bytes() != payload:
                raise RuntimeError("content-address collision detected")
            return existing
        directory.mkdir(parents=True, exist_ok=True)
        manifest = DatasetManifest(
            dataset_id=dataset_id,
            version=version,
            layer=layer,
            created_at=datetime.now(UTC),
            content_sha256=digest,
            byte_count=len(payload),
            **manifest_fields,
        )
        self._atomic_write(data_path, payload)
        self._atomic_write(
            manifest_path,
            manifest.model_dump_json(indent=2).encode(),
        )
        return manifest

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def load_manifest(self, layer: LakeLayer, dataset_id: str, version: str) -> DatasetManifest:
        path = (
            self.root
            / layer.value
            / self._safe_identifier(dataset_id)
            / self._safe_identifier(version)
            / "manifest.json"
        )
        return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def read(self, manifest: DatasetManifest) -> bytes:
        path = (
            self.root / manifest.layer.value / manifest.dataset_id / manifest.version / "data.bin"
        )
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != manifest.content_sha256:
            raise RuntimeError("dataset integrity verification failed")
        return payload
