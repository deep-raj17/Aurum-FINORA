"""Canonical financial data contracts shared by all external connectors."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class AssetClass(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    FOREX = "forex"
    CRYPTO = "crypto"
    FUND = "fund"
    COMMODITY = "commodity"
    BOND = "bond"
    RATE = "rate"
    DERIVATIVE = "derivative"
    MACRO = "macro"


class MarketBar(BaseModel):
    symbol: str = Field(min_length=1)
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = Field(default=None, ge=0)
    adjusted_close: float | None = Field(default=None, gt=0)
    dividend: float | None = Field(default=None, ge=0)
    split_coefficient: float | None = Field(default=None, gt=0)
    currency: str | None = None
    asset_class: AssetClass
    source: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_identifier: str | None = None

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_ohlc(self) -> MarketBar:
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high is below another OHLC value")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low is above another OHLC value")
        return self


class SyncRequest(BaseModel):
    symbol: str = Field(min_length=1)
    start: datetime
    end: datetime
    interval: str = "1d"
    adjusted: bool = True
    checkpoint: str | None = None

    @model_validator(mode="after")
    def ordered(self) -> SyncRequest:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("sync boundaries must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("sync start must precede end")
        return self


class ConnectorMetadata(BaseModel):
    source: str
    request_id: str
    retrieved_at: datetime
    records: int = Field(ge=0)
    pages: int = Field(ge=1)
    checkpoint: str | None = None
    cache_hit: bool | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class SyncResult(BaseModel):
    bars: list[MarketBar]
    metadata: ConnectorMetadata
