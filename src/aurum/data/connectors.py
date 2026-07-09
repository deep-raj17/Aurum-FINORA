"""Production market-data connectors using canonical contracts and resilient transport."""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

from .contracts import AssetClass, ConnectorMetadata, MarketBar, SyncRequest, SyncResult
from .resilience import ConnectorError, ResilientJSONClient

logger = logging.getLogger(__name__)


def _request_id(source: str, request: SyncRequest) -> str:
    material = f"{source}|{request.model_dump_json()}"
    return hashlib.sha256(material.encode()).hexdigest()[:20]


class MarketConnector(ABC):
    """Stateless connector; transport owns thread-safe caching and rate limiting."""

    source: str

    def __init__(self, client: ResilientJSONClient | None = None) -> None:
        self.client = client or ResilientJSONClient()

    @abstractmethod
    def fetch(self, request: SyncRequest) -> SyncResult:
        """Fetch, validate and normalize a historical interval."""

    def _result(
        self,
        request: SyncRequest,
        bars: list[MarketBar],
        *,
        pages: int = 1,
        checkpoint: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SyncResult:
        filtered = [
            bar
            for bar in bars
            if request.start.astimezone(UTC) <= bar.timestamp <= request.end.astimezone(UTC)
        ]
        filtered.sort(key=lambda bar: bar.timestamp)
        return SyncResult(
            bars=filtered,
            metadata=ConnectorMetadata(
                source=self.source,
                request_id=_request_id(self.source, request),
                retrieved_at=datetime.now(UTC),
                records=len(filtered),
                pages=pages,
                checkpoint=checkpoint or (filtered[-1].timestamp.isoformat() if filtered else None),
                source_metadata=metadata or {},
            ),
        )


class AlphaVantageConnector(MarketConnector):
    source = "alpha_vantage"

    def __init__(
        self, api_key: str | None = None, client: ResilientJSONClient | None = None
    ) -> None:
        super().__init__(client)
        self.api_key = (
            api_key or os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("ALPHAVANTAGE_API_KEY")
        )
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY is required")

    def fetch(self, request: SyncRequest) -> SyncResult:
        query = urlencode(
            {
                "function": "TIME_SERIES_DAILY_ADJUSTED"
                if request.adjusted
                else "TIME_SERIES_DAILY",
                "symbol": request.symbol,
                "outputsize": "full",
                "apikey": self.api_key,
            }
        )
        payload = self.client.get(
            f"https://www.alphavantage.co/query?{query}",
            validator=lambda value: (
                isinstance(value, dict)
                and not any(key in value for key in ("Error Message", "Information", "Note"))
            ),
        )
        series_key = next(
            (key for key in payload if key.lower().startswith("time series")),
            None,
        )
        if series_key is None or not isinstance(payload[series_key], dict):
            raise ConnectorError("Alpha Vantage response omitted its time series")
        bars = []
        for timestamp, row in payload[series_key].items():
            bars.append(
                MarketBar(
                    symbol=request.symbol,
                    timestamp=datetime.fromisoformat(timestamp).replace(tzinfo=UTC),
                    open=float(row["1. open"]),
                    high=float(row["2. high"]),
                    low=float(row["3. low"]),
                    close=float(row["4. close"]),
                    adjusted_close=float(row.get("5. adjusted close", row["4. close"])),
                    dividend=float(row["7. dividend amount"])
                    if row.get("7. dividend amount")
                    else None,
                    split_coefficient=float(row["8. split coefficient"])
                    if row.get("8. split coefficient")
                    else None,
                    volume=float(row.get("6. volume", row.get("5. volume", 0))),
                    asset_class=AssetClass.EQUITY,
                    source=self.source,
                )
            )
        return self._result(request, bars, metadata={"provider_metadata": payload.get("Meta Data")})


class TiingoConnector(MarketConnector):
    source = "tiingo"

    def __init__(
        self, api_key: str | None = None, client: ResilientJSONClient | None = None
    ) -> None:
        super().__init__(client)
        self.api_key = api_key or os.getenv("TIINGO_API_KEY")
        if not self.api_key:
            raise ValueError("TIINGO_API_KEY is required")

    def fetch(self, request: SyncRequest) -> SyncResult:
        query = urlencode(
            {
                "startDate": request.start.date().isoformat(),
                "endDate": request.end.date().isoformat(),
                "resampleFreq": "daily",
            }
        )
        payload = self.client.get(
            f"https://api.tiingo.com/tiingo/daily/{quote(request.symbol)}/prices?{query}",
            headers={"Authorization": f"Token {self.api_key}"},
            validator=lambda value: isinstance(value, list),
        )
        bars = [
            MarketBar(
                symbol=request.symbol,
                timestamp=datetime.fromisoformat(row["date"].replace("Z", "+00:00")),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                adjusted_close=float(row.get("adjClose", row["close"])),
                dividend=float(row["divCash"]) if row.get("divCash") is not None else None,
                split_coefficient=float(row["splitFactor"])
                if row.get("splitFactor") is not None
                else None,
                volume=float(row.get("volume") or 0),
                asset_class=AssetClass.EQUITY,
                source=self.source,
            )
            for row in payload
        ]
        return self._result(request, bars)


class CoinGeckoConnector(MarketConnector):
    source = "coingecko"

    def __init__(
        self,
        vs_currency: str = "usd",
        api_key: str | None = None,
        client: ResilientJSONClient | None = None,
    ) -> None:
        super().__init__(client)
        self.vs_currency = vs_currency
        self.api_key = api_key or os.getenv("COINGECKO_API_KEY")

    def fetch(self, request: SyncRequest) -> SyncResult:
        query = urlencode(
            {
                "vs_currency": self.vs_currency,
                "from": int(request.start.timestamp()),
                "to": int(request.end.timestamp()),
            }
        )
        headers = {"x-cg-demo-api-key": self.api_key} if self.api_key else {}
        payload = self.client.get(
            f"https://api.coingecko.com/api/v3/coins/{quote(request.symbol)}/market_chart/range?{query}",
            headers=headers,
            validator=lambda value: (
                isinstance(value, dict) and isinstance(value.get("prices"), list)
            ),
        )
        volumes = {int(row[0]): float(row[1]) for row in payload.get("total_volumes", [])}
        bars = [
            MarketBar(
                symbol=request.symbol,
                timestamp=datetime.fromtimestamp(row[0] / 1000, UTC),
                open=float(row[1]),
                high=float(row[1]),
                low=float(row[1]),
                close=float(row[1]),
                volume=volumes.get(int(row[0])),
                currency=self.vs_currency.upper(),
                asset_class=AssetClass.CRYPTO,
                source=self.source,
            )
            for row in payload["prices"]
        ]
        return self._result(request, bars)


class BinanceConnector(MarketConnector):
    source = "binance"
    maximum_page_size = 1000

    def fetch(self, request: SyncRequest) -> SyncResult:
        bars: list[MarketBar] = []
        cursor = int(request.start.timestamp() * 1000)
        end = int(request.end.timestamp() * 1000)
        pages = 0
        while cursor < end:
            query = urlencode(
                {
                    "symbol": request.symbol.upper(),
                    "interval": request.interval,
                    "startTime": cursor,
                    "endTime": end,
                    "limit": self.maximum_page_size,
                }
            )
            payload = self.client.get(
                f"https://api.binance.com/api/v3/klines?{query}",
                validator=lambda value: isinstance(value, list),
            )
            pages += 1
            if not payload:
                break
            for row in payload:
                bars.append(
                    MarketBar(
                        symbol=request.symbol.upper(),
                        timestamp=datetime.fromtimestamp(row[0] / 1000, UTC),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        asset_class=AssetClass.CRYPTO,
                        source=self.source,
                    )
                )
            next_cursor = int(payload[-1][6]) + 1
            if next_cursor <= cursor:
                raise ConnectorError("Binance pagination cursor did not advance")
            cursor = next_cursor
            if len(payload) < self.maximum_page_size:
                break
        return self._result(request, bars, pages=max(pages, 1), checkpoint=str(cursor))


class StooqConnector(MarketConnector):
    source = "stooq"

    def fetch(self, request: SyncRequest) -> SyncResult:
        query = urlencode(
            {
                "s": request.symbol.lower(),
                "d1": request.start.strftime("%Y%m%d"),
                "d2": request.end.strftime("%Y%m%d"),
                "i": "d",
            }
        )
        payload = self.client.get_bytes(f"https://stooq.com/q/d/l/?{query}")
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        bars = []
        for row in reader:
            try:
                bars.append(
                    MarketBar(
                        symbol=request.symbol,
                        timestamp=datetime.fromisoformat(row["Date"]).replace(tzinfo=UTC),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row["Volume"]) if row.get("Volume") else None,
                        asset_class=AssetClass.EQUITY,
                        source=self.source,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ConnectorError("Stooq returned a corrupted CSV row") from exc
        return self._result(request, bars)


class NasdaqDataLinkConnector(MarketConnector):
    source = "nasdaq_data_link"

    def __init__(
        self, api_key: str | None = None, client: ResilientJSONClient | None = None
    ) -> None:
        super().__init__(client)
        self.api_key = api_key or os.getenv("NASDAQ_DATA_LINK_API_KEY")
        if not self.api_key:
            raise ValueError("NASDAQ_DATA_LINK_API_KEY is required")

    def fetch(self, request: SyncRequest) -> SyncResult:
        query = urlencode(
            {
                "start_date": request.start.date().isoformat(),
                "end_date": request.end.date().isoformat(),
                "order": "asc",
                "api_key": self.api_key,
            }
        )
        payload = self.client.get(
            f"https://data.nasdaq.com/api/v3/datasets/{quote(request.symbol, safe='/')}.json?{query}",
            validator=lambda value: (
                isinstance(value, dict) and isinstance(value.get("dataset"), dict)
            ),
        )
        dataset = payload["dataset"]
        columns = {name.lower(): index for index, name in enumerate(dataset["column_names"])}
        required = {"date", "open", "high", "low", "close"}
        if not required <= columns.keys():
            raise ConnectorError(
                f"Nasdaq Data Link dataset lacks OHLC columns: {sorted(required - columns.keys())}"
            )
        bars = [
            MarketBar(
                symbol=request.symbol,
                timestamp=datetime.fromisoformat(row[columns["date"]]).replace(tzinfo=UTC),
                open=float(row[columns["open"]]),
                high=float(row[columns["high"]]),
                low=float(row[columns["low"]]),
                close=float(row[columns["close"]]),
                volume=float(row[columns["volume"]])
                if "volume" in columns and row[columns["volume"]] is not None
                else None,
                adjusted_close=float(row[columns["adj. close"]])
                if "adj. close" in columns and row[columns["adj. close"]] is not None
                else None,
                asset_class=AssetClass.EQUITY,
                source=self.source,
                raw_identifier=str(dataset.get("id")),
            )
            for row in dataset["data"]
        ]
        return self._result(
            request,
            bars,
            metadata={
                "dataset_code": dataset.get("dataset_code"),
                "refreshed_at": dataset.get("refreshed_at"),
            },
        )


class FinancialModelingPrepConnector(MarketConnector):
    source = "financial_modeling_prep"

    def __init__(
        self, api_key: str | None = None, client: ResilientJSONClient | None = None
    ) -> None:
        super().__init__(client)
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise ValueError("FMP_API_KEY is required")

    def fetch(self, request: SyncRequest) -> SyncResult:
        query = urlencode(
            {
                "symbol": request.symbol,
                "from": request.start.date().isoformat(),
                "to": request.end.date().isoformat(),
                "apikey": self.api_key,
            }
        )
        payload = self.client.get(
            f"https://financialmodelingprep.com/stable/historical-price-eod/full?{query}",
            validator=lambda value: isinstance(value, list),
        )
        bars = [
            MarketBar(
                symbol=request.symbol,
                timestamp=datetime.fromisoformat(row["date"]).replace(tzinfo=UTC),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]) if row.get("volume") is not None else None,
                adjusted_close=float(row["adjClose"]) if row.get("adjClose") is not None else None,
                asset_class=AssetClass.EQUITY,
                source=self.source,
            )
            for row in payload
        ]
        return self._result(request, bars)


