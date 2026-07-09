from datetime import UTC, datetime

import numpy as np
import pytest
from pydantic import ValidationError

from aurum.config import Settings
from aurum.data.connectors import (
    AlphaVantageConnector,
    FinancialModelingPrepConnector,
    FinnhubConnector,
    NasdaqDataLinkConnector,
    TiingoConnector,
)
from aurum.data.contracts import AssetClass, MarketBar, SyncRequest
from aurum.data.macro_connectors import MacroSyncRequest
from aurum.data.quality import MarketDataQualityEngine
from aurum.forecast_system import ForecastDistribution, TreeQuantileSpecialist
from aurum.rag import ProductionRAG, SemanticChunker, SourceDocument
from aurum.security import FieldEncryptor, SlidingWindowRateLimiter


def test_production_settings_and_temporal_contracts_fail_closed(monkeypatch) -> None:
    with pytest.raises(ValidationError, match="production requires"):
        Settings(environment="production")
    production = Settings(
        environment="production",
        api_key="secret",
        sentiment_backend="finbert",
        cors_origins=["https://finora.example"],
    )
    assert production.environment == "production"
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(
            environment="production",
            api_key="secret",
            sentiment_backend="finbert",
            cors_origins=["*"],
        )
    with pytest.raises(ValidationError, match="timezone"):
        SyncRequest(symbol="X", start=datetime(2025, 1, 1), end=datetime(2025, 1, 2))
    with pytest.raises(ValidationError, match="precede"):
        MacroSyncRequest(
            indicator="X",
            geography="Y",
            start=datetime(2025, 1, 2, tzinfo=UTC),
            end=datetime(2025, 1, 1, tzinfo=UTC),
        )


def test_market_bar_ohlc_and_quality_error_branches() -> None:
    base = {
        "symbol": "X",
        "timestamp": datetime(2025, 1, 1, tzinfo=UTC),
        "open": 10,
        "high": 11,
        "low": 9,
        "close": 10,
        "asset_class": AssetClass.EQUITY,
        "source": "test",
    }
    with pytest.raises(ValidationError, match="positive"):
        MarketBar.model_validate({**base, "close": -1})
    with pytest.raises(ValidationError, match="high"):
        MarketBar.model_validate({**base, "high": 9})
    bars = [
        MarketBar.model_validate(base),
        MarketBar.model_validate(
            {
                **base,
                "symbol": "Y",
                "timestamp": datetime(2025, 1, 2, tzinfo=UTC),
                "dividend": 1,
            }
        ),
    ]
    report = MarketDataQualityEngine().validate(bars)
    assert {"IDENTIFIER_MISMATCH", "MISSING_CORPORATE_ACTION_ADJUSTMENT"} <= {
        issue.code for issue in report.issues
    }
    assert not MarketDataQualityEngine().validate([]).accepted


def test_forecast_distribution_and_specialist_configuration_guards() -> None:
    with pytest.raises(ValueError, match="finite"):
        ForecastDistribution(model="bad", mean=np.array([np.nan]), quantiles={}, metadata={})
    with pytest.raises(ValueError, match="levels"):
        ForecastDistribution(
            model="bad",
            mean=np.array([1.0]),
            quantiles={1.0: np.array([1.0])},
            metadata={},
        )
    with pytest.raises(ValueError, match="engine"):
        TreeQuantileSpecialist("unknown")
    with pytest.raises(ValueError, match="ordered"):
        TreeQuantileSpecialist("xgboost", quantiles=(0.5, 0.1))


def test_rag_chunk_and_query_guards() -> None:
    with pytest.raises(ValueError, match="chunk"):
        SemanticChunker(10, 2)
    document = SourceDocument(
        document_id="long",
        origin="test",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        text=" ".join("word" for _ in range(80)),
    )
    assert len(SemanticChunker(30, 5).chunk(document)) >= 3

    class EmptyStore:
        def upsert(self, chunks):
            return None

        def search(self, *args, **kwargs):
            return []

    class Reranker:
        def score(self, query, passages):
            return []

    rag = ProductionRAG(EmptyStore(), Reranker())
    assert rag.search("query", as_of=datetime.now(UTC)) == []
    with pytest.raises(ValueError, match="non-empty"):
        rag.search("", as_of=datetime.now(UTC))


def test_connector_credentials_and_security_constructor_guards(monkeypatch) -> None:
    for name in (
        "ALPHA_VANTAGE_API_KEY",
        "ALPHAVANTAGE_API_KEY",
        "TIINGO_API_KEY",
        "NASDAQ_DATA_LINK_API_KEY",
        "FMP_API_KEY",
        "FINNHUB_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    for connector in (
        AlphaVantageConnector,
        TiingoConnector,
        NasdaqDataLinkConnector,
        FinancialModelingPrepConnector,
        FinnhubConnector,
    ):
        with pytest.raises(ValueError, match="required"):
            connector()
    with pytest.raises(ValueError, match="positive"):
        SlidingWindowRateLimiter(0, 1)
    with pytest.raises(ValueError, match="truncated"):
        object.__new__(FieldEncryptor).decrypt("eA==", context="ctx")


def test_api_key_startup_validation_uses_canonical_names(monkeypatch) -> None:
    from aurum.config import validate_api_keys

    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "configured")
    monkeypatch.setenv("TIINGO_API_KEY", "configured")
    monkeypatch.setenv("FINNHUB_API_KEY", "configured")
    status = validate_api_keys()
    assert status["ALPHA_VANTAGE"]
    assert status["TIINGO"]
    assert status["FINNHUB"]
    assert not status["FRED"]
