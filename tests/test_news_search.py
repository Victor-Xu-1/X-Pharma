from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import Entity, EntityType, NewsEvent, ReviewStatus, Tenant
from pharma_intel.security import Principal, require_principal
from pharma_intel.sorting import SortClause


def _entity(session: Session, tenant: Tenant, entity_type: EntityType, name: str) -> Entity:
    entity = Entity(
        tenant_id=tenant.id,
        entity_type=entity_type,
        name=name,
        normalized_name=name.casefold(),
        review_status=ReviewStatus.VERIFIED,
    )
    session.add(entity)
    session.flush()
    return entity


def _news_event(
    session: Session,
    tenant: Tenant,
    *,
    identifier: str,
    event_type: str,
    title: str,
    published_at: datetime,
    publisher: Entity | None,
    related_entities: list[Entity],
    language: str = "en",
    venue: str | None = None,
) -> NewsEvent:
    event = NewsEvent(
        tenant_id=tenant.id,
        event_identifier=identifier,
        event_type=event_type,
        title=title,
        summary=f"Governed summary for {title}",
        published_at=published_at,
        language=language,
        publisher_entity_id=publisher.id if publisher else None,
        related_entity_ids=[entity.id for entity in related_entities],
        canonical_url=f"https://example.test/news/{identifier}",
        venue=venue,
        details={"source_kind": "licensed_feed"},
    )
    session.add(event)
    session.flush()
    return event


