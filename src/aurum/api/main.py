"""Optional FastAPI entrypoint."""

from __future__ import annotations

import hmac
import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
except ImportError as exc:  # pragma: no cover - exercised only without serve extra
    raise RuntimeError("Install aurum-finora[serve] to run the API") from exc

from pydantic import BaseModel, Field

from aurum.backtest import BacktestResult, evaluate_strategy
from aurum.config import Settings
from aurum.governance import GovernanceError
from aurum.graph import Edge, EntityGraph
from aurum.kdq.contracts import KDQInferenceRequest, KDQPrediction
from aurum.macro import MacroAssessment, MacroInputs, classify_regime
from aurum.models import AnalysisReport, ForecastRequest
from aurum.monitoring import DriftReport, detect_drift
from aurum.observability import FinoraMetrics, request_id_context
from aurum.retrieval import Document
from aurum.security import SlidingWindowRateLimiter
from aurum.sentiment import (
    FilingComparison,
    FinBERTSentimentAnalyzer,
    SentimentResult,
    analyse_sentiment,
    compare_filings,
)
from aurum.service import FinoraService

app = FastAPI(title="Aurum / FINORA", version="1.1.0")
settings = Settings.from_yaml("config/settings.yaml")
service = FinoraService(settings)
metrics = FinoraMetrics()
rate_limiter = SlidingWindowRateLimiter(requests=120, window_seconds=60)
logger = logging.getLogger(__name__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def operational_controls(request: Request, call_next: Any) -> Response:
    request_id = request.headers.get("x-request-id", "")
    if not request_id or len(request_id) > 128 or any(char.isspace() for char in request_id):
        request_id = str(uuid4())
    token = request_id_context.set(request_id)
    started = time.perf_counter()
    client_key = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.allow(client_key)
    if not allowed:
        response = Response(
            '{"detail":"rate limit exceeded"}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(max(1, int(retry_after)))},
        )
    else:
        response = await call_next(request)
    duration = time.perf_counter() - started
    route = getattr(request.scope.get("route"), "path", request.url.path)
    metrics.requests.labels(
        method=request.method, route=route, status=str(response.status_code)
    ).inc()
    metrics.latency.labels(method=request.method, route=route).observe(duration)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request completed",
        extra={
            "endpoint": route,
            "duration_seconds": duration,
            "status_code": response.status_code,
        },
    )
    request_id_context.reset(token)
    return response


@lru_cache(maxsize=2)
def load_kdq_predictor(path: str) -> Any:
    from aurum.kdq.inference import KDQPredictor

    return KDQPredictor(path)


@lru_cache(maxsize=1)
def load_sentiment_analyzer(model_id: str) -> FinBERTSentimentAnalyzer:
    return FinBERTSentimentAnalyzer(model_id)


def authorize(x_api_key: str | None = Header(default=None)) -> None:
    if settings.api_key and (
        x_api_key is None or not hmac.compare_digest(x_api_key, settings.api_key)
    ):
        raise HTTPException(status_code=401, detail="invalid API key")


class AnalyseRequest(ForecastRequest):
    evidence_query: str | None = None


class BacktestRequest(BaseModel):
    values: list[float] = Field(min_length=3)
    positions: list[float] = Field(min_length=2)
    round_trip_bps: float = 10
    slippage_bps: float = 5


class DriftRequest(BaseModel):
    reference: list[float] = Field(min_length=20)
    current: list[float] = Field(min_length=10)


class SentimentRequest(BaseModel):
    text: str


class FilingRequest(BaseModel):
    current_text: str
    prior_text: str


