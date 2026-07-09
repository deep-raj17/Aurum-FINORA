"""Prometheus metrics, JSON logging, and OpenTelemetry initialization."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from importlib import import_module
from typing import Any

request_id_context: ContextVar[str] = ContextVar("request_id", default="")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        for key in ("model", "endpoint", "duration_seconds", "status_code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_json_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class FinoraMetrics:
    def __init__(self, registry: Any | None = None) -> None:
        prometheus = import_module("prometheus_client")
        self.registry = registry or prometheus.REGISTRY
        self.requests = prometheus.Counter(
            "finora_http_requests_total",
            "HTTP requests",
            ("method", "route", "status"),
            registry=self.registry,
        )
        self.latency = prometheus.Histogram(
            "finora_http_request_duration_seconds",
            "HTTP request latency",
            ("method", "route"),
            registry=self.registry,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        )
        self.inference_latency = prometheus.Histogram(
            "finora_model_inference_duration_seconds",
            "Model inference latency",
            ("model",),
            registry=self.registry,
        )
        self.drift = prometheus.Gauge(
            "finora_drift_score",
            "Latest drift score by kind",
            ("kind", "target"),
            registry=self.registry,
        )
        self.gpu_memory = prometheus.Gauge(
            "finora_gpu_memory_bytes",
            "Allocated GPU memory",
            ("device",),
            registry=self.registry,
        )

    @contextmanager
    def observe_inference(self, model: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.inference_latency.labels(model=model).observe(time.perf_counter() - started)

    def update_gpu(self) -> None:
        try:
            torch = import_module("torch")
        except ImportError:
            return
        if not torch.cuda.is_available():
            return
        for index in range(torch.cuda.device_count()):
            self.gpu_memory.labels(device=str(index)).set(torch.cuda.memory_allocated(index))

    def render(self) -> tuple[bytes, str]:
        prometheus = import_module("prometheus_client")
        return prometheus.generate_latest(self.registry), prometheus.CONTENT_TYPE_LATEST


def configure_opentelemetry(
    app: Any,
    *,
    service_name: str,
    endpoint: str,
    environment: str,
) -> Any:
    """Configure OTLP tracing and instrument FastAPI; returns the tracer provider."""
    resources = import_module("opentelemetry.sdk.resources")
    trace_sdk = import_module("opentelemetry.sdk.trace")
    export = import_module("opentelemetry.sdk.trace.export")
    exporter = import_module("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
    instrumentation = import_module("opentelemetry.instrumentation.fastapi")
    trace = import_module("opentelemetry.trace")
    resource = resources.Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": environment,
        }
    )
    provider = trace_sdk.TracerProvider(resource=resource)
    provider.add_span_processor(
        export.BatchSpanProcessor(exporter.OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)
    instrumentation.FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    return provider
