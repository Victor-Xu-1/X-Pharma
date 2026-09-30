from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    DealProfile,
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityType,
    Relationship,
    ReviewStatus,
    Tenant,
)
from pharma_intel.security import Principal, require_principal


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


def test_company_timeline_combines_dated_pipeline_and_transaction_events(
    session: Session,
    tenant: Tenant,
) -> None:
    company = _entity(session, tenant, EntityType.ORGANIZATION, "Victor Therapeutics")
    counterparty = _entity(session, tenant, EntityType.ORGANIZATION, "Partner Bio")
    drug = _entity(session, tenant, EntityType.DRUG, "VX-101")
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    disease = _entity(session, tenant, EntityType.DISEASE, "NSCLC")
    program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=drug.id,
        target_entity_id=target.id,
        disease_entity_id=disease.id,
        organization_entity_id=company.id,
        modality="small molecule",
        mechanism_of_action="covalent inhibitor",
        phase=DevelopmentPhase.PHASE_2,
        status_date=datetime(2026, 3, 1, tzinfo=UTC),
        geography="Global",
        status_detail="Recruiting",
        status_history=[
            {
                "phase": "phase_1",
                "status": "completed",
                "effective_at": "2025-06-01T00:00:00Z",
                "geography": "Global",
            }
        ],
        milestones=[
            {
                "milestone_type": "first_patient_in",
                "title": "Phase 2 first patient in",
                "occurred_at": "2026-03-01T00:00:00Z",
                "geography": "Global",
            }
        ],
    )
    session.add(program)
    session.flush()

    deal_entity = _entity(session, tenant, EntityType.TRANSACTION, "VX-101 global license")
    deal = DealProfile(
        tenant_id=tenant.id,
        entity_id=deal_entity.id,
        deal_type="license",
        announced_at=datetime(2026, 4, 1, tzinfo=UTC),
        parties=[
            {"entity_id": company.id, "name": company.name, "entity_type": company.entity_type.value},
            {
                "entity_id": counterparty.id,
                "name": counterparty.name,
                "entity_type": counterparty.entity_type.value,
            },
        ],
        asset_entity_ids=[drug.id],
        territory="Global",
        upfront_amount=50_000_000,
        total_potential_amount=750_000_000,
        currency="USD",
        terms={"royalties": "tiered"},
    )
    session.add(deal)
    session.flush()
    for predicate, linked in (
        ("deal_party", company),
        ("deal_party", counterparty),
        ("deal_asset", drug),
    ):
        session.add(
            Relationship(
                tenant_id=tenant.id,
                subject_id=deal_entity.id,
                predicate=predicate,
                object_id=linked.id,
            )
        )

    undated_drug = _entity(session, tenant, EntityType.DRUG, "VX-UNDATED")
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=undated_drug.id,
            organization_entity_id=company.id,
            phase=DevelopmentPhase.DISCOVERY,
        )
    )

    other_tenant = Tenant(slug="other-company-timeline", name="Other Company Timeline")
    session.add(other_tenant)
    session.flush()
    hidden_company = _entity(session, other_tenant, EntityType.ORGANIZATION, "Hidden Company")
    hidden_drug = _entity(session, other_tenant, EntityType.DRUG, "HIDDEN-1")
    session.add(
        DevelopmentProgram(
            tenant_id=other_tenant.id,
            drug_entity_id=hidden_drug.id,
            organization_entity_id=hidden_company.id,
            phase=DevelopmentPhase.APPROVED,
            status_date=datetime(2026, 5, 1, tzinfo=UTC),
        )
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    first = service.company_timeline(company.id, 1, 0)
    second = service.company_timeline(company.id, 1, 1)

    assert first is not None
    assert second is not None
    assert first.company.id == company.id
    assert first.total == second.total == 2
    assert first.facets == {
        "event_type": {"deal_announced": 1, "program_status": 1},
        "phase": {"phase_2": 1},
        "deal_type": {"license": 1},
    }
    assert first.items[0].event_type == "deal_announced"
    assert first.items[0].deal is not None
    assert first.items[0].deal.id == deal.id
    assert [item.name for item in first.items[0].deal.party_entities] == ["Partner Bio", "Victor Therapeutics"]
    assert second.items[0].event_type == "program_status"
    assert second.items[0].program is not None
    assert second.items[0].program.id == program.id
    assert second.items[0].program.status_history[0].phase == "phase_1"
    assert second.items[0].program.milestones[0].milestone_type == "first_patient_in"
    assert first.warnings == [
        "时间线仅包含具有明确日期的管线当前状态和已披露交易公告；未观察到记录不代表公司不存在相关活动。"
    ]

    assert service.company_timeline(drug.id, 10, 0) is None
    assert service.company_timeline(hidden_company.id, 10, 0) is None

    dossier = service.company_dossier(company.id, 100)
    assert dossier is not None
    assert dossier.entity.id == company.id
    assert dossier.summary.model_dump() == {
        "program_count": 2,
        "drug_count": 2,
        "target_count": 1,
        "indication_count": 1,
        "deal_count": 1,
        "timeline_event_count": 2,
        "modalities": ["small molecule"],
        "phase_distribution": {"phase_2": 1, "discovery": 1},
        "highest_phase": DevelopmentPhase.PHASE_2,
        "latest_activity_at": datetime(2026, 4, 1, tzinfo=UTC),
    }
    assert dossier.timeline.items[0].deal is not None
    assert service.company_dossier(drug.id, 100) is None
    assert service.company_dossier(hidden_company.id, 100) is None


def test_company_timeline_api_requires_pipeline_and_deal_scopes(session: Session, tenant: Tenant) -> None:
    company = _entity(session, tenant, EntityType.ORGANIZATION, "Scoped Pharma")
    drug = _entity(session, tenant, EntityType.DRUG, "SCOPED-1")
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=drug.id,
            organization_entity_id=company.id,
            phase=DevelopmentPhase.PRECLINICAL,
            status_date=datetime(2026, 2, 1, tzinfo=UTC),
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "analyst",
        "user",
        frozenset({"pipelines:read"}),
    )
    try:
        with TestClient(app) as client:
            denied = client.get(f"/api/v1/companies/{company.id}/timeline")
            assert denied.status_code == 403

            app.dependency_overrides[require_principal] = lambda: Principal(
                tenant.id,
                "analyst",
                "user",
                frozenset({"pipelines:read", "deals:read"}),
            )
            response = client.get(f"/api/v1/companies/{company.id}/timeline")
            assert response.status_code == 200
            assert response.json()["items"][0]["program"]["drug_name"] == "SCOPED-1"

            dossier_response = client.get(f"/api/v1/companies/{company.id}/dossier")
            assert dossier_response.status_code == 403

            not_company = client.get(f"/api/v1/companies/{drug.id}/timeline")
            assert not_company.status_code == 404

            app.dependency_overrides[require_principal] = lambda: Principal(
                tenant.id,
                "analyst",
                "user",
                frozenset({"dossiers:read", "pipelines:read", "deals:read"}),
            )
            dossier_response = client.get(f"/api/v1/companies/{company.id}/dossier")
            assert dossier_response.status_code == 200
            assert dossier_response.json()["summary"] == {
                "program_count": 1,
                "drug_count": 1,
                "target_count": 0,
                "indication_count": 0,
                "deal_count": 0,
                "timeline_event_count": 1,
                "modalities": [],
                "phase_distribution": {"preclinical": 1},
                "highest_phase": "preclinical",
                "latest_activity_at": "2026-02-01T00:00:00Z",
            }
            not_company = client.get(f"/api/v1/companies/{drug.id}/dossier")
            assert not_company.status_code == 404
    finally:
        app.dependency_overrides.clear()