class FinnhubConnector(MarketConnector):
    source = "finnhub"

    def __init__(
        self, api_key: str | None = None, client: ResilientJSONClient | None = None
    ) -> None:
        super().__init__(client)
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            raise ValueError("FINNHUB_API_KEY is required")

    def fetch(self, request: SyncRequest) -> SyncResult:
        resolution = "D" if request.interval == "1d" else request.interval
        query = urlencode(
            {
                "symbol": request.symbol,
                "resolution": resolution,
                "from": int(request.start.timestamp()),
                "to": int(request.end.timestamp()),
                "token": self.api_key,
            }
        )
        payload = self.client.get(
            f"https://finnhub.io/api/v1/stock/candle?{query}",
            validator=lambda value: isinstance(value, dict) and value.get("s") in {"ok", "no_data"},
        )
        if payload["s"] == "no_data":
            return self._result(request, [])
        lengths = {len(payload[key]) for key in ("o", "h", "l", "c", "t", "v")}
        if len(lengths) != 1:
            raise ConnectorError("Finnhub candle arrays have inconsistent lengths")
        bars = [
            MarketBar(
                symbol=request.symbol,
                timestamp=datetime.fromtimestamp(payload["t"][index], UTC),
                open=float(payload["o"][index]),
                high=float(payload["h"][index]),
                low=float(payload["l"][index]),
                close=float(payload["c"][index]),
                volume=float(payload["v"][index]),
                asset_class=AssetClass.EQUITY,
                source=self.source,
            )
            for index in range(lengths.pop())
        ]
        return self._result(request, bars)


