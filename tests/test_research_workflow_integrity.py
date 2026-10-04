from __future__ import annotations

from collections.abc import Generator
from typing import Literal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.comparison.service import ComparisonSetNotFound, ComparisonSetService
from pharma_intel.db import get_session
from pharma_intel.models import MonitoringAlert, SavedSearchVisibility, Tenant, User, UserRole
from pharma_intel.monitoring.service import MonitoringNotFound, MonitoringService
from pharma_intel.schemas import ComparisonSetCreate, ComparisonSetUpdate, SavedSearchCreate, SavedSearchUpdate
from pharma_intel.security import Principal, require_principal


def user(session: Session, tenant: Tenant, label: str) -> User:
    item = create_account(
        tenant_id=tenant.id,
        email=f"{label}@example.test",
        normalized_email=f"{label}@example.test",
        display_name=label,
        role=UserRole.ANALYST,
        password_hash="not-used",  # noqa: S106
    )
    session.add(item)
    session.commit()
    return item


def test_collection_catalog_searches_before_paging_and_isolates_owners(session: Session, tenant: Tenant) -> None:
    owner, colleague = user(session, tenant, "catalog-owner"), user(session, tenant, "catalog-colleague")
    service = ComparisonSetService(session, tenant.id, owner.id)
    old = service.create_set(ComparisonSetCreate(name="Older review", description="Literal 100% indication"))
    for index in range(103):
        service.create_set(ComparisonSetCreate(name=f"Newer review {index:03d}"))
    first = service.catalog(q="review", limit=25, offset=0)
    last = service.catalog(q="review", limit=25, offset=100)
    assert first.total == last.total == 104
    assert len(first.items) == 25 and len(last.items) == 4
    assert last.items[-1].item.id == old.item.id
    assert [view.item.id for view in service.catalog(q="100%", limit=25, offset=0).items] == [old.item.id]
    assert ComparisonSetService(session, tenant.id, colleague.id).catalog(q="", limit=25, offset=0).total == 0
    shared = service.create_set(ComparisonSetCreate(name="Shared review", visibility=SavedSearchVisibility.TENANT))
    reader = ComparisonSetService(session, tenant.id, colleague.id)
    assert reader.catalog(q="", limit=25, offset=0).items[0].item.id == shared.item.id
    assert reader.catalog(q="", limit=25, offset=0, editable_only=True).total == 0


def test_collection_history_does_not_publish_private_past_and_has_a_cursor(session: Session, tenant: Tenant) -> None:
    owner, colleague = user(session, tenant, "history-owner"), user(session, tenant, "history-colleague")
    service = ComparisonSetService(session, tenant.id, owner.id)
    created = service.create_set(ComparisonSetCreate(name="Private", description="Private old note"))
    shared = service.update_set(
        created.item.id,
        ComparisonSetUpdate(expected_version=1, description="Shared note", visibility=SavedSearchVisibility.TENANT),
    )
    reader = ComparisonSetService(session, tenant.id, colleague.id)
    assert reader.get_set(shared.item.id).item.description == "Shared note"
    with pytest.raises(ComparisonSetNotFound):
        reader.list_versions(shared.item.id)
    first = service.list_versions(shared.item.id, limit=1)
    earlier = service.list_versions(shared.item.id, limit=1, before_version=first[0].version)
    assert [item.version for item in first] == [2]
    assert [item.version for item in earlier] == [1]
    assert earlier[0].snapshot_json["description"] == "Private old note"


def test_monitoring_replay_uses_pinned_topic_and_original_alert_versions(session: Session, tenant: Tenant) -> None:
    owner = user(session, tenant, "replay-owner")
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(SavedSearchCreate(name="Research", query={"q": "Original"}))
    topic = service.create_topic("Pinned", saved.id)
    service.update_saved_search(saved.id, SavedSearchUpdate(query={"q": "Revised"}))
    pinned = service.replay_topic(topic.id)
    assert pinned.version.version == 1
    assert pinned.version.query_json["q"] == "Original"
    alert = MonitoringAlert(
        tenant_id=tenant.id,
        topic_id=topic.id,
        recipient_user_id=owner.id,
        entity_id="11111111-1111-4111-8111-111111111111",
        source_outbox_event_id="22222222-2222-4222-8222-222222222222",
        event_type="canonical.entity.upserted",
        title="Original event",
        summary="Synthetic",
        payload_json={"saved_search_id": saved.id, "query_version": 1},
    )
    session.add(alert)
    session.commit()
    service.update_topic(topic.id, name=None, active=None, query_version=2)
    assert service.replay_topic(topic.id).version.query_json["q"] == "Revised"
    assert service.replay_alert(alert.id).version.query_json["q"] == "Original"
    stranger = user(session, tenant, "replay-stranger")
    with pytest.raises(MonitoringNotFound):
        MonitoringService(session, tenant.id, stranger.id).replay_topic(topic.id)
    with pytest.raises(MonitoringNotFound):
        MonitoringService(session, tenant.id, stranger.id).replay_alert(alert.id)


