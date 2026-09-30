from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import Entity, EntityType, PatentFamily, Relationship, ReviewStatus, Tenant
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


def _patent(
    session: Session,
    tenant: Tenant,
    family_identifier: str,
    title: str,
    *,
    applicant: str,
    legal_status: str,
    priority_day: int,
    linked_entity_ids: list[str] | None = None,
) -> tuple[PatentFamily, Entity]:
    entity = _entity(session, tenant, EntityType.PATENT, family_identifier)
    patent = PatentFamily(
        tenant_id=tenant.id,
        entity_id=entity.id,
        family_identifier=family_identifier,
        title=title,
        priority_date=datetime(2024, 1, priority_day, tzinfo=UTC),
        applicants=[applicant],
        inventors=["A. Researcher"],
        publications=[{"publication_number": family_identifier, "jurisdiction": "WO"}],
        legal_status=legal_status,
        legal_status_at=datetime(2026, 6, priority_day, tzinfo=UTC),
        legal_events=[
            {
                "event_type": "status_update",
                "status": legal_status,
                "occurred_at": datetime(2026, 6, priority_day, tzinfo=UTC).isoformat(),
                "jurisdiction": "WO",
            }
        ],
        independent_claims=[
            {
                "claim_number": "1",
                "claim_type": "composition",
                "summary": f"Composition protected by {family_identifier}",
            }
        ],
        expiration_date=datetime(2044, 1, priority_day, tzinfo=UTC),
        linked_entity_ids=linked_entity_ids or [],
    )
    session.add(patent)
    session.flush()
    return patent, entity


