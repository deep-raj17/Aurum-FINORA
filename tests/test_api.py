import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from aurum.api.main import app  # noqa: E402

client = TestClient(app)


def test_health_and_dashboard() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "FINORA" in dashboard.text


def test_sentiment_and_drift_contracts() -> None:
    sentiment = client.post("/v1/sentiment", json={"text": "Strong profit growth"})
    assert sentiment.status_code == 200
    assert sentiment.json()["label"] == "Positive"
    drift = client.post(
        "/v1/drift",
        json={"reference": list(range(30)), "current": list(range(100, 110))},
    )
    assert drift.status_code == 200
    assert drift.json()["drift_detected"] is True


def test_backtest_rejects_bad_position_alignment() -> None:
    response = client.post(
        "/v1/backtest",
        json={"values": [100, 101, 102, 103], "positions": [1, 1]},
    )
    assert response.status_code == 422


def test_macro_filing_and_contagion_endpoints() -> None:
    macro = client.post(
        "/v1/macro-regime",
        json={
            "real_growth": -1,
            "inflation": 4,
            "inflation_trend": 0.2,
            "policy_rate_change": 0.5,
        },
    )
    assert macro.json()["regime"] == "stagflationary"
    filing = client.post(
        "/v1/filing-compare",
        json={
            "prior_text": "Strong profit growth",
            "current_text": "Weak outlook with litigation risk and loss",
        },
    )
    assert filing.json()["tone_divergence"] is True
    contagion = client.post(
        "/v1/contagion",
        json={
            "source": "A",
            "target": "C",
            "edges": [
                {
                    "source": "A",
                    "relationship": "funds",
                    "target": "B",
                    "mechanism": "liquidity",
                },
                {
                    "source": "B",
                    "relationship": "supplies",
                    "target": "C",
                    "mechanism": "shortage",
                },
            ],
        },
    )
    assert "A" in contagion.json()["path"]
