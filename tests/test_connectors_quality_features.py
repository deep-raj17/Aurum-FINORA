import csv
import io
import sys
import types
from datetime import UTC, date, datetime

import pandas as pd
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
from aurum.data.contracts import AssetClass, ConnectorMetadata, MarketBar, SyncRequest, SyncResult
from aurum.data.lake import LocalDataLake
from aurum.data.macro_connectors import (
    ECBConnector,
    IMFConnector,
    MacroSyncRequest,
    WorldBankConnector,
)
from aurum.data.providers import FREDProvider, SECProvider
from aurum.data.quality import DataQualityError, MarketDataQualityEngine
from aurum.data.sync import CheckpointStore, DataSynchronizer
from aurum.feature_store import FeatureDefinition, FeatureValue, PointInTimeFeatureStore


class StaticClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []
        self.timeout_seconds = 5

    def get(self, url, *, headers=None, validator=None):
        self.calls.append(url)
        payload = self.payloads.pop(0)
        assert validator is None or validator(payload)
        return payload

    def get_bytes(self, url, *, headers=None, validator=None):
        self.calls.append(url)
        payload = self.payloads.pop(0)
        assert validator is None or validator(payload)
        return payload


def sync_request() -> SyncRequest:
    return SyncRequest(
        symbol="TEST",
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 1, 5, tzinfo=UTC),
    )


def bar(day: int, close: float = 100, *, currency: str = "USD") -> MarketBar:
    return MarketBar(
        symbol="TEST",
        timestamp=datetime(2025, 1, day, tzinfo=UTC),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1000,
        currency=currency,
        asset_class=AssetClass.EQUITY,
        source="test",
    )


def test_alpha_vantage_normalizes_and_filters() -> None:
    client = StaticClient(
        [
            {
                "Meta Data": {"symbol": "TEST"},
                "Time Series (Daily)": {
                    "2025-01-02": {
                        "1. open": "100",
                        "2. high": "102",
                        "3. low": "99",
                        "4. close": "101",
                        "5. adjusted close": "100.5",
                        "6. volume": "1234",
                    }
                },
            }
        ]
    )
    result = AlphaVantageConnector(api_key="secret", client=client).fetch(sync_request())
    assert result.bars[0].timestamp.tzinfo is UTC
    assert result.bars[0].adjusted_close == 100.5
    assert result.metadata.records == 1
    assert "secret" in client.calls[0]


def test_binance_advances_pagination() -> None:
    first = [
        [
            int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000),
            "100",
            "102",
            "99",
            "101",
            "10",
            int(datetime(2025, 1, 2, tzinfo=UTC).timestamp() * 1000) - 1,
        ]
    ]
    client = StaticClient([first])
    result = BinanceConnector(client=client).fetch(sync_request())
    assert len(result.bars) == 1
    assert result.metadata.pages == 1


def test_tiingo_and_coingecko_normalize_provider_payloads() -> None:
    tiingo = TiingoConnector(
        api_key="secret",
        client=StaticClient(
            [
                [
                    {
                        "date": "2025-01-02T00:00:00Z",
                        "open": 100,
                        "high": 102,
                        "low": 99,
                        "close": 101,
                        "adjClose": 100.5,
                        "volume": 10,
                        "divCash": 0,
                        "splitFactor": 1,
                    }
                ]
            ]
        ),
    ).fetch(sync_request())
    assert tiingo.bars[0].adjusted_close == 100.5
    coingecko = CoinGeckoConnector(
        client=StaticClient(
            [
                {
                    "prices": [[int(datetime(2025, 1, 2, tzinfo=UTC).timestamp() * 1000), 42]],
                    "total_volumes": [
                        [int(datetime(2025, 1, 2, tzinfo=UTC).timestamp() * 1000), 99]
                    ],
                }
            ]
        )
    ).fetch(sync_request().model_copy(update={"symbol": "bitcoin"}))
    assert coingecko.bars[0].asset_class is AssetClass.CRYPTO
    assert coingecko.bars[0].volume == 99


