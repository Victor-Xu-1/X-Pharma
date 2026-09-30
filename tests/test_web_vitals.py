from __future__ import annotations

from collections.abc import Generator
from typing import Any, cast

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import pharma_intel.api as api_module
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import AuditEvent, Tenant, User, UserRole
from pharma_intel.operational_metrics import (
    OPERATIONAL_METRIC_NAMES,
    WEB_VITAL_CLS_BUCKETS,
    WEB_VITAL_DURATION_BUCKETS,
    OperationalMetrics,
)
from pharma_intel.schemas import WebVitalBatchCreate, WebVitalSampleCreate
from pharma_intel.security import CSRF_COOKIE, Principal, hash_password, require_principal


def _sample(**overrides: object) -> dict[str, object]:
    return {
        "metric_name": "LCP",
        "value": 2400,
        "rating": "good",
        "route": "pipeline",
        "navigation_type": "navigate",
        "navigation_sequence": 0,
        "viewport_class": "desktop",
        **overrides,
    }


def test_web_vital_schema_recomputes_ratings_and_rejects_unbounded_batches() -> None:
    assert WebVitalSampleCreate.model_validate(_sample()).rating == "good"
    assert WebVitalSampleCreate.model_validate(_sample(value=2501, rating="needs-improvement")).rating == (
        "needs-improvement"
    )
    assert WebVitalSampleCreate.model_validate(_sample(metric_name="CLS", value=0.251, rating="poor")).rating == "poor"

    with pytest.raises(ValidationError, match="rating does not match"):
        WebVitalSampleCreate.model_validate(_sample(value=4100, rating="good"))
    with pytest.raises(ValidationError):
        WebVitalSampleCreate.model_validate(_sample(route="/workspace/research?q=secret"))
    with pytest.raises(ValidationError):
        WebVitalSampleCreate.model_validate(_sample(value=float("inf")))
    with pytest.raises(ValidationError, match="at most 8"):
        WebVitalBatchCreate(samples=[_sample(navigation_sequence=index) for index in range(9)])
    with pytest.raises(ValidationError, match="must be unique"):
        WebVitalBatchCreate(samples=[_sample(), _sample()])


def test_web_vital_metrics_emit_only_bounded_non_identity_dimensions() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    instruments = OperationalMetrics(provider.get_meter("web-vitals-test"))

    instruments.record_web_vital("LCP", "pipeline", "good", "desktop", "navigate", 2400)
    instruments.record_web_vital("CLS", "drug", "needs-improvement", "mobile", "soft-navigation", 0.2)

    metrics_data = reader.get_metrics_data()
    assert metrics_data is not None
    metrics = {
        metric.name: metric
        for resource in metrics_data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }
    assert set(metrics) == {"pharma.web.vitals.duration", "pharma.web.vitals.cls"}
    assert set(metrics).issubset(OPERATIONAL_METRIC_NAMES)
    duration_point = cast(Any, metrics["pharma.web.vitals.duration"].data).data_points[0]
    cls_point = cast(Any, metrics["pharma.web.vitals.cls"].data).data_points[0]
    assert tuple(duration_point.explicit_bounds) == WEB_VITAL_DURATION_BUCKETS
    assert tuple(cls_point.explicit_bounds) == WEB_VITAL_CLS_BUCKETS
    for metric in metrics.values():
        for point in metric.data.data_points:
            attributes = cast(dict[str, Any], point.attributes or {})
            assert set(attributes) == {
                "device.class",
                "navigation.type",
                "web_vital.name",
                "web_vital.rating",
                "workspace.view",
            }
            assert not (
                {"tenant_id", "user_id", "query", "url", "entity_id", "document_id", "credential"} & set(attributes)
            )


def test_web_vital_api_accepts_bounded_human_batches_and_rejects_agents(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    tenant: Tenant,
) -> None:
    recorded: list[tuple[object, ...]] = []

    class RecordingMetrics:
        def record_web_vital(self, *values: object) -> None:
            recorded.append(values)

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "rum-user",
        "user",
        frozenset({"entities:read"}),
    )
    monkeypatch.setattr(api_module, "operational_metrics", lambda: RecordingMetrics())
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/workspace/web-vitals",
                json={
                    "schema_version": 1,
                    "samples": [
                        _sample(),
                        _sample(
                            metric_name="INP",
                            value=201,
                            rating="needs-improvement",
                            navigation_sequence=1,
                            viewport_class="tablet",
                        ),
                    ],
                },
            )
            assert response.status_code == 202
            assert response.json() == {"accepted_count": 2, "schema_version": 1}
            assert recorded == [
                ("LCP", "pipeline", "good", "desktop", "navigate", 2400.0),
                ("INP", "pipeline", "needs-improvement", "tablet", "navigate", 201.0),
            ]
            assert (
                client.post(
                    "/api/v1/workspace/web-vitals",
                    json={"samples": [_sample(value=5000, rating="good")]},
                ).status_code
                == 422
            )

        app.dependency_overrides[require_principal] = lambda: Principal(
            tenant.id,
            "rum-agent",
            "agent",
            frozenset({"entities:read"}),
        )
        with TestClient(app) as client:
            assert (
                client.post(
                    "/api/v1/workspace/web-vitals",
                    json={"samples": [_sample()]},
                ).status_code
                == 403
            )
    finally:
        app.dependency_overrides.clear()


def test_web_vital_api_requires_real_human_csrf_without_expanding_business_audit(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    tenant: Tenant,
) -> None:
    user = User(
        tenant_id=tenant.id,
        email="rum-auth@example.test",
        normalized_email="rum-auth@example.test",
        display_name="RUM Auth",
        password_hash=hash_password("rum-auth-password"),
        role=UserRole.ANALYST,
    )
    session.add(user)
    session.commit()

    class RecordingMetrics:
        def record_web_vital(self, *_: object) -> None:
            return None

    def session_override(request: Request) -> Generator[Session]:
        request.state.db_session = session
        yield session

    app.dependency_overrides[get_session] = session_override
    monkeypatch.setattr(api_module, "operational_metrics", lambda: RecordingMetrics())
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "rum-auth-password"},
            )
            assert login.status_code == 200
            assert (
                client.post(
                    "/api/v1/workspace/web-vitals",
                    json={"samples": [_sample()]},
                ).status_code
                == 403
            )
            csrf = client.cookies.get(CSRF_COOKIE)
            assert csrf
            accepted = client.post(
                "/api/v1/workspace/web-vitals",
                headers={"X-CSRF-Token": csrf},
                json={"samples": [_sample()]},
            )
            assert accepted.status_code == 202

        rum_audits = session.scalar(
            select(func.count(AuditEvent.id)).where(AuditEvent.action == "POST /api/v1/workspace/web-vitals")
        )
        assert rum_audits == 0
    finally:
        app.dependency_overrides.clear()
