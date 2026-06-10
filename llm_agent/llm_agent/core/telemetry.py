from __future__ import annotations

import os
from typing import Any

import fastapi
from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_TELEMETRY_CONFIGURED = False
_HTTPX_INSTRUMENTED = False


def instrument_for_telemetry(app: fastapi.FastAPI) -> None:
    configure_telemetry()
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=trace.get_tracer_provider(),
        meter_provider=metrics.get_meter_provider(),
        http_capture_headers_server_request=[
            "traceparent",
            "tracestate",
            "x-correlation-id",
            "x-request-id",
        ],
        http_capture_headers_sanitize_fields=[
            "authorization",
            "cookie",
            "set-cookie",
            "x-api-key",
        ],
        exclude_spans=["receive", "send"],
    )


def configure_telemetry() -> None:
    global _TELEMETRY_CONFIGURED, _HTTPX_INSTRUMENTED

    if not _TELEMETRY_CONFIGURED:
        resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "movie-agent-worker"),
            }
        )

        tracer_provider = TracerProvider(resource=resource)
        meter_provider = _create_meter_provider(resource)
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])

        trace.set_tracer_provider(tracer_provider)
        metrics.set_meter_provider(meter_provider)
        _TELEMETRY_CONFIGURED = True

    if not _HTTPX_INSTRUMENTED:
        HTTPXClientInstrumentor().instrument()
        _HTTPX_INSTRUMENTED = True


def _create_meter_provider(resource: Resource) -> MeterProvider:
    return MeterProvider(resource=resource)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    return metrics.get_meter(name)


def get_current_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return f"{span_context.trace_id:032x}"


def get_current_traceparent() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    trace_id = f"{span_context.trace_id:032x}"
    span_id = f"{span_context.span_id:016x}"
    trace_flags = int(span_context.trace_flags)
    return f"00-{trace_id}-{span_id}-{trace_flags:02x}"


def set_span_attributes(span: trace.Span, attributes: dict[str, Any]) -> None:
    if span is None or not span.is_recording():
        return

    for name, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, (str, bool, int, float)):
            span.set_attribute(name, value)
