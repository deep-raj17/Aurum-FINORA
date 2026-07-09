"""Parallel, checkpointed connector synchronization into the immutable data lake."""

from __future__ import annotations

import gzip
import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel, Field

from .connectors import MarketConnector
from .contracts import SyncRequest, SyncResult
from .lake import LocalDataLake, QualityMetrics
from .quality import MarketDataQualityEngine, MarketDataQualityReport

logger = logging.getLogger(__name__)


class SyncCheckpoint(BaseModel):
    source: str
    symbol: str
    interval: str
    last_timestamp: datetime | None = None
    status: str
    attempts: int = Field(ge=0)
    error: str | None = None
    updated_at: datetime


class SynchronizationResult(BaseModel):
    source: str
    symbol: str
    records: int
    dataset_version: str
    checkpoint: str | None
    quality: MarketDataQualityReport


class CheckpointStore:
    def __init__(self, path: str | Path = "data/sync-checkpoints.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = RLock()
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_checkpoints(
                    source TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
                    last_timestamp TEXT, status TEXT NOT NULL, attempts INTEGER NOT NULL,
                    error TEXT, updated_at TEXT NOT NULL,
                    PRIMARY KEY(source,symbol,interval)
                )
                """
            )

    def get(self, source: str, symbol: str, interval: str) -> SyncCheckpoint | None:
        row = self.connection.execute(
            "SELECT * FROM sync_checkpoints WHERE source=? AND symbol=? AND interval=?",
            (source, symbol, interval),
        ).fetchone()
        return (
            SyncCheckpoint(
                **{
                    **dict(row),
                    "last_timestamp": datetime.fromisoformat(row["last_timestamp"])
                    if row["last_timestamp"]
                    else None,
                    "updated_at": datetime.fromisoformat(row["updated_at"]),
                }
            )
            if row
            else None
        )

    def save(self, checkpoint: SyncCheckpoint) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO sync_checkpoints VALUES(?,?,?,?,?,?,?,?)",
                (
                    checkpoint.source,
                    checkpoint.symbol,
                    checkpoint.interval,
                    checkpoint.last_timestamp.isoformat() if checkpoint.last_timestamp else None,
                    checkpoint.status,
                    checkpoint.attempts,
                    checkpoint.error,
                    checkpoint.updated_at.isoformat(),
                ),
            )


class DataSynchronizer:
    def __init__(
        self,
        connectors: dict[str, MarketConnector],
        *,
        lake: LocalDataLake | None = None,
        quality_engine: MarketDataQualityEngine | None = None,
        checkpoints: CheckpointStore | None = None,
        maximum_workers: int = 4,
    ) -> None:
        if maximum_workers < 1:
            raise ValueError("maximum_workers must be positive")
        self.connectors = dict(connectors)
        self.lake = lake or LocalDataLake()
        self.quality_engine = quality_engine or MarketDataQualityEngine()
        self.checkpoints = checkpoints or CheckpointStore()
        self.maximum_workers = maximum_workers

    def synchronize(
        self, source: str, request: SyncRequest, *, incremental: bool = True
    ) -> SynchronizationResult:
        connector = self.connectors.get(source)
        if connector is None:
            raise KeyError(f"connector is not registered: {source}")
        previous = self.checkpoints.get(source, request.symbol, request.interval)
        effective = request
        if incremental and previous and previous.last_timestamp:
            start = max(request.start, previous.last_timestamp + timedelta(microseconds=1))
            if start >= request.end:
                start = request.end - timedelta(microseconds=1)
            effective = request.model_copy(update={"start": start})
        attempts = (previous.attempts if previous else 0) + 1
        try:
            result = connector.fetch(effective)
            quality = self.quality_engine.validate(result.bars)
            quality.raise_if_rejected()
            payload = self._serialize(result)
            manifest = self.lake.write_raw(
                f"{source}-{request.symbol}-{request.interval}",
                gzip.compress(payload, mtime=0),
                source=source,
                quality=QualityMetrics(
                    row_count=len(result.bars),
                    missing_values=0,
                    duplicate_rows=quality.duplicate_timestamps,
                    schema_valid=quality.accepted,
                    chronological=True,
                    quality_score=quality.score,
                ),
                metadata={
                    "compression": "gzip",
                    "representation": "canonical_connector_output",
                    "request": effective.model_dump(mode="json"),
                    "connector_metadata": result.metadata.model_dump(mode="json"),
                },
            )
            latest = (
                result.bars[-1].timestamp
                if result.bars
                else previous.last_timestamp
                if previous
                else None
            )
            self.checkpoints.save(
                SyncCheckpoint(
                    source=source,
                    symbol=request.symbol,
                    interval=request.interval,
                    last_timestamp=latest,
                    status="completed",
                    attempts=attempts,
                    updated_at=datetime.now(UTC),
                )
            )
            return SynchronizationResult(
                source=source,
                symbol=request.symbol,
                records=len(result.bars),
                dataset_version=manifest.version,
                checkpoint=latest.isoformat() if latest else None,
                quality=quality,
            )
        except Exception as exc:
            self.checkpoints.save(
                SyncCheckpoint(
                    source=source,
                    symbol=request.symbol,
                    interval=request.interval,
                    last_timestamp=previous.last_timestamp if previous else None,
                    status="failed",
                    attempts=attempts,
                    error=f"{type(exc).__name__}: {exc}",
                    updated_at=datetime.now(UTC),
                )
            )
            logger.exception(
                "synchronization failed",
                extra={"source": source, "symbol": request.symbol},
            )
            raise

    def synchronize_many(
        self, jobs: list[tuple[str, SyncRequest]], *, incremental: bool = True
    ) -> list[SynchronizationResult]:
        results: list[SynchronizationResult] = []
        with ThreadPoolExecutor(max_workers=self.maximum_workers) as executor:
            futures = {
                executor.submit(self.synchronize, source, request, incremental=incremental): (
                    source,
                    request.symbol,
                )
                for source, request in jobs
            }
            for future in as_completed(futures):
                results.append(future.result())
        return sorted(results, key=lambda item: (item.source, item.symbol))

    @staticmethod
    def _serialize(result: SyncResult) -> bytes:
        payload: dict[str, Any] = {
            "metadata": result.metadata.model_dump(mode="json"),
            "bars": [bar.model_dump(mode="json") for bar in result.bars],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
