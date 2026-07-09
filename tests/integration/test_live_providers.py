"""Credentialed provider validation.

Run with ``FINORA_RUN_LIVE_TESTS=1 pytest -m live tests/integration``.
Provider-specific tests skip when their required credential/configuration is absent.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta

import pytest

from aurum.data.connectors import (
    AlphaVantageConnector,
    BinanceConnector,
    CoinGeckoConnector,
    FinancialModelingPrepConnector,
    FinnhubConnector,
    NasdaqDataLinkConnector,
    StooqConnector,
    TiingoConnector,
    YahooFinanceConnector,
)
from aurum.data.contracts import SyncRequest
from aurum.data.macro_connectors import (
    ECBConnector,
    IMFConnector,
    MacroSyncRequest,
    OECDConnector,
    WorldBankConnector,
)
from aurum.data.providers import FREDProvider, SECProvider
from aurum.data.quality import MarketDataQualityEngine

pytestmark = pytest.mark.live


def _enabled() -> None:
    if os.getenv("FINORA_RUN_LIVE_TESTS") != "1":
        pytest.skip("set FINORA_RUN_LIVE_TESTS=1 to permit external API calls")


def _credential(name: str) -> str:
    _enabled()
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def _market_request(symbol: str = "AAPL", days: int = 10) -> SyncRequest:
    end = datetime.now(UTC) - timedelta(days=1)
    return SyncRequest(symbol=symbol, start=end - timedelta(days=days), end=end)


def _assert_market(result) -> None:
    assert result.bars, "provider returned no bars for the validation interval"
    report = MarketDataQualityEngine().validate(result.bars)
    report.raise_if_rejected()
    assert result.metadata.records == len(result.bars)
    assert result.metadata.request_id


@pytest.mark.parametrize(
    ("factory", "credential", "symbol"),
    [
        (lambda key: AlphaVantageConnector(key), "ALPHA_VANTAGE_API_KEY", "IBM"),
        (lambda key: TiingoConnector(key), "TIINGO_API_KEY", "AAPL"),
        (
            lambda key: NasdaqDataLinkConnector(key),
            "NASDAQ_DATA_LINK_API_KEY",
            os.getenv("NASDAQ_DATA_LINK_TEST_DATASET", "WIKI/AAPL"),
        ),
        (lambda key: FinancialModelingPrepConnector(key), "FMP_API_KEY", "AAPL"),
        (lambda key: FinnhubConnector(key), "FINNHUB_API_KEY", "AAPL"),
    ],
)
def test_credentialed_market_provider(factory, credential, symbol) -> None:
    _assert_market(factory(_credential(credential)).fetch(_market_request(symbol, 30)))


def test_yahoo_finance_live() -> None:
    _enabled()
    _assert_market(YahooFinanceConnector().fetch(_market_request("AAPL")))


def test_stooq_live() -> None:
    _enabled()
    _assert_market(StooqConnector().fetch(_market_request("aapl.us", 30)))


def test_coingecko_live() -> None:
    _enabled()
    _assert_market(CoinGeckoConnector().fetch(_market_request("bitcoin", 3)))


def test_binance_live() -> None:
    _enabled()
    _assert_market(BinanceConnector().fetch(_market_request("BTCUSDT", 3)))


def test_fred_live() -> None:
    provider = FREDProvider(_credential("FRED_API_KEY"))
    today = date.today()
    points = provider.fetch("FEDFUNDS", today - timedelta(days=365), today)
    assert points and all(point.source == "FRED:FEDFUNDS" for point in points)


def test_sec_edgar_live() -> None:
    _enabled()
    user_agent = os.getenv("SEC_USER_AGENT")
    if not user_agent:
        pytest.skip("SEC_USER_AGENT with a contact email is not configured")
    provider = SECProvider(user_agent)
    assert provider.submissions("320193")["filings"]
    assert provider.company_facts("320193")["facts"]


def _macro_request(
    indicator: str, geography: str, *, dataset: str | None = None
) -> MacroSyncRequest:
    return MacroSyncRequest(
        indicator=indicator,
        geography=geography,
        dataset=dataset,
        start=datetime(2020, 1, 1, tzinfo=UTC),
        end=datetime.now(UTC),
    )


def test_world_bank_live() -> None:
    _enabled()
    result = WorldBankConnector().fetch(_macro_request("NY.GDP.MKTP.KD.ZG", "IND"))
    assert result.observations


def test_imf_live() -> None:
    _enabled()
    result = IMFConnector().fetch(_macro_request("NGDP_RPCH", "IND"))
    assert result.observations


@pytest.mark.parametrize(
    ("connector", "prefix"),
    [(ECBConnector, "ECB"), (OECDConnector, "OECD")],
)
def test_configured_sdmx_live(connector, prefix) -> None:
    _enabled()
    dataset = os.getenv(f"{prefix}_TEST_DATASET")
    indicator = os.getenv(f"{prefix}_TEST_KEY")
    geography = os.getenv(f"{prefix}_TEST_GEOGRAPHY", "EA")
    if not dataset or not indicator:
        pytest.skip(f"{prefix}_TEST_DATASET and {prefix}_TEST_KEY are required")
    assert connector().fetch(_macro_request(indicator, geography, dataset=dataset)).observations
