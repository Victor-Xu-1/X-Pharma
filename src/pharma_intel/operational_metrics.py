from __future__ import annotations

import threading
from typing import Final, Literal

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, Meter

MCP_CALLS: Final = "pharma.mcp.commercial.calls"
MCP_DURATION: Final = "pharma.mcp.commercial.duration"
INGESTION_OPERATIONS: Final = "pharma.ingestion.operations"
INGESTION_DURATION: Final = "pharma.ingestion.duration"
PROJECTION_DELIVERIES: Final = "pharma.projection.deliveries"
PROJECTION_DURATION: Final = "pharma.projection.duration"
WEB_VITAL_DURATION: Final = "pharma.web.vitals.duration"
WEB_VITAL_CLS: Final = "pharma.web.vitals.cls"
WEB_VITAL_DURATION_BUCKETS: Final = (
    16.0,
    50.0,
    100.0,
    200.0,
    500.0,
    800.0,
    1_000.0,
    1_800.0,
    2_500.0,
    4_000.0,
    5_000.0,
    10_000.0,
    30_000.0,
    60_000.0,
    120_000.0,
)
WEB_VITAL_CLS_BUCKETS: Final = (0.01, 0.025, 0.05, 0.1, 0.15, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)

OPERATIONAL_METRIC_NAMES: Final = frozenset(
    {
        MCP_CALLS,
        MCP_DURATION,
        INGESTION_OPERATIONS,
        INGESTION_DURATION,
        PROJECTION_DELIVERIES,
        PROJECTION_DURATION,
        WEB_VITAL_DURATION,
        WEB_VITAL_CLS,
    }
)

McpOutcome = Literal["settled", "replayed", "failed"]
IngestionOperation = Literal["scan", "process"]
IngestionOutcome = Literal["succeeded", "partial", "retry", "failed", "skipped"]
ProjectionConsumer = Literal["opensearch", "billing_provider", "monitoring"]
ProjectionOutcome = Literal["succeeded", "retry", "dead"]
WebVitalMetricName = Literal["CLS", "INP", "LCP", "TTFB"]
WebVitalRating = Literal["good", "needs-improvement", "poor"]
WebVitalViewportClass = Literal["desktop", "tablet", "mobile"]
WebVitalNavigationType = Literal[
    "navigate",
    "reload",
    "back-forward",
    "back-forward-cache",
    "prerender",
    "restore",
    "soft-navigation",
]


class OperationalMetrics:
    def __init__(self, meter: Meter) -> None:
        self._mcp_calls: Counter = meter.create_counter(
            MCP_CALLS,
            unit="{call}",
            description="Commercial MCP calls by durable outcome",
        )
        self._mcp_duration: Histogram = meter.create_histogram(
            MCP_DURATION,
            unit="s",
            description="End-to-end commercial MCP call duration",
        )
        self._ingestion_operations: Counter = meter.create_counter(
            INGESTION_OPERATIONS,
            unit="{operation}",
            description="Data Factory operations by stage and outcome",
        )
        self._ingestion_duration: Histogram = meter.create_histogram(
            INGESTION_DURATION,
            unit="s",
            description="Data Factory operation duration",
        )
        self._projection_deliveries: Counter = meter.create_counter(
            PROJECTION_DELIVERIES,
            unit="{delivery}",
            description="Projection, monitoring and billing deliveries by durable outcome",
        )
        self._projection_duration: Histogram = meter.create_histogram(
            PROJECTION_DURATION,
            unit="s",
            description="Projection, monitoring and billing delivery duration",
        )
        self._web_vital_duration: Histogram = meter.create_histogram(
            WEB_VITAL_DURATION,
            unit="ms",
            description="External workbench LCP, INP and TTFB measurements",
            explicit_bucket_boundaries_advisory=WEB_VITAL_DURATION_BUCKETS,
        )
        self._web_vital_cls: Histogram = meter.create_histogram(
            WEB_VITAL_CLS,
            unit="1",
            description="External workbench cumulative layout shift measurements",
            explicit_bucket_boundaries_advisory=WEB_VITAL_CLS_BUCKETS,
        )

    def record_mcp_call(self, billing_class: str, outcome: McpOutcome, duration_seconds: float) -> None:
        attributes = {"billing.class": _bounded_identifier(billing_class), "outcome": outcome}
        self._mcp_calls.add(1, attributes)
        self._mcp_duration.record(_duration(duration_seconds), attributes)

    def record_ingestion(
        self,
        operation: IngestionOperation,
        outcome: IngestionOutcome,
        duration_seconds: float,
    ) -> None:
        attributes = {"operation": operation, "outcome": outcome}
        self._ingestion_operations.add(1, attributes)
        self._ingestion_duration.record(_duration(duration_seconds), attributes)

    def record_projection(
        self,
        consumer: ProjectionConsumer,
        outcome: ProjectionOutcome,
        duration_seconds: float,
    ) -> None:
        attributes = {"consumer": consumer, "outcome": outcome}
        self._projection_deliveries.add(1, attributes)
        self._projection_duration.record(_duration(duration_seconds), attributes)

    def record_web_vital(
        self,
        metric_name: WebVitalMetricName,
        route: str,
        rating: WebVitalRating,
        viewport_class: WebVitalViewportClass,
        navigation_type: WebVitalNavigationType,
        value: float,
    ) -> None:
        attributes = {
            "device.class": viewport_class,
            "navigation.type": navigation_type,
            "web_vital.name": metric_name.casefold(),
            "web_vital.rating": rating,
            "workspace.view": _bounded_identifier(route),
        }
        if metric_name == "CLS":
            self._web_vital_cls.record(max(0.0, min(float(value), 10.0)), attributes)
        else:
            self._web_vital_duration.record(max(0.0, min(float(value), 120_000.0)), attributes)


def _bounded_identifier(value: str) -> str:
    normalized = value.strip().casefold()
    if (
        not normalized
        or len(normalized) > 80
        or not all(character.isalnum() or character in "._-" for character in normalized)
    ):
        return "invalid"
    return normalized


def _duration(value: float) -> float:
    return max(0.0, min(float(value), 86_400.0))


_lock = threading.Lock()
_runtime: OperationalMetrics | None = None


def operational_metrics() -> OperationalMetrics:
    global _runtime
    with _lock:
        if _runtime is None:
            _runtime = OperationalMetrics(metrics.get_meter("pharma_intel.operations", "1.0.0"))
        return _runtime