def test_patent_search_filters_facets_and_returns_linked_entities(session: Session, tenant: Tenant) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    drug = _entity(session, tenant, EntityType.DRUG, "VX-101")
    patent, patent_entity = _patent(
        session,
        tenant,
        "WO2026000001",
        "Covalent inhibitors of mutant EGFR",
        applicant="Victor Therapeutics",
        legal_status="ACTIVE",
        priority_day=10,
        linked_entity_ids=[target.id, drug.id],
    )
    negative_patent, _ = _patent(
        session,
        tenant,
        "WO2026000003",
        "Covalent inhibitors of mutant EGFR",
        applicant="Victor Therapeutics",
        legal_status="PENDING",
        priority_day=11,
        linked_entity_ids=[target.id, drug.id],
    )
    for linked in (target, drug):
        session.add(
            Relationship(
                tenant_id=tenant.id,
                subject_id=patent_entity.id,
                predicate="patent_links_entity",
                object_id=linked.id,
            )
        )
    _patent(
        session,
        tenant,
        "WO2025000002",
        "Antibody composition",
        applicant="Other Bio",
        legal_status="EXPIRED",
        priority_day=5,
    )
    other_tenant = Tenant(slug="other-patent", name="Other Patent Tenant")
    session.add(other_tenant)
    session.flush()
    _patent(
        session,
        other_tenant,
        "WO2099000001",
        "Hidden tenant patent",
        applicant="Victor Therapeutics",
        legal_status="ACTIVE",
        priority_day=20,
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_patent_families(
        "egfr",
        "Victor Therapeutics",
        "ACTIVE",
        100,
        0,
    )

    assert result.total == 1
    assert result.query_schema_version == "pharma.patent.search.v2"
    assert result.sort_by == "priority_date"
    assert result.sort_direction == "desc"
    assert result.facets == {
        "legal_status": {"ACTIVE": 1},
        "applicant": {"Victor Therapeutics": 1},
    }
    assert result.items[0].id == patent.id
    assert all(item.id != negative_patent.id for item in result.items)
    assert result.items[0].family_identifier == "WO2026000001"
    assert result.items[0].legal_status_at == datetime(2026, 6, 10, tzinfo=UTC)
    assert result.items[0].legal_events[0].event_type == "status_update"
    assert result.items[0].independent_claims[0].claim_type == "composition"
    assert {(item.entity_type.value, item.name) for item in result.items[0].linked_entities} == {
        ("drug", "VX-101"),
        ("target", "EGFR"),
    }
    assert result.warnings == ["未观察到专利族不代表不存在；结果受司法辖区、数据授权、法律状态时效和治理状态限制。"]

    detail = IntelligenceService(session, tenant.id).patent_family_detail(patent.id)
    assert detail is not None
    assert detail.family_identifier == "WO2026000001"
    assert {item.name for item in detail.linked_entities} == {"EGFR", "VX-101"}
    assert IntelligenceService(session, other_tenant.id).patent_family_detail(patent.id) is None

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "patent-test", "api_key", frozenset({"patents:read"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/patent-families/{patent.id}")
            assert response.status_code == 200
            assert response.json()["family_identifier"] == "WO2026000001"
            assert client.get("/api/v1/patent-families/00000000-0000-0000-0000-000000000000").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_patent_search_escapes_wildcards_supports_legacy_links_and_paginates(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "KRAS")
    for index in range(2):
        _patent(
            session,
            tenant,
            f"WO202600000{index + 1}",
            f"Patent {index}",
            applicant="Legacy Bio",
            legal_status="PENDING",
            priority_day=index + 1,
            linked_entity_ids=[target.id] if index == 0 else [],
        )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    assert service.search_patent_families("%", None, None, 100, 0).total == 0
    legacy = service.search_patent_families(None, None, None, 100, 0, entity_id=target.id)
    assert legacy.total == 1
    assert [(item.entity_type.value, item.name) for item in legacy.items[0].linked_entities] == [("target", "KRAS")]
    first = service.search_patent_families(None, None, None, 1, 0)
    second = service.search_patent_families(None, None, None, 1, 1)
    assert first.total == second.total == 2
    assert first.items[0].family_identifier == "WO2026000002"
    assert second.items[0].family_identifier == "WO2026000001"
    ascending = service.search_patent_families(
        None,
        None,
        None,
        2,
        0,
        sort_by="family_identifier",
        sort_direction="asc",
    )
    assert [item.family_identifier for item in ascending.items] == ["WO2026000001", "WO2026000002"]
    assert ascending.sort_by == "family_identifier"
    assert ascending.sort_direction == "asc"
    multi_sorted = service.search_patent_families(
        None,
        None,
        None,
        2,
        0,
        sort=(
            SortClause(field="legal_status", direction="asc"),
            SortClause(field="family_identifier", direction="desc"),
        ),
    )
    assert [item.family_identifier for item in multi_sorted.items] == ["WO2026000002", "WO2026000001"]
    assert [criterion.model_dump() for criterion in multi_sorted.sort] == [
        {"field": "legal_status", "direction": "asc"},
        {"field": "family_identifier", "direction": "desc"},
    ]
    assert first.facets["applicant"] == {"Legacy Bio": 2}


def test_patent_landscape_aggregates_full_hit_set_not_current_page(session: Session, tenant: Tenant) -> None:
    """The landscape must be computed by the database over the complete filtered set.

    Three families are seeded but the query asks for a single-item page; a landscape
    derived from the returned page would report one family and lose the missing-status
    bucket entirely.
    """

    _patent(
        session, tenant, "WO2026000101", "First inhibitor", applicant="Alpha", legal_status="ACTIVE", priority_day=1
    )
    _patent(
        session, tenant, "WO2026000102", "Second inhibitor", applicant="Alpha", legal_status="ACTIVE", priority_day=2
    )
    entity = _entity(session, tenant, EntityType.PATENT, "WO2025000103")
    session.add(
        PatentFamily(
            tenant_id=tenant.id,
            entity_id=entity.id,
            family_identifier="WO2025000103",
            title="Legacy composition without status",
            priority_date=datetime(2025, 3, 1, tzinfo=UTC),
            applicants=["Beta"],
        )
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_patent_families(None, None, None, 1, 0)

    assert len(result.items) == 1
    landscape = result.landscape
    assert landscape.total_families == 3
    assert {(bucket.key, bucket.count) for bucket in landscape.legal_status} == {("ACTIVE", 2), ("__missing__", 1)}
    missing = next(bucket for bucket in landscape.legal_status if bucket.key == "__missing__")
    assert missing.label == "未披露"
    assert {(bucket.key, bucket.count) for bucket in landscape.top_applicants} == {("Alpha", 2), ("Beta", 1)}
    years = [bucket.key for bucket in landscape.priority_year]
    assert years == ["2025", "2024"]
    assert sum(bucket.count for bucket in landscape.priority_year) == 3
    assert abs(sum(bucket.share for bucket in landscape.legal_status) - 1.0) < 1e-9


def test_patent_landscape_respects_applied_filters(session: Session, tenant: Tenant) -> None:
    _patent(session, tenant, "WO2026000201", "Active one", applicant="Alpha", legal_status="ACTIVE", priority_day=1)
    _patent(session, tenant, "WO2026000202", "Expired one", applicant="Beta", legal_status="EXPIRED", priority_day=2)
    session.commit()

    result = IntelligenceService(session, tenant.id).search_patent_families(None, None, "ACTIVE", 25, 0)

    assert result.landscape.total_families == 1
    assert [bucket.key for bucket in result.landscape.legal_status] == ["ACTIVE"]
    assert [bucket.key for bucket in result.landscape.top_applicants] == ["Alpha"]


def test_patent_search_filters_by_priority_and_expiration_windows(session: Session, tenant: Tenant) -> None:
    """Date windows must bound the full result set inclusively and reject out-of-window rows."""

    _patent(session, tenant, "WO2026000301", "Early priority", applicant="Alpha", legal_status="ACTIVE", priority_day=1)
    _patent(session, tenant, "WO2026000302", "Late priority", applicant="Alpha", legal_status="ACTIVE", priority_day=20)
    session.commit()

    inside = IntelligenceService(session, tenant.id).search_patent_families(
        None,
        None,
        None,
        25,
        0,
        priority_from=datetime(2024, 1, 1, tzinfo=UTC),
        priority_to=datetime(2024, 1, 10, tzinfo=UTC),
    )
    assert inside.total == 1
    assert inside.items[0].family_identifier == "WO2026000301"
    assert {f.field for f in inside.applied_filters} == {"priority_from", "priority_to"}

    empty = IntelligenceService(session, tenant.id).search_patent_families(
        None,
        None,
        None,
        25,
        0,
        priority_from=datetime(2025, 6, 1, tzinfo=UTC),
    )
    assert empty.total == 0
    assert empty.landscape.total_families == 0
