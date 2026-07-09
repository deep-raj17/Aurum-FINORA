"""Versioned point-in-time feature store with online/offline parity."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class FeatureDefinition(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    version: str
    dtype: str
    owner: str
    description: str
    transformation: str
    dependencies: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)

    @property
    def definition_hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class FeatureValue(BaseModel):
    entity: str
    feature: str
    version: str
    event_timestamp: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    value: float | int | str | bool | None
    source_dataset_sha256: str


class FeatureStatistics(BaseModel):
    feature: str
    version: str
    observations: int = Field(ge=0)
    missing: int = Field(ge=0)
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    standard_deviation: float | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PointInTimeFeatureStore:
    """SQLite reference implementation; writes are serialized and reads are thread-safe."""

    def __init__(self, path: str | Path = "data/features.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = RLock()
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS feature_definitions(
                    name TEXT NOT NULL, version TEXT NOT NULL, definition_hash TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(name, version)
                );
                CREATE TABLE IF NOT EXISTS feature_values(
                    entity TEXT NOT NULL, feature TEXT NOT NULL, version TEXT NOT NULL,
                    event_timestamp TEXT NOT NULL, created_at TEXT NOT NULL,
                    value TEXT NOT NULL, source_dataset_sha256 TEXT NOT NULL,
                    PRIMARY KEY(entity, feature, version, event_timestamp)
                );
                CREATE INDEX IF NOT EXISTS ix_feature_point_in_time
                ON feature_values(entity, feature, version, event_timestamp DESC);
                """
            )

    def register(self, definition: FeatureDefinition) -> None:
        payload = definition.model_dump_json()
        with self.lock, self.connection:
            existing = self.connection.execute(
                "SELECT definition_hash FROM feature_definitions WHERE name=? AND version=?",
                (definition.name, definition.version),
            ).fetchone()
            if existing and existing["definition_hash"] != definition.definition_hash:
                raise ValueError("feature definition version is immutable")
            self.connection.execute(
                "INSERT OR IGNORE INTO feature_definitions VALUES(?,?,?,?)",
                (
                    definition.name,
                    definition.version,
                    definition.definition_hash,
                    payload,
                ),
            )

    def write(self, values: list[FeatureValue]) -> None:
        with self.lock, self.connection:
            for value in values:
                registered = self.connection.execute(
                    "SELECT 1 FROM feature_definitions WHERE name=? AND version=?",
                    (value.feature, value.version),
                ).fetchone()
                if not registered:
                    raise ValueError(f"unregistered feature {value.feature}:{value.version}")
                self.connection.execute(
                    "INSERT OR REPLACE INTO feature_values VALUES(?,?,?,?,?,?,?)",
                    (
                        value.entity,
                        value.feature,
                        value.version,
                        value.event_timestamp.astimezone(UTC).isoformat(),
                        value.created_at.astimezone(UTC).isoformat(),
                        json.dumps(value.value),
                        value.source_dataset_sha256,
                    ),
                )

    def point_in_time(
        self,
        entities: list[str],
        features: list[tuple[str, str]],
        as_of: datetime,
    ) -> dict[str, dict[str, Any]]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        result: dict[str, dict[str, Any]] = {entity: {} for entity in entities}
        for entity in entities:
            for feature, version in features:
                row = self.connection.execute(
                    """
                    SELECT value,event_timestamp,source_dataset_sha256
                    FROM feature_values
                    WHERE entity=? AND feature=? AND version=? AND event_timestamp<=?
                    ORDER BY event_timestamp DESC LIMIT 1
                    """,
                    (entity, feature, version, as_of.astimezone(UTC).isoformat()),
                ).fetchone()
                if row:
                    result[entity][feature] = {
                        "value": json.loads(row["value"]),
                        "version": version,
                        "event_timestamp": row["event_timestamp"],
                        "source_dataset_sha256": row["source_dataset_sha256"],
                    }
        return result

    def online_get(
        self, entity: str, feature: str, version: str, as_of: datetime | None = None
    ) -> Any:
        values = self.point_in_time([entity], [(feature, version)], as_of or datetime.now(UTC))
        row = values[entity].get(feature)
        return row["value"] if row else None

    def offline_range(
        self,
        entity: str,
        feature: str,
        version: str,
        start: datetime,
        end: datetime,
    ) -> list[FeatureValue]:
        if start.tzinfo is None or end.tzinfo is None or start > end:
            raise ValueError("offline range requires ordered timezone-aware boundaries")
        rows = self.connection.execute(
            """
            SELECT entity,feature,version,event_timestamp,created_at,value,
                   source_dataset_sha256
            FROM feature_values
            WHERE entity=? AND feature=? AND version=?
              AND event_timestamp>=? AND event_timestamp<=?
            ORDER BY event_timestamp
            """,
            (
                entity,
                feature,
                version,
                start.astimezone(UTC).isoformat(),
                end.astimezone(UTC).isoformat(),
            ),
        ).fetchall()
        return [
            FeatureValue(
                entity=row["entity"],
                feature=row["feature"],
                version=row["version"],
                event_timestamp=datetime.fromisoformat(row["event_timestamp"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                value=json.loads(row["value"]),
                source_dataset_sha256=row["source_dataset_sha256"],
            )
            for row in rows
        ]

    def statistics(self, feature: str, version: str) -> FeatureStatistics:
        rows = self.connection.execute(
            "SELECT value FROM feature_values WHERE feature=? AND version=?",
            (feature, version),
        ).fetchall()
        decoded = [json.loads(row["value"]) for row in rows]
        numeric = np.asarray(
            [
                float(value)
                for value in decoded
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ],
            dtype=float,
        )
        return FeatureStatistics(
            feature=feature,
            version=version,
            observations=len(decoded),
            missing=sum(value is None for value in decoded),
            minimum=float(numeric.min()) if len(numeric) else None,
            maximum=float(numeric.max()) if len(numeric) else None,
            mean=float(numeric.mean()) if len(numeric) else None,
            standard_deviation=float(numeric.std(ddof=1)) if len(numeric) > 1 else None,
        )

    def recompute(
        self,
        definition: FeatureDefinition,
        entities: list[str],
        timestamps: list[datetime],
        transformation: Callable[[str, datetime], tuple[Any, str]],
    ) -> int:
        """Recompute a registered version; callback returns value and source hash."""
        self.register(definition)
        values: list[FeatureValue] = []
        for entity in entities:
            for timestamp in timestamps:
                if timestamp.tzinfo is None:
                    raise ValueError("recomputation timestamps must be timezone-aware")
                value, source_hash = transformation(entity, timestamp)
                values.append(
                    FeatureValue(
                        entity=entity,
                        feature=definition.name,
                        version=definition.version,
                        event_timestamp=timestamp,
                        value=value,
                        source_dataset_sha256=source_hash,
                    )
                )
        self.write(values)
        return len(values)

    def assert_training_serving_consistency(
        self,
        entity: str,
        feature: str,
        version: str,
        as_of: datetime,
        training_value: Any,
    ) -> None:
        serving_value = self.online_get(entity, feature, version, as_of)
        if serving_value != training_value:
            raise RuntimeError(
                f"training-serving skew for {entity}/{feature}:{version}: "
                f"{training_value!r} != {serving_value!r}"
            )