def test_pinned_replay_stops_when_shared_query_is_withdrawn(session: Session, tenant: Tenant) -> None:
    owner, colleague = user(session, tenant, "share-owner"), user(session, tenant, "share-colleague")
    owner_service = MonitoringService(session, tenant.id, owner.id)
    reader = MonitoringService(session, tenant.id, colleague.id)
    saved = owner_service.create_saved_search(
        SavedSearchCreate(name="Shared", query={"q": "Original"}, visibility=SavedSearchVisibility.TENANT)
    )
    topic = reader.create_topic("Reader topic", saved.id)
    assert reader.replay_topic(topic.id).version.query_json["q"] == "Original"
    owner_service.update_saved_search(saved.id, SavedSearchUpdate(visibility=SavedSearchVisibility.PRIVATE))
    with pytest.raises(MonitoringNotFound):
        reader.replay_topic(topic.id)
    assert owner_service.get_saved_search(saved.id).query_version == 1


@pytest.mark.parametrize("actor", ["owner", "colleague", "outsider", "agent", "api_key"])
def test_research_catalog_history_and_replay_http_boundaries(session: Session, tenant: Tenant, actor: str) -> None:
    owner, colleague = user(session, tenant, "http-owner"), user(session, tenant, "http-colleague")
    outside = Tenant(slug="workflow-outside", name="Outside")
    session.add(outside)
    session.commit()
    outsider = user(session, outside, "http-outsider")
    comparison = ComparisonSetService(session, tenant.id, owner.id)
    item = comparison.create_set(ComparisonSetCreate(name="Shared", visibility=SavedSearchVisibility.TENANT))
    monitor = MonitoringService(session, tenant.id, owner.id)
    saved = monitor.create_saved_search(SavedSearchCreate(name="Pinned query", query={"q": "Original"}))
    topic = monitor.create_topic("Pinned topic", saved.id)
    monitor.update_saved_search(saved.id, SavedSearchUpdate(query={"q": "Revised"}))
    identities = {"owner": owner, "colleague": colleague, "outsider": outsider, "agent": owner, "api_key": owner}
    identity = identities[actor]
    actor_type: Literal["agent", "api_key", "user"] = (
        "agent" if actor == "agent" else "api_key" if actor == "api_key" else "user"
    )
    principal = Principal(
        outside.id if actor == "outsider" else tenant.id,
        identity.id,
        actor_type,
        frozenset({"collections:read", "monitoring:read"}),
    )

    def database() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = database
    app.dependency_overrides[require_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            catalog = client.get("/api/v1/comparison-sets/catalog?q=Shared&limit=1&offset=0")
            history = client.get(f"/api/v1/comparison-sets/{item.item.id}/versions?limit=1")
            replay = client.get(f"/api/v1/monitoring/topics/{topic.id}/replay")
            if actor in {"agent", "api_key"}:
                assert catalog.status_code == history.status_code == replay.status_code == 403
            else:
                assert catalog.status_code == 200
                assert catalog.json()["total"] == (0 if actor == "outsider" else 1)
                assert history.status_code == replay.status_code == (200 if actor == "owner" else 404)
                if actor == "owner":
                    assert replay.json()["query_version"] == 1
                    assert replay.json()["query_json"]["q"] == "Original"
                    assert client.get("/api/v1/comparison-sets/catalog?limit=101").status_code == 422
                    assert client.get("/api/v1/comparison-sets/catalog?offset=-1").status_code == 422
                    assert (
                        client.get(f"/api/v1/comparison-sets/{item.item.id}/versions?before_version=0").status_code
                        == 422
                    )
                    assert (
                        client.get(
                            f"/api/v1/comparison-sets/{item.item.id}/versions?before_version=999999999999999999999"
                        ).status_code
                        == 422
                    )
    finally:
        app.dependency_overrides.clear()
