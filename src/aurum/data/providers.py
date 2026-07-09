"""Timestamp-preserving ingestion adapters with explicit provenance."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

import numpy as np
from pydantic import BaseModel

from .resilience import ConnectorError, ResilientJSONClient


class DataPoint(BaseModel):
    entity: str
    timestamp: datetime
    value: float
    unit: str
    source: str
    release_timestamp: datetime


class TimeSeriesProvider(Protocol):
    def fetch(self, series: str, start: date, end: date) -> list[DataPoint]: ...


class CSVProvider:
    """Read normalized CSV columns: timestamp,value[,entity,unit,release_timestamp]."""

    def __init__(self, path: str | Path, source: str = "local-csv") -> None:
        self.path = Path(path)
        self.source = source

    def fetch(self, series: str, start: date, end: date) -> list[DataPoint]:
        points: list[DataPoint] = []
        with self.path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
                if not start <= timestamp.date() <= end:
                    continue
                released = row.get("release_timestamp")
                release_timestamp = (
                    datetime.fromisoformat(released.replace("Z", "+00:00"))
                    if released
                    else timestamp
                )
                if release_timestamp.tzinfo is None:
                    release_timestamp = release_timestamp.replace(tzinfo=UTC)
                points.append(
                    DataPoint(
                        entity=row.get("entity") or series,
                        timestamp=timestamp,
                        value=float(row["value"]),
                        unit=row.get("unit") or "unknown",
                        source=self.source,
                        release_timestamp=release_timestamp,
                    )
                )
        return sorted(points, key=lambda point: point.timestamp)


class SyntheticProvider:
    def __init__(self, seed: int = 42, initial_value: float = 100.0) -> None:
        self.seed = seed
        self.initial_value = initial_value

    def fetch(self, series: str, start: date, end: date) -> list[DataPoint]:
        days = (end - start).days + 1
        rng = np.random.default_rng(self.seed)
        levels = self.initial_value * np.exp(np.cumsum(rng.normal(0.0002, 0.01, days)))
        return [
            DataPoint(
                entity=series,
                timestamp=datetime.combine(start + timedelta(days=index), datetime.min.time(), UTC),
                value=float(value),
                unit="index",
                source=f"synthetic(seed={self.seed})",
                release_timestamp=datetime.combine(
                    start + timedelta(days=index), datetime.min.time(), UTC
                ),
            )
            for index, value in enumerate(levels)
        ]


class FREDProvider:
    """FRED observations adapter with pagination, retries, cache, and validation."""

    endpoint = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(
        self,
        api_key: str,
        timeout: float = 20,
        client: ResilientJSONClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("FRED_API_KEY is required")
        self.api_key = api_key
        self.timeout = timeout
        self.client = client or ResilientJSONClient(timeout_seconds=timeout, requests_per_second=2)

    def fetch(self, series: str, start: date, end: date) -> list[DataPoint]:
        retrieved_at = datetime.now(UTC)
        offset = 0
        limit = 100_000
        points: list[DataPoint] = []
        while True:
            query = urlencode(
                {
                    "series_id": series,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "observation_start": start.isoformat(),
                    "observation_end": end.isoformat(),
                    "limit": limit,
                    "offset": offset,
                    "sort_order": "asc",
                }
            )
            payload = self.client.get(
                f"{self.endpoint}?{query}",
                validator=lambda value: (
                    isinstance(value, dict)
                    and isinstance(value.get("observations"), list)
                    and isinstance(value.get("count"), int)
                ),
            )
            observations = payload["observations"]
            for item in observations:
                if item.get("value") in (None, "."):
                    continue
                try:
                    points.append(
                        DataPoint(
                            entity=series,
                            timestamp=datetime.fromisoformat(item["date"]).replace(tzinfo=UTC),
                            value=float(item["value"]),
                            unit="FRED series units",
                            source=f"FRED:{series}",
                            release_timestamp=retrieved_at,
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ConnectorError("FRED returned an invalid observation") from exc
            offset += len(observations)
            if not observations or offset >= int(payload["count"]):
                break
        return points


class SECProvider:
    """Retrieve SEC submissions using its required identity and resilient transport."""

    def __init__(
        self,
        user_agent: str,
        timeout: float = 20,
        client: ResilientJSONClient | None = None,
    ) -> None:
        if "@" not in user_agent:
            raise ValueError("SEC user agent must contain a contact email")
        self.user_agent = user_agent
        self.timeout = timeout
        self.client = client or ResilientJSONClient(timeout_seconds=timeout, requests_per_second=5)

    def submissions(self, cik: str) -> dict[str, object]:
        normalized = cik.zfill(10)
        payload = self.client.get(
            f"https://data.sec.gov/submissions/CIK{normalized}.json",
            headers={"User-Agent": self.user_agent},
            validator=lambda value: (
                isinstance(value, dict)
                and str(value.get("cik", "")).zfill(10) == normalized
                and isinstance(value.get("filings"), dict)
            ),
        )
        return payload

    def company_facts(self, cik: str) -> dict[str, object]:
        normalized = cik.zfill(10)
        payload = self.client.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized}.json",
            headers={"User-Agent": self.user_agent},
            validator=lambda value: (
                isinstance(value, dict)
                and str(value.get("cik", "")).zfill(10) == normalized
                and isinstance(value.get("facts"), dict)
            ),
        )
        return payload
