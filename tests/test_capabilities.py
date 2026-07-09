from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from aurum.backtest import evaluate_strategy
from aurum.graph import Edge, EntityGraph
from aurum.macro import MacroInputs, classify_regime
from aurum.models import Confidence
from aurum.retrieval import Document, InMemoryRetriever
from aurum.risk import calculate_risk
from aurum.sentiment import (
    FinBERTSentimentAnalyzer,
    TextObservation,
    aggregate_sentiment,
    analyse_sentiment,
    compare_filings,
)


def test_retriever_filters_future_documents_and_ranks_matches() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    retriever = InMemoryRetriever(
        [
            Document(
                origin="Prior filing",
                published_at=now - timedelta(days=2),
                text="Revenue growth improved and guidance was raised.",
                source_confidence=Confidence.HIGH,
            ),
            Document(
                origin="Future filing",
                published_at=now + timedelta(days=1),
                text="Revenue growth collapsed.",
            ),
        ]
    )
    results = retriever.search("revenue growth", as_of=now)
    assert [item.origin for item in results] == ["Prior filing"]
    assert results[0].relevance == 1


def test_graph_returns_explicit_multihop_path() -> None:
    graph = EntityGraph(
        [
            Edge(
                source="Supplier", relationship="sells to", target="Bank", mechanism="credit loss"
            ),
            Edge(
                source="Bank",
                relationship="funds",
                target="Economy",
                mechanism="credit contraction",
            ),
        ]
    )
    description = graph.describe_path("Supplier", "Economy")
    assert "Supplier" in description
    assert "credit contraction" in description


def test_sentiment_is_auditable_and_macro_rules_are_explicit() -> None:
    sentiment = analyse_sentiment("Profit growth was strong but guidance was lowered")
    assert sentiment.positive_hits
    assert sentiment.negative_hits
    macro = classify_regime(
        MacroInputs(real_growth=-1, inflation=5, inflation_trend=0.2, policy_rate_change=0.5)
    )
    assert macro.regime == "stagflationary"
    assert macro.monetary_stance == "hawkish"


def test_finbert_adapter_uses_full_probability_distribution() -> None:
    analyzer = FinBERTSentimentAnalyzer(
        pipeline=lambda text, truncation: [
            {"label": "positive", "score": 0.8},
            {"label": "negative", "score": 0.1},
            {"label": "neutral", "score": 0.1},
        ]
    )
    result = analyzer.analyse("Revenue guidance increased")
    assert result.label == "Positive"
    assert result.probability == 0.8
    assert result.model == "ProsusAI/finbert"


def test_sentiment_aggregation_cutoff_and_filing_changes() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    momentum = aggregate_sentiment(
        [
            TextObservation(
                entity="ACME",
                timestamp=now - timedelta(hours=1),
                text="strong profit growth",
                source_type="news",
            ),
            TextObservation(
                entity="ACME",
                timestamp=now + timedelta(hours=1),
                text="default loss",
                source_type="future",
            ),
        ],
        now,
    )[0]
    assert momentum.observations == 1
    assert momentum.one_day > 0
    comparison = compare_filings("weak outlook with litigation and impairment", "strong growth")
    assert comparison.tone_divergence
    assert set(comparison.new_risk_terms) == {"impairment", "litigation"}


def test_finbert_rejects_empty_or_invalid_model_schema() -> None:
    analyzer = FinBERTSentimentAnalyzer(pipeline=lambda *args, **kwargs: [])
    with pytest.raises(ValueError, match="empty"):
        analyzer.analyse("")
    with pytest.raises(RuntimeError, match="labels"):
        analyzer.analyse("text")


def test_finbert_batch_inference_and_label_aliases() -> None:
    def pipeline(texts, **kwargs):
        assert kwargs["batch_size"] == 2
        return [
            [
                {"label": "label_0", "score": 0.1},
                {"label": "label_1", "score": 0.8},
                {"label": "label_2", "score": 0.1},
            ],
            [
                {"label": "positive", "score": 0.7},
                {"label": "negative", "score": 0.1},
                {"label": "neutral", "score": 0.2},
            ],
        ]

    analyzer = FinBERTSentimentAnalyzer(pipeline=pipeline, batch_size=2)
    results = analyzer.analyse_batch(["weak outlook", "strong growth"])
    assert [result.label for result in results] == ["Negative", "Positive"]
    assert analyzer.analyse_batch([]) == []
    with pytest.raises(ValueError, match="non-empty"):
        analyzer.analyse_batch([" ", ""])


