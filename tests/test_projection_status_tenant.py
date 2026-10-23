from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.models import OutboxEvent, ProjectionDelivery, ProjectionDeliveryState, Tenant
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.search.client import OpenSearchGateway
from pharma_intel.search.projector import CONSUMER_NAME, SearchProjectionConsumer
from pharma_intel.security import Principal, require_principal


def _seed(session: Session, tenant_id: str, state: ProjectionDeliveryState, consumer: str = CONSUMER_NAME) -> None:
    event = OutboxEvent(
        tenant_id=tenant_id,
        aggregate_type="entity",
        aggregate_id="test",
        event_type="canonical.entity.upserted",
        payload={},
    )
    session.add(event)
    session.flush()
    session.add(
        ProjectionDelivery(
            tenant_id=tenant_id,
            outbox_event_id=event.id,
            consumer_name=consumer,
            state=state,
            available_at=datetime.now(UTC),
        )
    )


@pytest.mark.parametrize("through_http", [False, True])
def test_projection_counts_read_only_the_callers_organization(
    session: Session, tenant: Tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, through_http: bool
) -> None:
    other = Tenant(slug="projection-other", name="Other organization")
    session.add(other)
    session.flush()
    _seed(session, tenant.id, ProjectionDeliveryState.SUCCEEDED)
    _seed(session, tenant.id, ProjectionDeliveryState.RETRY, "monitoring-v1")
    _seed(session, other.id, ProjectionDeliveryState.DEAD)
    _seed(session, other.id, ProjectionDeliveryState.DEAD)
    session.commit()
    session_factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

    class ReadyGateway:
        @staticmethod
        def status() -> object:
            return type(
                "Status",
                (),
                dict(
                    available=True, version="test", cluster_name="test", cluster_status="green", aliases={}, error=None
                ),
            )()

    consumer = SearchProjectionConsumer(
        session_factory, cast(OpenSearchGateway, ReadyGateway()), FileSystemObjectStore(tmp_path), Settings()
    )
    if not through_http:

        def unexpected_tenant_scan() -> list[str]:
            raise AssertionError("An organization-scoped count must not enumerate every tenant")

        monkeypatch.setattr(consumer, "_tenant_ids", unexpected_tenant_scan)
        counts = consumer.delivery_counts(tenant.id)
    else:
        monkeypatch.setattr("pharma_intel.http.search_projection.get_session_factory", lambda: session_factory)
        monkeypatch.setattr("pharma_intel.http.search_projection.get_opensearch_gateway", ReadyGateway)
        monkeypatch.setattr("pharma_intel.http.search_projection.SearchProjectionConsumer", lambda *_: consumer)
        monkeypatch.setattr(
            "pharma_intel.http.search_projection.object_store_module.build_object_store", lambda _: object()
        )
        app.dependency_overrides[require_principal] = lambda: Principal(
            tenant.id, "operator", "user", frozenset({"ingestion:read"})
        )
        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/admin/search/status")
            assert response.status_code == 200
            counts = response.json()["deliveries"]
        finally:
            app.dependency_overrides.clear()
    assert counts == {"processing": 0, "retry": 0, "succeeded": 1, "dead": 0}


def test_trusted_host_global_projection_status_remains_available(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    _seed(session, tenant.id, ProjectionDeliveryState.DEAD)
    session.commit()
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    consumer = SearchProjectionConsumer(
        factory, cast(OpenSearchGateway, object()), FileSystemObjectStore(tmp_path), Settings()
    )
    assert consumer.delivery_counts()["dead"] == 1