def test_nasdaq_fmp_and_finnhub_validate_real_schemas() -> None:
    nasdaq = NasdaqDataLinkConnector(
        api_key="secret",
        client=StaticClient(
            [
                {
                    "dataset": {
                        "id": 1,
                        "dataset_code": "TEST",
                        "column_names": ["Date", "Open", "High", "Low", "Close", "Volume"],
                        "data": [["2025-01-02", 1, 3, 0.5, 2, 100]],
                    }
                }
            ]
        ),
    ).fetch(sync_request())
    assert nasdaq.bars[0].raw_identifier == "1"
    fmp = FinancialModelingPrepConnector(
        api_key="secret",
        client=StaticClient(
            [
                [
                    {
                        "date": "2025-01-02",
                        "open": 1,
                        "high": 3,
                        "low": 0.5,
                        "close": 2,
                        "volume": 100,
                        "adjClose": 1.9,
                    }
                ]
            ]
        ),
    ).fetch(sync_request())
    assert fmp.bars[0].adjusted_close == 1.9
    finnhub = FinnhubConnector(
        api_key="secret",
        client=StaticClient(
            [
                {
                    "s": "ok",
                    "o": [1],
                    "h": [3],
                    "l": [0.5],
                    "c": [2],
                    "t": [int(datetime(2025, 1, 2, tzinfo=UTC).timestamp())],
                    "v": [100],
                }
            ]
        ),
    ).fetch(sync_request())
    assert finnhub.bars[0].close == 2


def test_finnhub_rejects_inconsistent_arrays_and_handles_no_data() -> None:
    no_data = FinnhubConnector(api_key="secret", client=StaticClient([{"s": "no_data"}])).fetch(
        sync_request()
    )
    assert no_data.bars == []
    with pytest.raises(Exception, match="inconsistent"):
        FinnhubConnector(
            api_key="secret",
            client=StaticClient(
                [{"s": "ok", "o": [1], "h": [], "l": [1], "c": [1], "t": [1], "v": [1]}]
            ),
        ).fetch(sync_request())


def test_yahoo_adapter_handles_multiindex_and_corporate_actions(monkeypatch) -> None:
    index = pd.DatetimeIndex([datetime(2025, 1, 2, tzinfo=UTC)])
    frame = pd.DataFrame(
        [[1, 3, 0.5, 2, 100, 0.1, 0]],
        index=index,
        columns=pd.MultiIndex.from_tuples(
            [
                ("Open", "TEST"),
                ("High", "TEST"),
                ("Low", "TEST"),
                ("Close", "TEST"),
                ("Volume", "TEST"),
                ("Dividends", "TEST"),
                ("Stock Splits", "TEST"),
            ]
        ),
    )
    monkeypatch.setitem(
        sys.modules, "yfinance", types.SimpleNamespace(download=lambda *args, **kwargs: frame)
    )
    result = YahooFinanceConnector(client=StaticClient([])).fetch(sync_request())
    assert result.bars[0].adjusted_close == 2
    assert result.bars[0].dividend == 0.1


def test_stooq_rejects_corrupted_csv() -> None:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["Date", "Open", "High", "Low", "Close", "Volume"])
    writer.writeheader()
    writer.writerow(
        {
            "Date": "2025-01-02",
            "Open": "broken",
            "High": "102",
            "Low": "99",
            "Close": "101",
            "Volume": "10",
        }
    )
    with pytest.raises(Exception, match="corrupted"):
        StooqConnector(client=StaticClient([output.getvalue().encode()])).fetch(sync_request())


def test_quality_engine_rejects_duplicates_and_currency_mismatch() -> None:
    bars = [bar(1), bar(1, currency="EUR")]
    report = MarketDataQualityEngine().validate(bars)
    assert not report.accepted
    assert {issue.code for issue in report.issues} >= {
        "DUPLICATE_TIMESTAMP",
        "CURRENCY_MISMATCH",
    }
    with pytest.raises(DataQualityError):
        report.raise_if_rejected()


def test_quality_engine_flags_gaps_splits_and_outliers() -> None:
    bars = [bar(1, 100), bar(2, 101), bar(3, 100), bar(4, 101), bar(20, 400)]
    report = MarketDataQualityEngine(outlier_z_score=3).validate(bars)
    codes = {issue.code for issue in report.issues}
    assert "CALENDAR_GAP" in codes
    assert "POSSIBLE_UNADJUSTED_SPLIT" in codes


