import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from aurum.data.contracts import AssetClass, MarketBar
from aurum.research import (
    ExperimentMetrics,
    ExperimentSpec,
    ResearchDecision,
    ResearchExperiment,
    ResearchRegistry,
    decide_experiment,
    experiment_id,
    market_dataset_hash,
    research_version,
    validate_and_frame_bars,
)


def bars(count: int = 40) -> list[MarketBar]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        MarketBar(
            symbol="TEST",
            timestamp=start + timedelta(days=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100.5 + index,
            volume=1000 + index,
            asset_class=AssetClass.EQUITY,
            source="controlled",
        )
        for index in range(count)
    ]


def test_research_features_and_hash_are_deterministic() -> None:
    observations = bars()
    frame = validate_and_frame_bars(observations)
    assert {"return_1d", "volatility_20d", "momentum_20d", "volume_zscore_20d"} <= set(
        frame.columns
    )
    assert market_dataset_hash(observations) == market_dataset_hash(list(reversed(observations)))
    assert research_version("test", "ABC", observations[0].timestamp).startswith("test:ABC:")


def test_research_bar_validation_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="at least 30"):
        validate_and_frame_bars(bars(2))
    observations = bars()
    observations[1] = observations[1].model_copy(update={"timestamp": observations[0].timestamp})
    with pytest.raises(ValueError, match="duplicate"):
        validate_and_frame_bars(observations)
    bad_price = bars()
    bad_price[0] = bad_price[0].model_copy(update={"open": -1})
    with pytest.raises(ValueError, match="positive"):
        validate_and_frame_bars(bad_price)

    bad_high = bars()
    bad_high[0] = bad_high[0].model_copy(update={"high": 50})
    with pytest.raises(ValueError, match="high price"):
        validate_and_frame_bars(bad_high)

    bad_low = bars()
    bad_low[0] = bad_low[0].model_copy(update={"low": 150})
    with pytest.raises(ValueError, match="low price"):
        validate_and_frame_bars(bad_low)

    bad_volume = bars()
    bad_volume[0] = bad_volume[0].model_copy(update={"volume": -1})
    with pytest.raises(ValueError, match="volume"):
        validate_and_frame_bars(bad_volume)


def experiment_spec() -> ExperimentSpec:
    return ExperimentSpec(
        hypothesis="20 day momentum improves risk-adjusted returns",
        dataset_version="yahoo:research-v1",
        feature_version="technical-v1",
        model_version="xgboost-v1",
        training_period="2010-01-01/2024-12-31",
        testing_period="2025-01-01/2026-06-30",
        validation_methodology="expanding walk-forward",
        assets=["AAPL", "MSFT"],
        regimes=["bull", "bear"],
    )


def test_experiment_id_is_deterministic() -> None:
    spec = experiment_spec()
    assert experiment_id(spec) == experiment_id(spec.model_copy())


def test_decision_rule_rejects_weak_research_signal() -> None:
    conclusion = decide_experiment(
        ExperimentMetrics(
            observations=30,
            strategy_return=-0.04,
            buy_hold_return=0.10,
            random_return=0.0,
            sharpe_net=-0.5,
            max_drawdown=-0.25,
            bootstrap_p_value=0.80,
        ),
        assets=["AAPL"],
        regimes=["bull"],
    )
    assert conclusion.decision is ResearchDecision.REJECT
    assert "strategy does not beat buy and hold" in conclusion.reasons
    assert "strategy has not survived multiple assets" in conclusion.reasons


def test_decision_rule_accepts_signal_only_after_all_gates_pass() -> None:
    conclusion = decide_experiment(
        ExperimentMetrics(
            observations=504,
            strategy_return=0.18,
            buy_hold_return=0.10,
            random_return=0.0,
            sharpe_net=1.2,
            max_drawdown=-0.12,
            bootstrap_p_value=0.02,
            deflated_sharpe=0.8,
            probability_backtest_overfit=0.05,
            white_reality_check_p_value=0.03,
            spa_p_value=0.04,
        ),
        assets=["AAPL", "MSFT"],
        regimes=["bull", "bear"],
    )
    assert conclusion.decision is ResearchDecision.ACCEPT


def test_decision_rule_keeps_missing_tests_inconclusive() -> None:
    conclusion = decide_experiment(
        ExperimentMetrics(
            observations=504,
            strategy_return=0.18,
            buy_hold_return=0.10,
            random_return=0.0,
            sharpe_net=1.2,
            max_drawdown=-0.12,
            bootstrap_p_value=0.02,
        ),
        assets=["AAPL", "MSFT"],
        regimes=["bull", "bear"],
    )
    assert conclusion.decision is ResearchDecision.INCONCLUSIVE
    assert "White Reality Check not computed" in conclusion.limitations


def test_research_registry_is_append_only(tmp_path) -> None:
    spec = experiment_spec()
    metrics = ExperimentMetrics(
        observations=30,
        strategy_return=-0.04,
        buy_hold_return=0.10,
        random_return=0.0,
        sharpe_net=-0.5,
        max_drawdown=-0.25,
        bootstrap_p_value=0.80,
    )
    experiment = ResearchExperiment(
        experiment_id=experiment_id(spec),
        created_at=datetime(2026, 7, 9, tzinfo=UTC),
        spec=spec,
        metrics=metrics,
        conclusion=decide_experiment(metrics, assets=spec.assets, regimes=spec.regimes),
    )
    registry = ResearchRegistry(tmp_path / "experiments.sqlite3")

    digest = registry.save(experiment)

    assert len(digest) == 64
    assert registry.get(experiment.experiment_id) == experiment
    assert registry.list()[0]["decision"] == ResearchDecision.REJECT.value
    with pytest.raises(sqlite3.IntegrityError):
        registry.save(experiment)
