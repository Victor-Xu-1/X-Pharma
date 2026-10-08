from __future__ import annotations

import atexit
import threading
from dataclasses import dataclass

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_NAMESPACE, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.engine import Engine

from pharma_intel.config import Settings, get_settings
from pharma_intel.db import get_engine
from pharma_intel.product import PRODUCT_VERSION


@dataclass(frozen=True)
class TelemetryRuntime:
    tracer_provider: TracerProvider
    meter_provider: MeterProvider

    def shutdown(self) -> None:
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()


_lock = threading.Lock()
_runtime: TelemetryRuntime | None = None
_instrumented_apps: set[int] = set()


def initialize_telemetry(
    service_name: str,
    *,
    settings: Settings | None = None,
    engine: Engine | None = None,
) -> TelemetryRuntime | None:
    global _runtime
    runtime_settings = settings or get_settings()
    if not runtime_settings.otel_enabled:
        return None
    with _lock:
        if _runtime is not None:
            return _runtime
        resource = Resource.create(
            {
                SERVICE_NAME: service_name,
                SERVICE_NAMESPACE: "pharma-intelligence",
                "deployment.environment.name": runtime_settings.app_env,
                "service.version": PRODUCT_VERSION,
            }
        )
        span_exporter = OTLPSpanExporter(
            endpoint=runtime_settings.otel_exporter_otlp_endpoint,
            insecure=runtime_settings.otel_exporter_otlp_insecure,
        )
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        metric_exporter = OTLPMetricExporter(
            endpoint=runtime_settings.otel_exporter_otlp_endpoint,
            insecure=runtime_settings.otel_exporter_otlp_insecure,
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[
                PeriodicExportingMetricReader(
                    metric_exporter,
                    export_interval_millis=runtime_settings.otel_metric_export_interval_ms,
                )
            ],
        )
        trace.set_tracer_provider(tracer_provider)
        metrics.set_meter_provider(meter_provider)
        HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)
        SQLAlchemyInstrumentor().instrument(engine=engine or get_engine(), tracer_provider=tracer_provider)
        LoggingInstrumentor().instrument(set_logging_format=False, tracer_provider=tracer_provider)
        _runtime = TelemetryRuntime(tracer_provider=tracer_provider, meter_provider=meter_provider)
        atexit.register(_runtime.shutdown)
        return _runtime


def instrument_fastapi(app: FastAPI, service_name: str) -> None:
    runtime = initialize_telemetry(service_name)
    if runtime is None:
        return
    with _lock:
        app_identity = id(app)
        if app_identity in _instrumented_apps:
            return
        FastAPIInstrumentor.instrument_app(app, tracer_provider=runtime.tracer_provider)
        _instrumented_apps.add(app_identity)
