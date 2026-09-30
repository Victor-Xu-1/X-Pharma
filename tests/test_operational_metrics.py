from __future__ import annotations

from typing import Any, cast

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from pharma_intel.operational_metrics import OPERATIONAL_METRIC_NAMES, OperationalMetrics


def test_operational_metrics_emit_only_bounded_business_dimensions() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    instruments = OperationalMetrics(provider.get_meter("operations-test"))

    instruments.record_mcp_call("search_entities", "settled", 0.25)
    instruments.record_mcp_call("unsafe value with spaces", "failed", -1)
    instruments.record_ingestion("process", "retry", 2.5)
    instruments.record_projection("opensearch", "dead", 90_000)
    instruments.record_web_vital("LCP", "pipeline", "good", "desktop", "navigate", 2400)
    instruments.record_web_vital("CLS", "drug", "poor", "mobile", "soft-navigation", 0.3)

    metrics_data = reader.get_metrics_data()
    assert metrics_data is not None
    metrics = {
        metric.name: metric
        for resource in metrics_data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }
    assert set(metrics) == OPERATIONAL_METRIC_NAMES
    for metric in metrics.values():
        for point in metric.data.data_points:
            attributes = cast(dict[str, Any], point.attributes or {})
            assert not ({"tenant_id", "user_id", "query", "document_id", "credential"} & set(attributes))
    mcp_points = cast(Any, metrics["pharma.mcp.commercial.calls"].data).data_points
    assert {cast(dict[str, Any], point.attributes)["billing.class"] for point in mcp_points} == {
        "search_entities",
        "invalid",
    }
    projection_point = cast(Any, metrics["pharma.projection.duration"].data).data_points[0]
    assert projection_point.max == 86_400.0


def test_operational_metric_name_contract_is_stable() -> None:
    assert OPERATIONAL_METRIC_NAMES == {
        "pharma.ingestion.duration",
        "pharma.ingestion.operations",
        "pharma.mcp.commercial.calls",
        "pharma.mcp.commercial.duration",
        "pharma.projection.deliveries",
        "pharma.projection.duration",
        "pharma.web.vitals.cls",
        "pharma.web.vitals.duration",
    }
