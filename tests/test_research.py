from datetime import UTC, datetime, timedelta

import pytest

from aurum.data.contracts import AssetClass, MarketBar
from aurum.research import market_dataset_hash, research_version, validate_and_frame_bars


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