def test_finbert_batch_rejects_incomplete_distribution() -> None:
    analyzer = FinBERTSentimentAnalyzer(
        pipeline=lambda *args, **kwargs: [[{"label": "positive", "score": 1.0}]]
    )
    with pytest.raises(RuntimeError, match="labels"):
        analyzer.analyse_batch(["text"])


def test_finbert_lazy_loader_honors_private_cache(monkeypatch) -> None:
    calls = []
    runtime = object()

    class Loader:
        @staticmethod
        def from_pretrained(model_id, *, cache_dir):
            calls.append((model_id, cache_dir))
            return f"loaded:{model_id}"

    transformers = SimpleNamespace(
        AutoModelForSequenceClassification=Loader,
        AutoTokenizer=Loader,
        pipeline=lambda **kwargs: runtime,
    )
    monkeypatch.setattr("aurum.sentiment.import_module", lambda _: transformers)
    analyzer = FinBERTSentimentAnalyzer(cache_dir="model_cache")
    assert analyzer._load() is runtime  # noqa: SLF001 - validates lazy model boundary
    assert calls == [
        ("ProsusAI/finbert", "model_cache"),
        ("ProsusAI/finbert", "model_cache"),
    ]

    monkeypatch.setattr(
        "aurum.sentiment.import_module",
        lambda _: SimpleNamespace(pipeline=lambda **kwargs: runtime),
    )
    assert FinBERTSentimentAnalyzer(device=-1)._load() is runtime  # noqa: SLF001


def test_finbert_accepts_nested_single_and_batch_schemas() -> None:
    distribution = [
        {"label": "positive", "score": 0.7},
        {"label": "negative", "score": 0.1},
        {"label": "neutral", "score": 0.2},
    ]
    single = FinBERTSentimentAnalyzer(pipeline=lambda *args, **kwargs: [distribution])
    assert single.analyse("growth").label == "Positive"
    batch = FinBERTSentimentAnalyzer(pipeline=lambda *args, **kwargs: [[distribution]])
    assert batch.analyse_batch(["growth"])[0].label == "Positive"


def test_backtest_lags_positions_and_charges_costs() -> None:
    result = evaluate_strategy(
        [0.01, -0.02, 0.015, 0.005],
        [1, 1, -1, -1],
        round_trip_bps=10,
        slippage_bps=5,
    )
    assert result.trading_cost > 0
    assert result.annualised_return_net < result.annualised_return_gross
    assert result.observations == 4


def test_backtest_rejects_misalignment() -> None:
    with pytest.raises(ValueError, match="align"):
        evaluate_strategy([0.1, 0.2], [1])


def test_risk_benchmark_liquidity_and_input_validation() -> None:
    values = np.linspace(100, 120, 40).tolist()
    benchmark = np.linspace(200, 210, 40).tolist()
    result = calculate_risk(values, benchmark_values=benchmark, bid_ask_bps=20)
    assert result.beta is not None
    assert result.liquidity_adjusted_var >= result.var_99_10d
    with pytest.raises(ValueError, match="positive"):
        calculate_risk([1.0] * 10 + [0.0])
    with pytest.raises(ValueError, match="11"):
        calculate_risk([1.0] * 10)


@pytest.mark.parametrize(
    ("inputs", "regime", "stance"),
    [
        (
            MacroInputs(real_growth=-1, inflation=1, inflation_trend=0, policy_rate_change=-1),
            "recessionary",
            "dovish",
        ),
        (
            MacroInputs(real_growth=1, inflation=2, inflation_trend=-1, policy_rate_change=0),
            "disinflationary expansion",
            "neutral",
        ),
        (
            MacroInputs(real_growth=1, inflation=2, inflation_trend=1, policy_rate_change=1),
            "expansionary",
            "hawkish",
        ),
    ],
)
def test_macro_regime_branches(inputs, regime, stance) -> None:
    result = classify_regime(inputs)
    assert (result.regime, result.monetary_stance) == (regime, stance)
