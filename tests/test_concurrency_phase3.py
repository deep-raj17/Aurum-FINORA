from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import numpy as np

from aurum.forecasting import ForecastEngine
from aurum.models import ForecastRequest
from aurum.reliability import CircuitBreaker


def _request() -> ForecastRequest:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    values = np.linspace(100, 120, 100).tolist()
    return ForecastRequest(
        target="CONCURRENT",
        values=values,
        dates=[start.date() - timedelta(days=100 - index) for index in range(100)],
        horizon=2,
        forecast_start=start,
    )


def test_concurrent_forecast_inference_is_deterministic() -> None:
    engine = ForecastEngine()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: engine.forecast(_request()), range(16)))
    assert len({result.model_dump_json() for result in results}) == 1


def test_vector_and_graph_failures_degrade_independently() -> None:
    qdrant = CircuitBreaker("qdrant", failure_threshold=1)
    neo4j = CircuitBreaker("neo4j", failure_threshold=1)
    vector_result = qdrant.call(
        lambda: (_ for _ in ()).throw(ConnectionError("vector db offline")),
        fallback=lambda exc: [],
    )
    graph_result = neo4j.call(
        lambda: (_ for _ in ()).throw(ConnectionError("graph db offline")),
        fallback=lambda exc: {"paths": []},
    )
    assert vector_result.degraded and vector_result.value == []
    assert graph_result.degraded and graph_result.value == {"paths": []}
