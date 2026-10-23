from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_updated_telemetry_keeps_real_http_sql_logging_and_metrics_instrumentation() -> None:
    # An isolated interpreter avoids changing the process-wide providers used by other tests.
    probe = textwrap.dedent(
        """
        import logging
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from opentelemetry import trace
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import StaticPool
        from pharma_intel import telemetry
        from pharma_intel.config import Settings

        spans = InMemorySpanExporter()
        metrics = InMemoryMetricReader()
        # Only exporters are isolated: the application's actual instrumentation still runs.
        telemetry.OTLPSpanExporter = lambda **kwargs: spans
        telemetry.OTLPMetricExporter = lambda **kwargs: None
        telemetry.BatchSpanProcessor = SimpleSpanProcessor
        telemetry.PeriodicExportingMetricReader = lambda *args, **kwargs: metrics
        settings = Settings(_env_file=None, otel_enabled=True)
        telemetry.get_settings = lambda: settings
        original_log_factory = logging.getLogRecordFactory()
        engine = create_engine(
            "sqlite+pysqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        runtime = telemetry.initialize_telemetry("security-regression", settings=settings, engine=engine)
        assert runtime is not None
        assert telemetry.initialize_telemetry("security-regression", settings=settings, engine=engine) is runtime
        app = FastAPI()

        @app.get("/probe")
        def read_probe():
            with engine.connect() as connection:
                return {"value": connection.scalar(text("SELECT 7"))}

        telemetry.instrument_fastapi(app, "security-regression")
        middleware_count = len(app.user_middleware)
        telemetry.instrument_fastapi(app, "security-regression")
        assert len(app.user_middleware) == middleware_count
        with trace.get_tracer("security-regression").start_as_current_span("caller"):
            record = logging.getLogger("security-regression").makeRecord(
                "security-regression", logging.INFO, "probe", 1, "bounded probe", (), None
            )
            assert logging.getLogRecordFactory() is not original_log_factory
            assert record.getMessage() == "bounded probe"
            assert trace.get_current_span().get_span_context().is_valid
            with TestClient(app) as client:
                response = client.get("/probe")
            assert response.status_code == 200 and response.json() == {"value": 7}
        runtime.tracer_provider.force_flush()
        finished = spans.get_finished_spans()
        assert any(span.attributes.get("http.route") == "/probe" for span in finished)
        assert any(span.attributes.get("db.statement") == "SELECT 7" for span in finished)
        counter = runtime.meter_provider.get_meter("security-regression").create_counter("verified_calls")
        counter.add(1)
        assert metrics.get_metrics_data() is not None
        runtime.shutdown()
        engine.dispose()
        print("telemetry_runtime=passed exporters=in_memory external_requests=0")
        """
    )
    result = subprocess.run(  # noqa: S603 - Fixed same-interpreter probe; no caller or external input.
        [sys.executable, "-I", "-B", "-c", probe],
        env={"PATH": os.defpath},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "telemetry_runtime=passed" in result.stdout
