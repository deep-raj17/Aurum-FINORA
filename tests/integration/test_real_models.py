"""Real weight/runtime validation; never substitutes smoke outputs."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

import numpy as np
import pytest

from aurum.forecast_system import (
    Chronos2Specialist,
    NeuralForecastSpecialist,
    TreeQuantileSpecialist,
)
from aurum.llm import Evidence, FinancialReasoningRequest, GPTOSSClient
from aurum.sentiment import FinBERTSentimentAnalyzer

pytestmark = pytest.mark.model


def _enabled() -> None:
    if os.getenv("FINORA_RUN_MODEL_TESTS") != "1":
        pytest.skip("set FINORA_RUN_MODEL_TESTS=1 to load production model weights")


def _series(length: int = 160) -> tuple[np.ndarray, list[date]]:
    values = 100 * np.exp(np.cumsum(np.random.default_rng(17).normal(0, 0.01, length)))
    dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(length)]
    return values, dates


def test_chronos_real_weights() -> None:
    _enabled()
    values, dates = _series()
    model_id = os.getenv("FINORA_CHRONOS_MODEL_ID", "amazon/chronos-t5-tiny")
    result = Chronos2Specialist(
        model_id=model_id, cache_dir=os.getenv("FINORA_MODEL_CACHE_DIR")
    ).forecast(values, dates, 3)
    assert result.mean.shape == (3,) and np.all(np.isfinite(result.mean))


@pytest.mark.parametrize(
    "architecture",
    ["patchtst", "itransformer", "tft", "tide", "nhits"],
)
def test_neuralforecast_real_training(architecture) -> None:
    _enabled()
    values, dates = _series()
    result = NeuralForecastSpecialist(architecture, input_size=30, max_steps=20).forecast(
        values, dates, 2
    )
    assert result.mean.shape == (2,) and np.all(np.isfinite(result.mean))


@pytest.mark.parametrize("engine", ["xgboost", "lightgbm", "catboost"])
def test_tree_quantile_real_training(engine) -> None:
    _enabled()
    values, dates = _series()
    result = TreeQuantileSpecialist(engine, lags=20).forecast(values, dates, 2)
    assert np.all(result.quantiles[0.1] <= result.quantiles[0.9])


def test_finbert_real_weights() -> None:
    _enabled()
    result = FinBERTSentimentAnalyzer(
        os.getenv("FINORA_FINBERT_MODEL_ID", "ProsusAI/finbert"),
        cache_dir=os.getenv("FINORA_MODEL_CACHE_DIR"),
    ).analyse("Revenue and earnings exceeded expectations.")
    assert result.model and 0 <= result.probability <= 1


def test_gpt_oss_self_hosted_endpoint() -> None:
    _enabled()
    endpoint = os.getenv("FINORA_LLM_ENDPOINT")
    if not endpoint:
        pytest.skip("GPT_OSS_ENDPOINT is not configured")
    client = GPTOSSClient(
        endpoint,
        model=os.getenv("FINORA_LLM_MODEL_ID", "openai/gpt-oss-120b"),
        api_token=os.getenv("FINORA_LLM_API_TOKEN"),
    )
    response = client.reason(
        FinancialReasoningRequest(
            question="Summarize the disclosed revenue change.",
            evidence=[
                Evidence(
                    evidence_id="validation:1",
                    source="controlled validation",
                    published_at="2025-01-01",
                    excerpt="Revenue increased 10% year over year.",
                )
            ],
            computed_metrics={"revenue_growth": 0.1},
        )
    )
    assert response.requires_human_review
    assert json.loads(response.model_dump_json())["claims"]