def test_feature_store_is_point_in_time_correct(tmp_path) -> None:
    store = PointInTimeFeatureStore(tmp_path / "features.sqlite3")
    definition = FeatureDefinition(
        name="returns.1d",
        version="1",
        dtype="float64",
        owner="quant",
        description="one-day return",
        transformation="close / lag(close) - 1",
        dependencies=["close"],
    )
    store.register(definition)
    store.write(
        [
            FeatureValue(
                entity="TEST",
                feature=definition.name,
                version=definition.version,
                event_timestamp=datetime(2025, 1, 2, tzinfo=UTC),
                value=0.01,
                source_dataset_sha256="a" * 64,
            ),
            FeatureValue(
                entity="TEST",
                feature=definition.name,
                version=definition.version,
                event_timestamp=datetime(2025, 1, 3, tzinfo=UTC),
                value=0.02,
                source_dataset_sha256="b" * 64,
            ),
        ]
    )
    historical = store.point_in_time(
        ["TEST"],
        [(definition.name, definition.version)],
        datetime(2025, 1, 2, 12, tzinfo=UTC),
    )
    assert historical["TEST"][definition.name]["value"] == 0.01
    assert (
        store.online_get(
            "TEST",
            definition.name,
            definition.version,
            datetime(2025, 1, 4, tzinfo=UTC),
        )
        == 0.02
    )


def test_feature_definition_version_is_immutable(tmp_path) -> None:
    store = PointInTimeFeatureStore(tmp_path / "features.sqlite3")
    original = FeatureDefinition(
        name="risk.beta",
        version="1",
        dtype="float64",
        owner="risk",
        description="market beta",
        transformation="cov/var",
    )
    store.register(original)
    changed = original.model_copy(update={"transformation": "different"})
    with pytest.raises(ValueError, match="immutable"):
        store.register(changed)


def test_feature_store_statistics_recompute_and_consistency(tmp_path) -> None:
    store = PointInTimeFeatureStore(tmp_path / "features.sqlite3")
    definition = FeatureDefinition(
        name="momentum.5d",
        version="2",
        dtype="float64",
        owner="quant",
        description="momentum",
        transformation="close / lag5 - 1",
    )
    timestamps = [
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 2, tzinfo=UTC),
    ]
    count = store.recompute(
        definition,
        ["TEST"],
        timestamps,
        lambda entity, timestamp: (float(timestamp.day), "c" * 64),
    )
    assert count == 2
    assert store.statistics(definition.name, definition.version).mean == 1.5
    assert (
        len(
            store.offline_range(
                "TEST", definition.name, definition.version, timestamps[0], timestamps[1]
            )
        )
        == 2
    )
    store.assert_training_serving_consistency(
        "TEST", definition.name, definition.version, timestamps[1], 2.0
    )
    with pytest.raises(RuntimeError, match="skew"):
        store.assert_training_serving_consistency(
            "TEST", definition.name, definition.version, timestamps[1], 99
        )