class YahooFinanceConnector(MarketConnector):
    source = "yahoo_finance"

    def __init__(
        self,
        client: ResilientJSONClient | None = None,
        retries: int = 3,
    ) -> None:
        super().__init__(client)
        self.retries = retries

    def fetch(self, request: SyncRequest) -> SyncResult:
        try:
            import yfinance
        except ImportError as exc:
            raise RuntimeError("Install aurum-finora[data] for Yahoo Finance support") from exc
        last_error: Exception | None = None
        frame = None
        for attempt in range(self.retries + 1):
            try:
                frame = yfinance.download(
                    request.symbol,
                    start=request.start.date().isoformat(),
                    end=(request.end.date() + timedelta(days=1)).isoformat(),
                    interval=request.interval,
                    auto_adjust=request.adjusted,
                    actions=True,
                    repair=True,
                    progress=False,
                    threads=False,
                    timeout=self.client.timeout_seconds,
                )
                if frame is not None and not frame.empty:
                    break
                raise ConnectorError("Yahoo Finance returned no rows")
            except Exception as exc:  # yfinance exposes several transport exceptions
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(2**attempt)
        if frame is None or frame.empty:
            raise ConnectorError("Yahoo Finance synchronization failed") from last_error
        if getattr(frame.columns, "nlevels", 1) > 1:
            frame.columns = frame.columns.get_level_values(0)
        bars = [
            MarketBar(
                symbol=request.symbol,
                timestamp=index.to_pydatetime().replace(tzinfo=index.tzinfo or UTC),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                adjusted_close=float(row["Close"]) if request.adjusted else None,
                volume=float(row["Volume"]) if row.get("Volume") is not None else None,
                dividend=float(row["Dividends"]) if row.get("Dividends") is not None else None,
                split_coefficient=float(row["Stock Splits"])
                if row.get("Stock Splits") not in (None, 0)
                else None,
                asset_class=AssetClass.EQUITY,
                source=self.source,
            )
            for index, row in frame.iterrows()
        ]
        return self._result(request, bars)
