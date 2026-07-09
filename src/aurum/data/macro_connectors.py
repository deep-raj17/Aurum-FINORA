"""Official macroeconomic API connectors with pagination and UTC normalization."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

from pydantic import BaseModel, Field, model_validator

from .resilience import ConnectorError, ResilientJSONClient


class MacroSyncRequest(BaseModel):
    indicator: str = Field(min_length=1)
    geography: str = Field(min_length=1)
    start: datetime
    end: datetime
    frequency: str = "annual"
    dataset: str | None = None

    @model_validator(mode="after")
    def ordered(self) -> MacroSyncRequest:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("macro sync boundaries must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("macro sync start must precede end")
        return self


class MacroObservation(BaseModel):
    indicator: str
    geography: str
    timestamp: datetime
    value: float
    unit: str | None = None
    source: str
    source_note: str | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attributes: dict[str, Any] = Field(default_factory=dict)


class MacroSyncResult(BaseModel):
    observations: list[MacroObservation]
    source: str
    pages: int = Field(ge=1)
    checkpoint: str | None = None


class WorldBankConnector:
    source = "world_bank"

    def __init__(self, client: ResilientJSONClient | None = None) -> None:
        self.client = client or ResilientJSONClient(requests_per_second=2)

    def fetch(self, request: MacroSyncRequest) -> MacroSyncResult:
        page = 1
        pages = 1
        observations: list[MacroObservation] = []
        while page <= pages:
            query = urlencode(
                {
                    "format": "json",
                    "date": f"{request.start.year}:{request.end.year}",
                    "page": page,
                    "per_page": 1000,
                }
            )
            payload = self.client.get(
                "https://api.worldbank.org/v2/country/"
                f"{quote(request.geography)}/indicator/{quote(request.indicator)}?{query}",
                validator=lambda value: (
                    isinstance(value, list) and len(value) == 2 and isinstance(value[0], dict)
                ),
            )
            pages = int(payload[0].get("pages", 1))
            for row in payload[1] or []:
                if row.get("value") is None:
                    continue
                observations.append(
                    MacroObservation(
                        indicator=request.indicator,
                        geography=str(row.get("countryiso3code") or request.geography),
                        timestamp=datetime(int(row["date"]), 12, 31, tzinfo=UTC),
                        value=float(row["value"]),
                        source=self.source,
                        source_note=row.get("obs_status") or None,
                        attributes={
                            "indicator_name": row.get("indicator", {}).get("value"),
                            "country_name": row.get("country", {}).get("value"),
                            "decimal": row.get("decimal"),
                        },
                    )
                )
            page += 1
        observations.sort(key=lambda item: item.timestamp)
        return MacroSyncResult(
            observations=observations,
            source=self.source,
            pages=pages,
            checkpoint=observations[-1].timestamp.isoformat() if observations else None,
        )


class SDMXCSVConnector:
    """SDMX REST connector shared by ECB and OECD CSV endpoints."""

    source: str
    base_url: str
    accept = "text/csv"

    def __init__(self, client: ResilientJSONClient | None = None) -> None:
        self.client = client or ResilientJSONClient(requests_per_second=2)

    def fetch(self, request: MacroSyncRequest) -> MacroSyncResult:
        if not request.dataset:
            raise ValueError("SDMX requests require a dataset/dataflow identifier")
        query = urlencode(
            {
                "startPeriod": request.start.date().isoformat(),
                "endPeriod": request.end.date().isoformat(),
            }
        )
        url = (
            f"{self.base_url}/{quote(request.dataset, safe=',.@')}/"
            f"{quote(request.indicator, safe='.+-')}"
            f"?{query}"
        )
        payload = self.client.get_bytes(url, headers={"Accept": self.accept})
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
        observations = []
        for row in rows:
            time_value = row.get("TIME_PERIOD") or row.get("TIME")
            observation = row.get("OBS_VALUE") or row.get("Value")
            if not time_value or observation in (None, ""):
                continue
            observations.append(
                MacroObservation(
                    indicator=request.indicator,
                    geography=row.get("REF_AREA") or request.geography,
                    timestamp=self._timestamp(time_value),
                    value=float(str(observation)),
                    unit=row.get("UNIT_MEASURE") or row.get("Unit"),
                    source=self.source,
                    attributes={
                        key: value
                        for key, value in row.items()
                        if key not in {"TIME_PERIOD", "TIME", "OBS_VALUE", "Value"}
                        and value not in (None, "")
                    },
                )
            )
        if rows and not observations:
            raise ConnectorError(f"{self.source} CSV contained no parseable observations")
        observations.sort(key=lambda item: item.timestamp)
        return MacroSyncResult(
            observations=observations,
            source=self.source,
            pages=1,
            checkpoint=observations[-1].timestamp.isoformat() if observations else None,
        )

    @staticmethod
    def _timestamp(value: str) -> datetime:
        if len(value) == 4:
            return datetime(int(value), 12, 31, tzinfo=UTC)
        if "Q" in value:
            year, quarter = value.split("-Q")
            return datetime(int(year), int(quarter) * 3, 1, tzinfo=UTC)
        if len(value) == 7:
            return datetime.fromisoformat(f"{value}-01").replace(tzinfo=UTC)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class ECBConnector(SDMXCSVConnector):
    source = "ecb"
    base_url = "https://data-api.ecb.europa.eu/service/data"
    accept = "text/csv"


class OECDConnector(SDMXCSVConnector):
    source = "oecd"
    base_url = "https://sdmx.oecd.org/public/rest/v1/data"
    accept = "text/csv"


class IMFConnector(SDMXCSVConnector):
    """IMF DataMapper connector with normalized annual observations."""

    source = "imf"
    base_url = "https://www.imf.org/external/datamapper/api/v1"

    def fetch(self, request: MacroSyncRequest) -> MacroSyncResult:
        query = urlencode(
            {
                "periods": ",".join(
                    str(year) for year in range(request.start.year, request.end.year + 1)
                )
            }
        )
        payload = self.client.get(
            f"{self.base_url}/{quote(request.indicator)}/{quote(request.geography)}?{query}",
            validator=lambda value: (
                isinstance(value, dict) and isinstance(value.get("values"), dict)
            ),
        )
        geography_values = payload["values"].get(request.indicator, {}).get(request.geography, {})
        observations = [
            MacroObservation(
                indicator=request.indicator,
                geography=request.geography,
                timestamp=datetime(int(period), 12, 31, tzinfo=UTC),
                value=float(value),
                source=self.source,
                attributes={"api": "IMF DataMapper", "period": period},
            )
            for period, value in geography_values.items()
            if value is not None and request.start.year <= int(period) <= request.end.year
        ]
        observations.sort(key=lambda item: item.timestamp)
        return MacroSyncResult(
            observations=observations,
            source=self.source,
            pages=1,
            checkpoint=observations[-1].timestamp.isoformat() if observations else None,
        )