def test_news_search_filters_facets_links_and_tenant_isolation(session: Session, tenant: Tenant) -> None:
    publisher = _entity(session, tenant, EntityType.ORGANIZATION, "Acme Pharma")
    drug = _entity(session, tenant, EntityType.DRUG, "Compound A")
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    event = _news_event(
        session,
        tenant,
        identifier="ACME-EGFR-2026",
        event_type="press_release",
        title="Acme reports EGFR Phase 2 results",
        published_at=datetime(2026, 7, 1, tzinfo=UTC),
        publisher=publisher,
        related_entities=[drug, target],
        venue="ASCO 2026",
    )
    negative_event = _news_event(
        session,
        tenant,
        identifier="ACME-EGFR-AACR-2026",
        event_type="press_release",
        title="Acme EGFR venue control",
        published_at=datetime(2026, 7, 2, tzinfo=UTC),
        publisher=publisher,
        related_entities=[drug, target],
        venue="AACR 2026",
    )
    _news_event(
        session,
        tenant,
        identifier="ACME-CORP-2025",
        event_type="corporate_announcement",
        title="Acme appoints a new research leader",
        published_at=datetime(2025, 6, 1, tzinfo=UTC),
        publisher=publisher,
        related_entities=[],
    )

    other_tenant = Tenant(slug="other-news", name="Other News Tenant")
    session.add(other_tenant)
    session.flush()
    hidden_publisher = _entity(session, other_tenant, EntityType.ORGANIZATION, "Hidden Pharma")
    _news_event(
        session,
        other_tenant,
        identifier="HIDDEN-2026",
        event_type="press_release",
        title="Hidden EGFR event",
        published_at=datetime(2026, 7, 2, tzinfo=UTC),
        publisher=hidden_publisher,
        related_entities=[],
        venue="ASCO 2026",
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_news_events(
        "EGFR",
        "press_release",
        "Acme",
        "en",
        "ASCO 2026",
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 12, 31, tzinfo=UTC),
        100,
        0,
    )

    assert result.total == 1
    assert result.query_schema_version == "pharma.news.search.v2"
    assert result.sort_by == "published_at"
    assert result.sort_direction == "desc"
    assert result.items[0].id == event.id
    assert all(item.id != negative_event.id for item in result.items)
    assert result.items[0].publisher_entity is not None
    assert result.items[0].publisher_entity.name == "Acme Pharma"
    assert [entity.name for entity in result.items[0].related_entities] == ["Compound A", "EGFR"]
    assert result.facets == {
        "event_type": {"press_release": 1},
        "language": {"en": 1},
        "venue": {"ASCO 2026": 1},
        "publisher": {"Acme Pharma": 1},
    }

    detail = IntelligenceService(session, tenant.id).news_event_detail(event.id)
    assert detail is not None
    assert detail.title == "Acme reports EGFR Phase 2 results"
    assert detail.publisher_entity is not None
    assert detail.publisher_entity.name == "Acme Pharma"
    assert IntelligenceService(session, other_tenant.id).news_event_detail(event.id) is None

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "news-test", "api_key", frozenset({"news:read"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/news-events/{event.id}")
            assert response.status_code == 200
            assert response.json()["publisher_entity"]["name"] == "Acme Pharma"
            assert client.get("/api/v1/news-events/00000000-0000-0000-0000-000000000000").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_news_search_escapes_wildcards_and_paginates_deterministically(session: Session, tenant: Tenant) -> None:
    publisher = _entity(session, tenant, EntityType.ORGANIZATION, "Publisher")
    related = _entity(session, tenant, EntityType.DRUG, "Compound B")
    older = _news_event(
        session,
        tenant,
        identifier="NEWS-OLDER",
        event_type="news",
        title="Older governed event",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        publisher=publisher,
        related_entities=[related],
    )
    newer = _news_event(
        session,
        tenant,
        identifier="NEWS-NEWER",
        event_type="news",
        title="Newer governed event",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        publisher=publisher,
        related_entities=[related],
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    assert service.search_news_events("%", None, None, None, None, None, None, 100, 0).total == 0
    assert [
        item.id
        for item in service.news_event_search_items(
            related.id,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            100,
        )
    ] == [newer.id, older.id]
    first = service.search_news_events(None, None, None, None, None, None, None, 1, 0)
    second = service.search_news_events(None, None, None, None, None, None, None, 1, 1)
    assert first.total == second.total == 2
    assert first.items[0].id == newer.id
    assert second.items[0].id == older.id
    ascending = service.search_news_events(
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        2,
        0,
        sort_by="title",
        sort_direction="asc",
    )
    assert [item.id for item in ascending.items] == [newer.id, older.id]
    assert ascending.sort_by == "title"
    assert ascending.sort_direction == "asc"
    multi_sorted = service.search_news_events(
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        2,
        0,
        sort=(SortClause(field="event_type", direction="asc"), SortClause(field="title", direction="desc")),
    )
    assert [item.id for item in multi_sorted.items] == [older.id, newer.id]
    assert [criterion.model_dump() for criterion in multi_sorted.sort] == [
        {"field": "event_type", "direction": "asc"},
        {"field": "title", "direction": "desc"},
    ]


def test_news_research_scope_returns_only_publications_and_conference_materials(
    session: Session,
    tenant: Tenant,
) -> None:
    publisher = _entity(session, tenant, EntityType.ORGANIZATION, "Research Publisher")
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    publication = _news_event(
        session,
        tenant,
        identifier="PMID-RESEARCH-1",
        event_type="publication",
        title="EGFR peer-reviewed publication",
        published_at=datetime(2026, 7, 3, tzinfo=UTC),
        publisher=publisher,
        related_entities=[target],
        venue="Journal of Precision Oncology",
    )
    poster = _news_event(
        session,
        tenant,
        identifier="ASCO-POSTER-1",
        event_type="poster",
        title="EGFR conference poster",
        published_at=datetime(2026, 7, 2, tzinfo=UTC),
        publisher=publisher,
        related_entities=[target],
        venue="ASCO 2026",
    )
    _news_event(
        session,
        tenant,
        identifier="PRESS-1",
        event_type="press_release",
        title="EGFR press release",
        published_at=datetime(2026, 7, 4, tzinfo=UTC),
        publisher=publisher,
        related_entities=[target],
        venue="ASCO 2026",
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_news_events(
        "EGFR",
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        research_content_only=True,
    )

    assert result.total == 2
    assert [item.id for item in result.items] == [publication.id, poster.id]
    assert result.facets["event_type"] == {"poster": 1, "publication": 1}


def test_news_landscape_aggregates_full_hit_set(session: Session, tenant: Tenant) -> None:
    """Landscape buckets come from the complete filtered set, not the returned page."""

    _news_event(
        session,
        tenant,
        identifier="NEWS-L1",
        event_type="publication",
        title="First readout",
        published_at=datetime(2026, 3, 1, tzinfo=UTC),
        publisher=None,
        related_entities=[],
        venue="ASCO",
    )
    _news_event(
        session,
        tenant,
        identifier="NEWS-L2",
        event_type="publication",
        title="Second readout",
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        publisher=None,
        related_entities=[],
        venue="ASCO",
    )
    _news_event(
        session,
        tenant,
        identifier="NEWS-L3",
        event_type="press_release",
        title="Corporate update",
        published_at=datetime(2025, 8, 1, tzinfo=UTC),
        publisher=None,
        related_entities=[],
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_news_events(None, None, None, None, None, None, None, 1, 0)

    assert len(result.items) == 1
    assert result.landscape.total_events == 3
    assert {(b.key, b.count) for b in result.landscape.event_type} == {("publication", 2), ("press_release", 1)}
    assert {(b.key, b.count) for b in result.landscape.venue} == {("ASCO", 2), ("__missing__", 1)}
    assert [b.key for b in result.landscape.published_year] == ["2026", "2025"]
