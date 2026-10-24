from __future__ import annotations

from collections.abc import Callable, Generator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from opensearchpy import OpenSearch
from sqlalchemy import event
from sqlalchemy.engine import Connection, ExecutionContext
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.models import Entity, EntityType, ReviewStatus, Tenant
from pharma_intel.search.client import OpenSearchGateway, SearchProjectionError
from pharma_intel.search.service import EntitySearchService
from pharma_intel.security import Principal, require_principal


@pytest.fixture
def search_settings() -> Settings:
    return Settings(_env_file=None, database_url="sqlite://", search_backend="opensearch")


@pytest.fixture
def index_client() -> MagicMock:
    return MagicMock(spec=OpenSearch)


@pytest.fixture
def gateway(search_settings: Settings, index_client: MagicMock) -> OpenSearchGateway:
    return OpenSearchGateway(search_settings, client=index_client)


def _entity(
    session: Session,
    tenant: Tenant,
    review_status: ReviewStatus = ReviewStatus.VERIFIED,
    entity_type: EntityType = EntityType.TARGET,
    name: str = "Current authoritative name",
) -> Entity:
    entity = Entity(
        tenant_id=tenant.id,
        name=name,
        normalized_name=name.casefold(),
        entity_type=entity_type,
        review_status=review_status,
        external_ids={},
        attributes={},
    )
    session.add(entity)
    session.commit()
    return entity


def _project(index_client: MagicMock, *entities: Entity, total: int | None = None) -> None:
    """Exercise the real gateway with an intentionally stale index response."""
    index_client.search.return_value = {
        "hits": {
            "total": {"value": len(entities) if total is None else total},
            "hits": [
                {
                    "_source": {
                        "entity_id": entity.id,
                        "name": f"Old indexed name {entity.id}",
                        "entity_type": "target",
                        "review_status": "verified",
                    }
                }
                for entity in entities
            ],
        },
        "aggregations": {
            "entity_types": {"values": {"buckets": [{"key": "target", "doc_count": 57}]}},
            "review_statuses": {"values": {"buckets": [{"key": "verified", "doc_count": 57}]}},
        },
        "took": 7,
    }


@pytest.mark.parametrize("review_status", [ReviewStatus.DRAFT, ReviewStatus.REJECTED, ReviewStatus.SUPERSEDED])
def test_indexed_search_rechecks_authoritative_review_status(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
    review_status: ReviewStatus,
) -> None:
    entity = _entity(session, tenant, review_status)
    _project(index_client, entity)
    service = EntitySearchService(session, tenant.id, search_settings, gateway)

    with pytest.raises(SearchProjectionError, match="review status"):
        service.search("Current", None, 25, 0, ReviewStatus.VERIFIED)


def test_indexed_search_rechecks_authoritative_entity_type(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
) -> None:
    entity = _entity(session, tenant, entity_type=EntityType.DRUG)
    _project(index_client, entity)

    with pytest.raises(SearchProjectionError, match="entity type"):
        EntitySearchService(session, tenant.id, search_settings, gateway).search(
            "Current",
            EntityType.TARGET,
            25,
            0,
            ReviewStatus.VERIFIED,
        )


@pytest.mark.parametrize("reverse", [False, True])
def test_one_stale_record_rejects_the_entire_page_instead_of_changing_counts(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
    reverse: bool,
) -> None:
    visible = _entity(session, tenant)
    hidden = _entity(session, tenant, ReviewStatus.DRAFT, name="Hidden authoritative name")
    entities = [visible, hidden]
    _project(index_client, *reversed(entities) if reverse else entities, total=57)

    with pytest.raises(SearchProjectionError, match="review status"):
        EntitySearchService(session, tenant.id, search_settings, gateway).search(
            "Current",
            None,
            2,
            4,
            ReviewStatus.VERIFIED,
        )


@pytest.mark.parametrize("review_status", [None, *ReviewStatus])
def test_unrestricted_and_matching_review_filters_remain_valid(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
    review_status: ReviewStatus | None,
) -> None:
    entity = _entity(session, tenant, review_status or ReviewStatus.DRAFT)
    _project(index_client, entity)
    result = EntitySearchService(session, tenant.id, search_settings, gateway).search(
        "Current",
        None,
        25,
        0,
        review_status,
    )

    assert [item.id for item in result.items] == [entity.id]


@pytest.mark.parametrize(
    "entity_type,entity_types",
    [
        (None, []),
        (EntityType.DRUG, []),
        (EntityType.TARGET, [EntityType.DRUG]),
        (None, [EntityType.TARGET, EntityType.DRUG]),
    ],
)
def test_type_filters_preserve_the_existing_or_semantics(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
    entity_type: EntityType | None,
    entity_types: list[EntityType],
) -> None:
    entity = _entity(session, tenant, entity_type=EntityType.DRUG)
    _project(index_client, entity)
    result = EntitySearchService(session, tenant.id, search_settings, gateway).search(
        "Current",
        entity_type,
        25,
        0,
        ReviewStatus.VERIFIED,
        entity_types=entity_types,
    )

    assert [item.id for item in result.items] == [entity.id]


def test_search_uses_canonical_names_and_preserves_index_order_pagination_and_facets(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
) -> None:
    first = _entity(session, tenant, name="Current first")
    second = _entity(session, tenant, name="Current second")
    _project(index_client, second, first, total=57)
    result = EntitySearchService(session, tenant.id, search_settings, gateway).search(
        "Current",
        EntityType.TARGET,
        2,
        4,
        ReviewStatus.VERIFIED,
    )

    assert [item.id for item in result.items] == [second.id, first.id]
    assert result.suggestions == ["Current second", "Current first"]
    assert result.total == 57
    assert result.facets == {"entity_type": {"target": 57}, "review_status": {"verified": 57}}
    assert result.engine == "opensearch" and result.took_ms == 7
    body = index_client.search.call_args.kwargs["body"]
    assert body["size"] == 2 and body["from"] == 4