def test_world_bank_paginates_and_normalizes() -> None:
    pages = [
        [
            {"page": 1, "pages": 2},
            [
                {
                    "date": "2024",
                    "value": 2.5,
                    "countryiso3code": "IND",
                    "country": {"value": "India"},
                    "indicator": {"value": "Growth"},
                }
            ],
        ],
        [
            {"page": 2, "pages": 2},
            [
                {
                    "date": "2025",
                    "value": 3.0,
                    "countryiso3code": "IND",
                    "country": {"value": "India"},
                    "indicator": {"value": "Growth"},
                }
            ],
        ],
    ]
    result = WorldBankConnector(StaticClient(pages)).fetch(
        MacroSyncRequest(
            indicator="NY.GDP.MKTP.KD.ZG",
            geography="IND",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert result.pages == 2
    assert [item.value for item in result.observations] == [2.5, 3.0]


def test_ecb_parses_sdmx_csv() -> None:
    payload = b"TIME_PERIOD,OBS_VALUE,REF_AREA,UNIT_MEASURE\n2025-01,2.75,EA,PCPA\n"
    result = ECBConnector(StaticClient([payload])).fetch(
        MacroSyncRequest(
            indicator="M.U2.N.A.A20.A.1.U2.2300.Z01.E",
            geography="EA",
            dataset="EXR",
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2025, 2, 1, tzinfo=UTC),
        )
    )
    assert result.observations[0].value == 2.75
    assert result.observations[0].timestamp.tzinfo is UTC


def test_imf_normalizes_datamapper_observations() -> None:
    payload = {"values": {"NGDP_RPCH": {"IND": {"2024": 6.5, "2025": 6.2}}}}
    result = IMFConnector(StaticClient([payload])).fetch(
        MacroSyncRequest(
            indicator="NGDP_RPCH",
            geography="IND",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert [item.value for item in result.observations] == [6.5, 6.2]
    assert result.checkpoint == "2025-12-31T00:00:00+00:00"


def test_fred_paginates_and_skips_missing_observations() -> None:
    client = StaticClient(
        [
            {
                "count": 2,
                "observations": [
                    {"date": "2025-01-01", "value": "2.5"},
                    {"date": "2025-02-01", "value": "."},
                ],
            }
        ]
    )
    points = FREDProvider("secret", client=client).fetch(
        "FEDFUNDS", date(2025, 1, 1), date(2025, 2, 1)
    )
    assert len(points) == 1
    assert points[0].value == 2.5
    assert "offset=0" in client.calls[0]


def test_sec_validates_identity_and_company_facts() -> None:
    client = StaticClient(
        [
            {"cik": "320193", "filings": {"recent": {}}},
            {"cik": 320193, "facts": {"us-gaap": {}}},
        ]
    )
    provider = SECProvider("FINORA engineering@example.com", client=client)
    assert provider.submissions("320193")["filings"] == {"recent": {}}
    assert provider.company_facts("320193")["facts"] == {"us-gaap": {}}


class RecordingConnector:
    source = "recording"

    def __init__(self, bars):
        self.bars = bars
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        return SyncResult(
            bars=self.bars,
            metadata=ConnectorMetadata(
                source=self.source,
                request_id="request",
                retrieved_at=datetime.now(UTC),
                records=len(self.bars),
                pages=1,
            ),
        )


def test_synchronizer_writes_compressed_lake_and_resumes(tmp_path) -> None:
    connector = RecordingConnector([bar(1), bar(2)])
    synchronizer = DataSynchronizer(
        {"recording": connector},
        lake=LocalDataLake(tmp_path / "lake"),
        checkpoints=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
    )
    request = sync_request()
    first = synchronizer.synchronize("recording", request)
    second = synchronizer.synchronize("recording", request)
    assert first.records == 2
    assert first.dataset_version
    assert second.checkpoint
    assert connector.requests[1].start > connector.requests[0].start
    checkpoint = synchronizer.checkpoints.get("recording", "TEST", "1d")
    assert checkpoint is not None
    assert checkpoint.status == "completed"


def test_synchronizer_records_quality_failure(tmp_path) -> None:
    connector = RecordingConnector([bar(1), bar(1)])
    synchronizer = DataSynchronizer(
        {"recording": connector},
        lake=LocalDataLake(tmp_path / "lake"),
        checkpoints=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
    )
    with pytest.raises(DataQualityError):
        synchronizer.synchronize("recording", sync_request())
    checkpoint = synchronizer.checkpoints.get("recording", "TEST", "1d")
    assert checkpoint is not None
    assert checkpoint.status == "failed"
    assert "DataQualityError" in (checkpoint.error or "")


def test_synchronizer_parallel_downloads(tmp_path) -> None:
    connector = RecordingConnector([bar(1)])
    synchronizer = DataSynchronizer(
        {"recording": connector},
        lake=LocalDataLake(tmp_path / "lake"),
        checkpoints=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
    )
    requests = [
        sync_request(),
        sync_request().model_copy(update={"symbol": "OTHER"}),
    ]
    results = synchronizer.synchronize_many([("recording", request) for request in requests])
    assert len(results) == 2
    assert all(result.records == 1 for result in results)
