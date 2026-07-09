from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from aurum.forecast_system import (
    Chronos2Specialist,
    ForecastDistribution,
    NeuralForecastSpecialist,
    ProductionForecastEngine,
    TreeQuantileSpecialist,
    classify_volatility_regime,
)


class LinearEstimator:
    def __init__(self, quantile: float) -> None:
        self.quantile = quantile
        self.feature_importances_: np.ndarray | None = None

    def fit(self, features: np.ndarray, target: np.ndarray) -> None:
        self.value = float(np.quantile(target, self.quantile))
        self.feature_importances_ = np.ones(features.shape[1])

    def predict(self, features: np.ndarray) -> np.ndarray:
        return np.array([self.value])


def series(length: int = 100) -> tuple[np.ndarray, list[date]]:
    values = np.linspace(10, 20, length) + np.sin(np.arange(length) / 5)
    dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(length)]
    return values, dates


def test_tree_specialist_trains_real_estimators_and_returns_ordered_quantiles() -> None:
    values, dates = series()
    specialist = TreeQuantileSpecialist(
        "xgboost", lags=10, estimator_factory=lambda quantile: LinearEstimator(quantile)
    )
    result = specialist.forecast(values, dates, 3)
    assert result.mean.shape == (3,)
    assert np.all(result.quantiles[0.1] <= result.quantiles[0.9])
    assert result.metadata["feature_importance"]


class ChronosPipeline:
    def predict_df(self, frame: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
        assert kwargs["prediction_length"] == 2
        assert len(frame) == 100
        return pd.DataFrame(
            {
                "predictions": [20.0, 20.1],
                "0.1": [19.0, 19.1],
                "0.5": [20.0, 20.1],
                "0.9": [21.0, 21.1],
            }
        )


def test_chronos_adapter_validates_external_schema() -> None:
    values, dates = series()
    result = Chronos2Specialist(pipeline=ChronosPipeline()).forecast(values, dates, 2)
    assert result.model == "chronos-2"
    assert result.quantiles[0.9][-1] == 21.1


class ChronosSamplePipeline:
    def predict(self, context, **kwargs):
        assert kwargs["prediction_length"] == 2
        assert context.shape == (100,)
        samples = np.tile(np.array([[20.0, 20.2]]), (50, 1))
        return [samples]


def test_chronos_t5_sample_adapter() -> None:
    values, dates = series()
    result = Chronos2Specialist(
        model_id="amazon/chronos-t5-tiny", pipeline=ChronosSamplePipeline()
    ).forecast(values, dates, 2)
    assert result.mean.tolist() == pytest.approx([20.0, 20.2])


class TrendSpecialist:
    def __init__(self, name: str, bias: float) -> None:
        self.name = name
        self.bias = bias

    def forecast(self, values: np.ndarray, dates: list[date], horizon: int) -> ForecastDistribution:
        slope = float(np.mean(np.diff(values[-10:])))
        mean = values[-1] + slope * np.arange(1, horizon + 1) + self.bias
        return ForecastDistribution(
            model=self.name,
            mean=mean,
            quantiles={0.1: mean - 0.5, 0.5: mean, 0.9: mean + 0.5},
            metadata={},
        )


def test_production_engine_selects_and_calibrates_walk_forward() -> None:
    values, dates = series(140)
    result, scores = ProductionForecastEngine(
        [TrendSpecialist("accurate", 0), TrendSpecialist("biased", 5)],
        minimum_train_size=50,
        validation_windows=5,
    ).forecast(values, dates, 2)
    assert result.model == "accurate"
    assert scores[0].rmse < scores[1].rmse
    assert result.metadata["conformal_absolute_error_80"] >= 0
    assert np.all(result.quantiles[0.1] <= result.mean)


def test_distribution_and_input_validation_fail_closed() -> None:
    with pytest.raises(ValueError, match="cross"):
        ForecastDistribution(
            model="bad",
            mean=np.array([1.0]),
            quantiles={0.1: np.array([2.0]), 0.9: np.array([1.0])},
            metadata={},
        )
    values, dates = series(60)
    with pytest.raises(ValueError, match="at least"):
        TreeQuantileSpecialist(
            "lightgbm", lags=50, estimator_factory=lambda quantile: LinearEstimator(quantile)
        ).forecast(values, dates, 2)


def test_volatility_regime_is_explicit() -> None:
    assert classify_volatility_regime(np.arange(10.0)) == "insufficient-history"


def test_neuralforecast_adapter_trains_and_parses_quantiles(monkeypatch) -> None:
    values, dates = series(120)

    class Losses:
        @staticmethod
        def MQLoss(level):
            return ("mqloss", level)

    monkeypatch.setattr(
        "aurum.forecast_system.import_module",
        lambda name: Losses if name == "neuralforecast.losses.pytorch" else None,
    )

    class Forecast:
        def __init__(self, models, freq):
            assert models and freq

        def fit(self, df, val_size):
            assert len(df) == 120 and val_size > 0

        def predict(self):
            return pd.DataFrame(
                {
                    "unique_id": ["series", "series"],
                    "ds": [dates[-1], dates[-1]],
                    "patchtst-median": [20.0, 20.1],
                    "patchtst-lo-80": [19.0, 19.1],
                    "patchtst-hi-80": [21.0, 21.1],
                }
            )

    specialist = NeuralForecastSpecialist(
        "patchtst",
        input_size=20,
        model_factory=lambda **kwargs: kwargs,
        forecast_factory=Forecast,
    )
    result = specialist.forecast(values, dates, 2)
    assert result.mean.tolist() == [20.0, 20.1]
    assert result.metadata["architecture"] == "PatchTST"


def test_tree_specialist_uses_lazy_runtime(monkeypatch) -> None:
    class XGB(LinearEstimator):
        def __init__(self, quantile_alpha, **kwargs):
            super().__init__(quantile_alpha)

    monkeypatch.setattr(
        "aurum.forecast_system.import_module",
        lambda name: type("Module", (), {"XGBRegressor": XGB}),
    )
    specialist = TreeQuantileSpecialist("xgboost", lags=10)
    estimator = specialist._estimator(0.5)
    assert estimator.quantile == 0.5


def test_catboost_and_new_neural_experts_are_registered(monkeypatch) -> None:
    class Cat:
        def __init__(self, loss_function, **kwargs):
            self.loss_function = loss_function

    monkeypatch.setattr(
        "aurum.forecast_system.import_module",
        lambda name: type("Module", (), {"CatBoostRegressor": Cat}),
    )
    estimator = TreeQuantileSpecialist("catboost", lags=10)._estimator(0.9)
    assert estimator.loss_function == "Quantile:alpha=0.9"
    assert NeuralForecastSpecialist.SUPPORTED["itransformer"] == "iTransformer"
    assert NeuralForecastSpecialist.SUPPORTED["tide"] == "TiDE"
