import json
import logging

import pytest

from aurum.observability import (
    FinoraMetrics,
    JSONFormatter,
    configure_json_logging,
    configure_opentelemetry,
    request_id_context,
)


def test_json_formatter_includes_request_context() -> None:
    token = request_id_context.set("request-1")
    try:
        record = logging.LogRecord("finora", logging.INFO, "", 1, "hello", (), None)
        output = json.loads(JSONFormatter().format(record))
    finally:
        request_id_context.reset(token)
    assert output["request_id"] == "request-1"
    assert output["message"] == "hello"


def test_prometheus_metrics_render_latency_and_drift() -> None:
    prometheus = pytest.importorskip("prometheus_client")
    metrics = FinoraMetrics(prometheus.CollectorRegistry())
    metrics.requests.labels(method="GET", route="/health", status="200").inc()
    with metrics.observe_inference("finora"):
        pass
    metrics.drift.labels(kind="feature", target="returns").set(0.3)
    body, content_type = metrics.render()
    assert b"finora_http_requests_total" in body
    assert b"finora_drift_score" in body
    assert "text/plain" in content_type


def test_logging_configuration_and_gpu_metrics(monkeypatch) -> None:
    old_handlers = logging.getLogger().handlers
    try:
        configure_json_logging("WARNING")
        assert logging.getLogger().level == logging.WARNING
    finally:
        logging.getLogger().handlers = old_handlers
    prometheus = pytest.importorskip("prometheus_client")
    metrics = FinoraMetrics(prometheus.CollectorRegistry())

    class Cuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def device_count():
            return 1

        @staticmethod
        def memory_allocated(index):
            return 123

    monkeypatch.setattr(
        "aurum.observability.import_module",
        lambda name: type("Torch", (), {"cuda": Cuda}) if name == "torch" else prometheus,
    )
    metrics.update_gpu()
    assert b'finora_gpu_memory_bytes{device="0"} 123.0' in metrics.render()[0]


def test_opentelemetry_wires_provider_exporter_and_fastapi(monkeypatch) -> None:
    calls = []

    class Resource:
        @staticmethod
        def create(values):
            calls.append(("resource", values))
            return values

    class Provider:
        def __init__(self, resource):
            self.resource = resource

        def add_span_processor(self, processor):
            calls.append(("processor", processor))

    class Exporter:
        def __init__(self, endpoint):
            self.endpoint = endpoint

    class Processor:
        def __init__(self, exporter):
            self.exporter = exporter

    modules = {
        "opentelemetry.sdk.resources": type("M", (), {"Resource": Resource}),
        "opentelemetry.sdk.trace": type("M", (), {"TracerProvider": Provider}),
        "opentelemetry.sdk.trace.export": type("M", (), {"BatchSpanProcessor": Processor}),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": type(
            "M", (), {"OTLPSpanExporter": Exporter}
        ),
        "opentelemetry.instrumentation.fastapi": type(
            "M",
            (),
            {
                "FastAPIInstrumentor": type(
                    "I",
                    (),
                    {
                        "instrument_app": staticmethod(
                            lambda app, tracer_provider: calls.append(("app", app))
                        )
                    },
                )
            },
        ),
        "opentelemetry.trace": type(
            "M",
            (),
            {
                "set_tracer_provider": staticmethod(
                    lambda provider: calls.append(("provider", provider))
                )
            },
        ),
    }
    monkeypatch.setattr("aurum.observability.import_module", modules.__getitem__)
    provider = configure_opentelemetry(
        object(), service_name="finora", endpoint="collector:4317", environment="test"
    )
    assert isinstance(provider, Provider)
    assert {item[0] for item in calls} >= {"resource", "processor", "provider", "app"}
