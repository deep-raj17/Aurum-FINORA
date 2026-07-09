"""FINORA API staging load profile."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from locust import HttpUser, between, task


def forecast_payload() -> dict[str, object]:
    start = datetime.now(UTC) - timedelta(days=121)
    return {
        "target": "LOAD_TEST",
        "values": [100 + index * 0.1 for index in range(120)],
        "dates": [(start + timedelta(days=index)).date().isoformat() for index in range(120)],
        "horizon": 5,
        "frequency": "daily",
        "forecast_start": datetime.now(UTC).isoformat(),
    }


class FinoraUser(HttpUser):
    wait_time = between(0.1, 1.0)

    def on_start(self) -> None:
        api_key = os.getenv("AURUM_API_KEY")
        self.headers = {"X-API-Key": api_key} if api_key else {}

    @task(5)
    def health(self) -> None:
        self.client.get("/health", name="/health")

    @task(2)
    def forecast(self) -> None:
        with self.client.post(
            "/v1/forecast",
            json=forecast_payload(),
            headers=self.headers,
            name="/v1/forecast",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status {response.status_code}")