def test_a_projected_id_from_another_tenant_still_fails_closed(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
) -> None:
    other = Tenant(slug="other", name="Other tenant")
    session.add(other)
    session.commit()
    _project(index_client, _entity(session, other))

    with pytest.raises(SearchProjectionError, match="unavailable"):
        EntitySearchService(session, tenant.id, search_settings, gateway).search(
            "Current",
            None,
            25,
            0,
            ReviewStatus.VERIFIED,
        )


def test_canonical_suggestions_remain_unique_ordered_and_bounded(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
) -> None:
    entities = [_entity(session, tenant, name=f"Current {index:02d}") for index in range(12)]
    duplicate = _entity(session, tenant, name=entities[0].name, entity_type=EntityType.DRUG)
    _project(index_client, entities[0], duplicate, *entities[1:])

    result = EntitySearchService(session, tenant.id, search_settings, gateway).search(
        "Current",
        None,
        25,
        0,
        ReviewStatus.VERIFIED,
    )

    assert len(result.items) == 13
    assert result.suggestions == [entity.name for entity in entities[:10]]


def test_authority_validation_and_suggestions_do_not_add_per_row_database_queries(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    index_client: MagicMock,
) -> None:
    entities = [_entity(session, tenant, name=f"Current {index:02d}") for index in range(20)]
    statements: list[str] = []
    counts: list[int] = []

    def record_query(
        _connection: Connection,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: ExecutionContext,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    engine = session.get_bind()
    for size in (1, 20):
        session.expunge_all()
        _project(index_client, *entities[:size])
        statements.clear()
        event.listen(engine, "before_cursor_execute", record_query)
        try:
            result = EntitySearchService(session, tenant.id, search_settings, gateway).search(
                "Current",
                None,
                25,
                0,
                ReviewStatus.VERIFIED,
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_query)
        assert len(result.items) == size
        counts.append(len(statements))

    assert counts == [4, 4]


@pytest.fixture
def client(
    session: Session,
    tenant: Tenant,
    search_settings: Settings,
    gateway: OpenSearchGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient]:
    def session_override() -> Generator[Session]:
        yield session

    def principal_override(request: Request) -> Principal:
        principal = Principal(tenant.id, "authority-test-reader", "user", frozenset({"entities:read"}))
        request.state.principal = principal
        return principal

    overrides: dict[Callable[..., object], Callable[..., object]] = app.dependency_overrides
    replacements: dict[Callable[..., object], Callable[..., object]] = {
        get_session: session_override,
        require_principal: principal_override,
    }
    for dependency, replacement in replacements.items():
        monkeypatch.setitem(overrides, dependency, replacement)
    monkeypatch.setattr("pharma_intel.http.runtime.get_settings", lambda: search_settings)
    monkeypatch.setattr("pharma_intel.search.service.get_opensearch_gateway", lambda: gateway)
    audit_factory = sessionmaker(bind=session.get_bind(), autoflush=False, expire_on_commit=False)
    monkeypatch.setattr("pharma_intel.http.middleware.get_session_factory", lambda: audit_factory)
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/api/v1/entities", "/api/v1/entities/suggestions"])
@pytest.mark.parametrize("review_status", [ReviewStatus.DRAFT, ReviewStatus.REJECTED, ReviewStatus.SUPERSEDED])
def test_http_search_and_suggestions_do_not_expose_an_unpublished_index_hit(
    session: Session,
    tenant: Tenant,
    client: TestClient,
    index_client: MagicMock,
    path: str,
    review_status: ReviewStatus,
) -> None:
    entity = _entity(session, tenant, review_status)
    _project(index_client, entity)

    assert client.get(f"/api/v1/entities/{entity.id}").status_code == 404
    response = client.get(path, params={"q": "Current"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Entity search projection unavailable"}
    assert entity.name not in response.text and entity.id not in response.text


@pytest.mark.parametrize("path", ["/api/v1/entities", "/api/v1/entities/suggestions"])
def test_http_search_rejects_stale_type_and_returns_current_suggestion_names(
    session: Session,
    tenant: Tenant,
    client: TestClient,
    index_client: MagicMock,
    path: str,
) -> None:
    entity = _entity(session, tenant, entity_type=EntityType.DRUG)
    _project(index_client, entity)

    rejected = client.get(path, params={"q": "Current", "entity_type": "target"})
    assert rejected.status_code == 503
    accepted = client.get(path, params={"q": "Current", "entity_type": "drug"})
    assert accepted.status_code == 200
    assert accepted.json()["suggestions"] == [entity.name]


def test_agent_domain_rejects_stale_projection_without_issuing_a_cursor(
    session: Session,
    tenant: Tenant,
    client: TestClient,
    index_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _project(index_client, _entity(session, tenant, ReviewStatus.DRAFT))
    commercial = MagicMock()
    commercial.authorize_paginated_query.return_value = SimpleNamespace(page_offset=0, page_depth=0)
    commercial.issue_next_cursor.return_value = None
    monkeypatch.setattr("pharma_intel.http.agent_entities._commercial_service", lambda *_: commercial)

    response = client.get(
        "/internal/v1/domain/entities",
        params={"q": "Current", "billing_class": "entity.search"},
        headers={"X-Commercial-Reservation-ID": "00000000-0000-4000-8000-000000000001"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Entity search projection unavailable"}
    commercial.authorize_paginated_query.assert_called_once()
    commercial.issue_next_cursor.assert_not_called()
