"""Streamlit operations console for FINORA and FINORA-KD-Q."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install aurum-finora[ui] to launch the console") from exc


def call_api(base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("AURUM_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> None:
    st.set_page_config(page_title="FINORA", page_icon="◈", layout="wide")
    st.title("FINORA Financial Intelligence")
    st.caption("Auditable probabilistic analytics and FINORA-KD-Q inference")
    base_url = st.sidebar.text_input(
        "API URL", os.getenv("FINORA_API_URL", "http://localhost:8000")
    )
    try:
        health = call_api(base_url, "/health")
        st.sidebar.success(f"API healthy · audit chain: {health['audit_chain_valid']}")
    except (HTTPError, URLError, TimeoutError) as exc:
        st.sidebar.error(f"API unavailable: {exc}")
    sentiment_tab, macro_tab, kdq_tab = st.tabs(["Sentiment", "Macro regime", "FINORA-KD-Q"])
    with sentiment_tab:
        text = st.text_area("Financial text", "Revenue growth improved and guidance was raised.")
        if st.button("Analyse sentiment"):
            st.json(call_api(base_url, "/v1/sentiment", {"text": text}))
    with macro_tab:
        left, right = st.columns(2)
        growth = left.number_input("Real growth", value=2.0)
        inflation = right.number_input("Inflation", value=2.5)
        trend = left.number_input("Inflation trend", value=-0.1)
        rate_change = right.number_input("Policy-rate change", value=0.0)
        if st.button("Classify regime"):
            st.json(
                call_api(
                    base_url,
                    "/v1/macro-regime",
                    {
                        "real_growth": growth,
                        "inflation": inflation,
                        "inflation_trend": trend,
                        "policy_rate_change": rate_change,
                    },
                )
            )
    with kdq_tab:
        st.info("Deploy a validated artifact and set FINORA_KDQ_ARTIFACT before inference.")
        payload = st.text_area(
            "KD-Q request JSON",
            json.dumps(
                {
                    "time_series": [[0.0] * 6 for _ in range(64)],
                    "text": "grounded financial evidence",
                    "tabular": [0.0] * 24,
                    "evidence_ids": [],
                },
                indent=2,
            ),
            height=320,
        )
        if st.button("Run KD-Q inference"):
            try:
                st.json(call_api(base_url, "/v1/kdq/predict", json.loads(payload)))
            except (json.JSONDecodeError, HTTPError, URLError, TimeoutError) as exc:
                st.error(str(exc))


if __name__ == "__main__":
    main()