class ContagionRequest(BaseModel):
    source: str
    target: str
    edges: list[Edge]


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "mode": "decision-support",
        "audit_chain_valid": service.repository.verify_audit_chain(),
    }


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    body, content_type = metrics.render()
    return Response(body, media_type=content_type)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """<!doctype html><html><head><title>FINORA</title>
    <style>body{font:16px system-ui;max-width:900px;margin:5rem auto;padding:0 2rem;
    background:#07111f;color:#dce8f5}h1{color:#d6ad60}.card{padding:1.5rem;
    border:1px solid #27415f;border-radius:12px;background:#0d1b2d}code{color:#8ee3cf}</style>
    </head><body><h1>FINORA</h1><div class="card"><h2>Financial Intelligence API</h2>
    <p>Auditable forecasts, evidence grounding, risk, scenarios, and monitoring.</p>
    <p>Open <a href="/docs">interactive API documentation</a> or check
    <code>/health</code>.</p></div></body></html>"""


@app.post("/v1/forecast", response_model=AnalysisReport)
def forecast(request: AnalyseRequest, _: None = Depends(authorize)) -> AnalysisReport:
    try:
        return service.analyse(request, request.evidence_query)
    except (ValueError, GovernanceError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/evidence", status_code=201)
def add_evidence(document: Document, _: None = Depends(authorize)) -> dict[str, str]:
    service.add_evidence(document)
    return {"status": "indexed"}


@app.get("/v1/reports")
def list_reports(_: None = Depends(authorize)) -> list[dict[str, str]]:
    return service.repository.list_reports()


@app.get("/v1/reports/{run_id}")
def get_report(run_id: str, _: None = Depends(authorize)) -> AnalysisReport:
    report = service.repository.get_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@app.get("/v1/reports/{run_id}/markdown")
def markdown_report(run_id: str, _: None = Depends(authorize)) -> Response:
    report = service.markdown_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return Response(report, media_type="text/markdown")


@app.post("/v1/backtest", response_model=BacktestResult)
def backtest(request: BacktestRequest, _: None = Depends(authorize)) -> BacktestResult:
    returns = [
        request.values[index] / request.values[index - 1] - 1
        for index in range(1, len(request.values))
    ]
    if len(request.positions) not in {len(returns), len(request.values)}:
        raise HTTPException(status_code=422, detail="positions must align with values or returns")
    positions = request.positions[-len(returns) :]
    return evaluate_strategy(
        returns,
        positions,
        round_trip_bps=request.round_trip_bps,
        slippage_bps=request.slippage_bps,
    )


@app.post("/v1/drift", response_model=DriftReport)
def drift(request: DriftRequest, _: None = Depends(authorize)) -> DriftReport:
    return detect_drift(request.reference, request.current)


@app.post("/v1/sentiment", response_model=SentimentResult)
def sentiment(request: SentimentRequest, _: None = Depends(authorize)) -> SentimentResult:
    if settings.sentiment_backend == "finbert":
        return load_sentiment_analyzer(settings.sentiment_model_id).analyse(request.text)
    return analyse_sentiment(request.text)


@app.post("/v1/filing-compare", response_model=FilingComparison)
def filing_compare(request: FilingRequest, _: None = Depends(authorize)) -> FilingComparison:
    return compare_filings(request.current_text, request.prior_text)


@app.post("/v1/macro-regime", response_model=MacroAssessment)
def macro_regime(request: MacroInputs, _: None = Depends(authorize)) -> MacroAssessment:
    return classify_regime(request)


@app.post("/v1/contagion")
def contagion(
    request: ContagionRequest, _: None = Depends(authorize)
) -> dict[str, str | list[tuple[str, int]]]:
    graph = EntityGraph(request.edges)
    return {
        "path": graph.describe_path(request.source, request.target),
        "critical_nodes": graph.critical_nodes(),
    }


@app.post("/v1/kdq/predict", response_model=KDQPrediction)
def kdq_predict(request: KDQInferenceRequest, _: None = Depends(authorize)) -> KDQPrediction:
    artifact = Path(os.getenv("FINORA_KDQ_ARTIFACT", "artifacts/finora-kdq"))
    if not (artifact / "manifest.json").exists():
        raise HTTPException(status_code=503, detail="FINORA-KD-Q artifact is not deployed")
    try:
        predictor = load_kdq_predictor(str(artifact))
        return predictor.predict(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
