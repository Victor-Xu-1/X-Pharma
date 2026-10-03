from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    DealAssetAssociation,
    DealDirection,
    DealPartyAssociation,
    DealPartyRole,
    DealProfile,
    DealRight,
    DealRightType,
    DealStatus,
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityType,
    Relationship,
    ReviewStatus,
    Tenant,
)
from pharma_intel.schemas import DealSavedSearchQuery
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


def _deal(
    session: Session,
    tenant: Tenant,
    name: str,
    *,
    deal_type: str,
    territory: str,
    announced_day: int,
    parties: list[Entity] | None = None,
    assets: list[Entity] | None = None,
    status: DealStatus = DealStatus.UNKNOWN,
    direction: DealDirection = DealDirection.UNDISCLOSED,
    direction_reference_jurisdiction: str | None = None,
    terminated_day: int | None = None,
    updated_day: int | None = None,
    party_roles: list[tuple[Entity, DealPartyRole]] | None = None,
    asset_stages: list[tuple[Entity, str]] | None = None,
    rights: list[tuple[Entity, DealRightType, str, bool | None]] | None = None,
) -> tuple[DealProfile, Entity]:
    entity = _entity(session, tenant, EntityType.TRANSACTION, name)
    deal = DealProfile(
        tenant_id=tenant.id,
        entity_id=entity.id,
        deal_type=deal_type,
        status=status.value,
        direction=direction.value,
        direction_reference_jurisdiction=direction_reference_jurisdiction,
        announced_at=datetime(2026, 1, announced_day, tzinfo=UTC),
        terminated_at=datetime(2026, 2, terminated_day, tzinfo=UTC) if terminated_day else None,
        source_updated_at=datetime(2026, 3, updated_day, tzinfo=UTC) if updated_day else None,
        parties=[
            {"entity_id": party.id, "name": party.name, "entity_type": party.entity_type.value}
            for party in parties or []
        ],
        asset_entity_ids=[asset.id for asset in assets or []],
        territory=territory,
        upfront_amount=25_000_000,
        total_potential_amount=500_000_000,
        currency="USD",
        terms={"royalties": "tiered"},
    )
    session.add(deal)
    session.flush()
    session.add_all(
        [
            DealPartyAssociation(
                tenant_id=tenant.id,
                deal_id=deal.id,
                party_entity_id=party.id,
                role=role.value,
                country_region="US" if role == DealPartyRole.LICENSOR else "China",
                organization_type="biopharma",
            )
            for party, role in party_roles or []
        ]
        + [
            DealAssetAssociation(
                tenant_id=tenant.id,
                deal_id=deal.id,
                asset_entity_id=asset.id,
                development_phase_at_transaction=phase,
            )
            for asset, phase in asset_stages or []
        ]
        + [
            DealRight(
                tenant_id=tenant.id,
                deal_id=deal.id,
                holder_entity_id=holder.id,
                right_type=right_type.value,
                territory=right_territory,
                exclusive=exclusive,
                scope_description="Governed commercial scope",
            )
            for holder, right_type, right_territory, exclusive in rights or []
        ]
    )
    return deal, entity


def test_entity_dossier_returns_typed_deal_links(
    session: Session,
    tenant: Tenant,
) -> None:
    company = _entity(session, tenant, EntityType.ORGANIZATION, "Acme Pharma")
    drug = _entity(session, tenant, EntityType.DRUG, "Compound A")
    _deal(
        session,
        tenant,
        "Compound A global license",
        deal_type="license",
        territory="Global",
        announced_day=1,
        parties=[company],
        assets=[drug],
        direction=DealDirection.OUTBOUND,
        direction_reference_jurisdiction="US",
        party_roles=[(company, DealPartyRole.LICENSOR)],
        asset_stages=[(drug, DevelopmentPhase.PHASE_2.value)],
    )
    session.commit()

    dossier = IntelligenceService(session, tenant.id).entity_dossier(company.id, limit=10)

    assert dossier is not None
    assert len(dossier.deals) == 1
    deal = dossier.deals[0]
    assert deal.name == "Compound A global license"
    assert deal.party_roles[0].id == company.id
    assert deal.party_roles[0].entity_type == EntityType.ORGANIZATION
    assert deal.asset_stages[0].id == drug.id
    assert deal.asset_stages[0].entity_type == EntityType.DRUG


def test_deal_search_filters_facets_and_returns_linked_entities(session: Session, tenant: Tenant) -> None:
    acme = _entity(session, tenant, EntityType.ORGANIZATION, "Acme Pharma")
    beta = _entity(session, tenant, EntityType.ORGANIZATION, "Beta Bio")
    asset = _entity(session, tenant, EntityType.DRUG, "VX-101")
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    disease = _entity(session, tenant, EntityType.DISEASE, "Non-small cell lung cancer")
    deal, deal_entity = _deal(
        session,
        tenant,
        "Acme-Beta VX-101 license",
        deal_type="license",
        territory="global",
        announced_day=20,
        parties=[acme, beta],
        assets=[asset],
        status=DealStatus.ACTIVE,
        direction=DealDirection.OUTBOUND,
        direction_reference_jurisdiction="US",
        updated_day=15,
        party_roles=[
            (acme, DealPartyRole.LICENSOR),
            (beta, DealPartyRole.LICENSEE),
        ],
        asset_stages=[(asset, "phase_2")],
        rights=[(beta, DealRightType.COMMERCIALIZATION, "Greater China", True)],
    )
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=asset.id,
            target_entity_id=target.id,
            disease_entity_id=disease.id,
            modality="antibody",
            phase=DevelopmentPhase.PHASE_3,
            program_tags=["first_in_class"],
            status_date=datetime(2026, 7, 1, tzinfo=UTC),
        )
    )
    for predicate, linked in [("deal_party", acme), ("deal_party", beta), ("deal_asset", asset)]:
        session.add(
            Relationship(
                tenant_id=tenant.id,
                subject_id=deal_entity.id,
                predicate=predicate,
                object_id=linked.id,
            )
        )
    _deal(
        session,
        tenant,
        "Other research collaboration",
        deal_type="collaboration",
        territory="China",
        announced_day=10,
    )
    other_tenant = Tenant(slug="other-deal", name="Other Deal Tenant")
    session.add(other_tenant)
    session.flush()
    _deal(
        session,
        other_tenant,
        "Hidden tenant license",
        deal_type="license",
        territory="global",
        announced_day=25,
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_deals(
        "VX-101",
        "license",
        "global",
        "Acme Pharma",
        100,
        0,
        status=DealStatus.ACTIVE.value,
        direction=DealDirection.OUTBOUND.value,
        direction_reference_jurisdiction="US",
        asset_entity_id=asset.id,
        target_entity_id=target.id,
        disease_entity_id=disease.id,
        asset_modality=["antibody", "small molecule"],
        asset_program_tag=["first_in_class", "best_in_class"],
        party_entity_id=acme.id,
        party_role=DealPartyRole.LICENSOR.value,
        party_country_region="US",
        party_organization_type="biopharma",
        development_phase_at_transaction="phase_2",
        current_development_phase="phase_3",
        right_type=DealRightType.COMMERCIALIZATION.value,
        rights_territory="Greater China",
        currency="USD",
        announced_from=datetime(2026, 1, 1, tzinfo=UTC),
        announced_to=datetime(2026, 1, 31, tzinfo=UTC),
        source_updated_from=datetime(2026, 3, 1, tzinfo=UTC),
        source_updated_to=datetime(2026, 3, 31, tzinfo=UTC),
        upfront_amount_min=20_000_000,
        upfront_amount_max=30_000_000,
        total_potential_amount_min=400_000_000,
        total_potential_amount_max=600_000_000,
    )

    assert result.total == 1
    assert result.query_schema_version == "pharma.deal.search.v8"
    assert result.landscape.total_deals == 1
    assert result.landscape.limit == 8
    assert [(bucket.key, bucket.count, bucket.share) for bucket in result.landscape.deal_type] == [("license", 1, 1.0)]
    assert [(bucket.key, bucket.count) for bucket in result.landscape.asset_modality] == [("antibody", 1)]
    assert result.sort_by == "announced_at"
    assert result.sort_direction == "desc"
    applied = {item.field: item.value for item in result.applied_filters}
    assert applied["q"] == "VX-101"
    assert applied["status"] == DealStatus.ACTIVE.value
    assert applied["direction"] == DealDirection.OUTBOUND.value
    assert applied["asset_entity_id"] == asset.id
    assert applied["target_entity_id"] == target.id
    assert applied["disease_entity_id"] == disease.id
    assert applied["asset_modality"] == ["antibody", "small molecule"]
    assert applied["asset_program_tag"] == ["first_in_class", "best_in_class"]
    assert applied["party_entity_id"] == acme.id
    assert applied["party_role"] == DealPartyRole.LICENSOR.value
    assert applied["party_country_region"] == "US"
    assert applied["party_organization_type"] == "biopharma"
    assert applied["development_phase_at_transaction"] == "phase_2"
    assert applied["current_development_phase"] == "phase_3"
    assert applied["right_type"] == DealRightType.COMMERCIALIZATION.value
    assert applied["rights_territory"] == "Greater China"
    assert applied["upfront_amount_min"] == 20_000_000
    assert applied["total_potential_amount_max"] == 600_000_000
    assert result.facets == {
        "deal_type": {"license": 1},
        "status": {"active": 1},
        "direction": {"outbound": 1},
        "territory": {"global": 1},
        "currency": {"USD": 1},
        "asset": {"VX-101": 1},
        "target": {"EGFR": 1},
        "disease": {"Non-small cell lung cancer": 1},
        "asset_modality": {"antibody": 1},
        "asset_program_tag": {"first_in_class": 1},
        "party": {"Acme Pharma": 1, "Beta Bio": 1},
        "party_role": {"licensee": 1, "licensor": 1},
        "party_country_region": {"China": 1, "US": 1},
        "party_organization_type": {"biopharma": 1},
        "development_phase_at_transaction": {"phase_2": 1},
        "current_development_phase": {"phase_3": 1},
        "right_type": {"commercialization": 1},
        "rights_territory": {"Greater China": 1},
    }
    assert result.items[0].id == deal.id
    assert result.items[0].name == "Acme-Beta VX-101 license"
    assert [(item.entity_type.value, item.name) for item in result.items[0].party_entities] == [
        ("organization", "Acme Pharma"),
        ("organization", "Beta Bio"),
    ]
    assert [(item.entity_type.value, item.name) for item in result.items[0].asset_entities] == [("drug", "VX-101")]
    assert [(item.name, item.role.value) for item in result.items[0].party_roles] == [
        ("Beta Bio", "licensee"),
        ("Acme Pharma", "licensor"),
    ]
    assert result.items[0].asset_stages[0].development_phase_at_transaction == "phase_2"
    assert result.items[0].asset_stages[0].current_development_phase == "phase_3"
    assert result.items[0].asset_stages[0].current_phase_as_of is not None
    assert result.items[0].rights[0].holder_name == "Beta Bio"
    assert result.items[0].rights[0].right_type == DealRightType.COMMERCIALIZATION
    assert result.items[0].rights[0].territory == "Greater China"
    assert result.items[0].rights[0].exclusive is True
    assert result.warnings == ["未观察到交易不代表不存在；结果受数据授权、披露完整性、金额口径和治理状态限制。"]
    assert (
        IntelligenceService(session, tenant.id)
        .search_deals(None, None, None, None, 100, 0, asset_modality=["small_molecule"])
        .total
        == 0
    )


def test_deal_landscape_uses_full_match_set_and_exposes_missing_scalar_values(
    session: Session,
    tenant: Tenant,
) -> None:
    _deal(
        session,
        tenant,
        "First disclosed license",
        deal_type="license",
        territory="global",
        announced_day=10,
        status=DealStatus.ACTIVE,
        direction=DealDirection.OUTBOUND,
        direction_reference_jurisdiction="US",
    )
    missing_currency, _ = _deal(
        session,
        tenant,
        "Undisclosed currency collaboration",
        deal_type="collaboration",
        territory="China",
        announced_day=11,
        status=DealStatus.COMPLETED,
        direction=DealDirection.DOMESTIC,
        direction_reference_jurisdiction="China",
    )
    missing_currency.currency = None
    session.commit()

    result = IntelligenceService(session, tenant.id).search_deals(
        None,
        None,
        None,
        None,
        1,
        0,
        landscape_limit=5,
    )

    assert len(result.items) == 1
    assert result.total == 2
    assert result.landscape.total_deals == 2
    assert result.landscape.limit == 5
    assert [(bucket.key, bucket.count, bucket.share) for bucket in result.landscape.currency] == [
        ("USD", 1, 0.5),
        ("__missing__", 1, 0.5),
    ]
    assert {(bucket.key, bucket.count) for bucket in result.landscape.deal_type} == {
        ("license", 1),
        ("collaboration", 1),
    }


def test_deal_search_uses_structured_links_without_relationship_or_legacy_payload(
    session: Session,
    tenant: Tenant,
) -> None:
    party = _entity(session, tenant, EntityType.ORGANIZATION, "Structured Pharma")
    asset = _entity(session, tenant, EntityType.DRUG, "Structured-101")
    deal, _ = _deal(
        session,
        tenant,
        "Structured transaction",
        deal_type="license",
        territory="global",
        announced_day=21,
        party_roles=[(party, DealPartyRole.LICENSOR)],
        asset_stages=[(asset, "phase_1")],
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    result = service.search_deals("Structured-101", "license", "global", "Structured Pharma", 100, 0)
    by_party = service.search_deals(None, None, None, None, 100, 0, entity_id=party.id)
    by_asset = service.search_deals(None, None, None, None, 100, 0, entity_id=asset.id)

    assert [item.id for item in result.items] == [deal.id]
    assert result.facets["party"] == {"Structured Pharma": 1}
    assert [item.id for item in by_party.items] == [deal.id]
    assert [item.id for item in by_asset.items] == [deal.id]


def test_deal_asset_multiselect_uses_or_within_dimensions_and_same_program_across_dimensions(
    session: Session,
    tenant: Tenant,
) -> None:
    asset = _entity(session, tenant, EntityType.DRUG, "Multi-101")
    first_target = _entity(session, tenant, EntityType.TARGET, "TARGET-A")
    second_target = _entity(session, tenant, EntityType.TARGET, "TARGET-B")
    deal, _ = _deal(
        session,
        tenant,
        "Multi-101 collaboration",
        deal_type="collaboration",
        territory="global",
        announced_day=22,
        asset_stages=[(asset, "preclinical")],
    )
    session.add_all(
        [
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=asset.id,
                target_entity_id=first_target.id,
                modality="antibody",
                phase=DevelopmentPhase.PRECLINICAL,
                program_tags=["first_in_class"],
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=asset.id,
                target_entity_id=second_target.id,
                modality="small molecule",
                phase=DevelopmentPhase.PRECLINICAL,
                program_tags=["best_in_class"],
            ),
        ]
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    cross_program_false_positive = service.search_deals(
        None,
        None,
        None,
        None,
        100,
        0,
        asset_modality=["antibody"],
        asset_program_tag=["best_in_class"],
    )
    matching_second_program = service.search_deals(
        None,
        None,
        None,
        None,
        100,
        0,
        asset_modality=["antibody", "small molecule"],
        asset_program_tag=["best_in_class", "next_generation"],
    )

    assert cross_program_false_positive.total == 0
    assert [item.id for item in matching_second_program.items] == [deal.id]
    assert {item.field: (item.operator, item.value) for item in matching_second_program.applied_filters} == {
        "asset_modality": ("in", ["antibody", "small molecule"]),
        "asset_program_tag": ("in", ["best_in_class", "next_generation"]),
    }

    legacy_query = DealSavedSearchQuery.model_validate(
        {"asset_modality": "antibody", "asset_program_tag": "first_in_class"}
    )
    assert legacy_query.asset_modality == ["antibody"]
    assert legacy_query.asset_program_tag == ["first_in_class"]
    assert legacy_query.display_mode == "list"
    assert legacy_query.analysis_dimension == "all"
    assert legacy_query.analysis_view == "chart"
    assert legacy_query.analysis_limit == 8


def test_deal_asset_attributes_and_phases_bind_to_the_selected_asset(
    session: Session,
    tenant: Tenant,
) -> None:
    selected_asset = _entity(session, tenant, EntityType.DRUG, "Selected-101")
    decoy_asset = _entity(session, tenant, EntityType.DRUG, "Decoy-202")
    selected_target = _entity(session, tenant, EntityType.TARGET, "SELECTED-TARGET")
    selected_disease = _entity(session, tenant, EntityType.DISEASE, "Selected disease")
    decoy_target = _entity(session, tenant, EntityType.TARGET, "DECOY-TARGET")
    decoy_disease = _entity(session, tenant, EntityType.DISEASE, "Decoy disease")
    false_positive, _ = _deal(
        session,
        tenant,
        "Cross-asset false positive",
        deal_type="license",
        territory="global",
        announced_day=23,
        asset_stages=[(selected_asset, "preclinical"), (decoy_asset, "phase_2")],
    )
    session.add_all(
        [
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=selected_asset.id,
                target_entity_id=selected_target.id,
                disease_entity_id=selected_disease.id,
                modality="small molecule",
                phase=DevelopmentPhase.PRECLINICAL,
                program_tags=["follow_on"],
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=decoy_asset.id,
                target_entity_id=decoy_target.id,
                disease_entity_id=decoy_disease.id,
                modality="antibody",
                phase=DevelopmentPhase.PHASE_3,
                program_tags=["first_in_class"],
            ),
        ]
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    result = service.search_deals(
        None,
        None,
        None,
        None,
        100,
        0,
        asset_entity_id=selected_asset.id,
        target_entity_id=selected_target.id,
        disease_entity_id=selected_disease.id,
        asset_modality=["antibody"],
        asset_program_tag=["first_in_class"],
        development_phase_at_transaction="phase_2",
        current_development_phase="phase_3",
    )

    assert result.total == 0
    assert false_positive.id not in {item.id for item in result.items}


def test_deal_search_escapes_wildcards_supports_legacy_links_and_paginates(
    session: Session,
    tenant: Tenant,
) -> None:
    party = _entity(session, tenant, EntityType.ORGANIZATION, "Legacy Bio")
    asset = _entity(session, tenant, EntityType.DRUG, "Legacy-101")
    _deal(
        session,
        tenant,
        "Legacy license",
        deal_type="license",
        territory="US",
        announced_day=1,
        parties=[party],
        assets=[asset],
    )
    _deal(
        session,
        tenant,
        "Newer collaboration",
        deal_type="collaboration",
        territory="EU",
        announced_day=2,
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    assert service.search_deals("%", None, None, None, 100, 0).total == 0
    legacy = service.search_deals(None, None, None, None, 100, 0, entity_id=asset.id)
    assert legacy.total == 1
    assert [(item.entity_type.value, item.name) for item in legacy.items[0].party_entities] == [
        ("organization", "Legacy Bio")
    ]
    assert [(item.entity_type.value, item.name) for item in legacy.items[0].asset_entities] == [("drug", "Legacy-101")]
    first = service.search_deals(None, None, None, None, 1, 0)
    second = service.search_deals(None, None, None, None, 1, 1)
    assert first.total == second.total == 2
    assert first.items[0].deal_type == "collaboration"
    assert second.items[0].deal_type == "license"


def test_deal_api_validates_ranges_and_returns_role_stage_rights_and_detail(
    session: Session,
    tenant: Tenant,
) -> None:
    licensor = _entity(session, tenant, EntityType.ORGANIZATION, "Originator Pharma")
    licensee = _entity(session, tenant, EntityType.ORGANIZATION, "Regional Bio")
    asset = _entity(session, tenant, EntityType.DRUG, "RG-202")
    target = _entity(session, tenant, EntityType.TARGET, "ALK")
    disease = _entity(session, tenant, EntityType.DISEASE, "Lung cancer")
    deal, _deal_entity = _deal(
        session,
        tenant,
        "Originator-Regional RG-202 license",
        deal_type="license",
        territory="Greater China",
        announced_day=20,
        parties=[licensor, licensee],
        assets=[asset],
        status=DealStatus.TERMINATED,
        direction=DealDirection.OUTBOUND,
        direction_reference_jurisdiction="US",
        terminated_day=5,
        updated_day=10,
        party_roles=[
            (licensor, DealPartyRole.LICENSOR),
            (licensee, DealPartyRole.LICENSEE),
        ],
        asset_stages=[(asset, "phase_1")],
        rights=[(licensee, DealRightType.DEVELOPMENT, "Greater China", True)],
    )
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=asset.id,
            target_entity_id=target.id,
            disease_entity_id=disease.id,
            modality="antibody",
            phase=DevelopmentPhase.PHASE_2,
            program_tags=["first_in_class"],
            status_date=datetime(2026, 3, 12, tzinfo=UTC),
        )
    )
    other_tenant = Tenant(slug="hidden-deal-api", name="Hidden Deal API Tenant")
    session.add(other_tenant)
    session.flush()
    hidden, _hidden_entity = _deal(
        session,
        other_tenant,
        "Hidden transaction",
        deal_type="license",
        territory="global",
        announced_day=21,
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "deal-api-test", "api_key", frozenset({"deals:read"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/deal-transactions",
                params=[
                    ("asset_modality", "antibody"),
                    ("asset_modality", "small molecule"),
                    ("asset_program_tag", "first_in_class"),
                    ("asset_program_tag", "best_in_class"),
                    *(
                        (key, str(value))
                        for key, value in {
                            "analysis_top": 5,
                            "status": "terminated",
                            "direction": "outbound",
                            "direction_reference_jurisdiction": "US",
                            "asset_entity_id": asset.id,
                            "target_entity_id": target.id,
                            "disease_entity_id": disease.id,
                            "party_entity_id": licensor.id,
                            "party_role": "licensor",
                            "party_country_region": "US",
                            "party_organization_type": "biopharma",
                            "development_phase_at_transaction": "phase_1",
                            "current_development_phase": "phase_2",
                            "right_type": "development",
                            "rights_territory": "Greater China",
                            "currency": "USD",
                            "announced_from": "2026-01-01T00:00:00Z",
                            "announced_to": "2026-01-31T23:59:59Z",
                            "terminated_from": "2026-02-01T00:00:00Z",
                            "terminated_to": "2026-02-28T23:59:59Z",
                            "source_updated_from": "2026-03-01T00:00:00Z",
                            "source_updated_to": "2026-03-31T23:59:59Z",
                            "upfront_amount_min": 20_000_000,
                            "upfront_amount_max": 30_000_000,
                            "total_potential_amount_min": 400_000_000,
                            "total_potential_amount_max": 600_000_000,
                        }.items()
                    ),
                ],
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert [item["id"] for item in body["items"]] == [deal.id]
            assert body["query_schema_version"] == "pharma.deal.search.v8"
            assert body["landscape"]["total_deals"] == 1
            assert body["landscape"]["limit"] == 5
            assert body["landscape"]["status"] == [
                {"key": "terminated", "label": "terminated", "count": 1, "share": 1.0}
            ]
            assert body["sort_by"] == "announced_at"
            assert body["sort_direction"] == "desc"
            assert body["items"][0]["party_roles"][0]["role"] == "licensee"
            assert body["items"][0]["asset_stages"][0]["development_phase_at_transaction"] == "phase_1"
            assert body["items"][0]["rights"][0]["right_type"] == "development"
            applied = {item["field"]: item["value"] for item in body["applied_filters"]}
            assert applied["asset_entity_id"] == asset.id
            assert applied["target_entity_id"] == target.id
            assert applied["disease_entity_id"] == disease.id
            assert applied["asset_modality"] == ["antibody", "small molecule"]
            assert applied["asset_program_tag"] == ["first_in_class", "best_in_class"]

            detail = client.get(f"/api/v1/deal-transactions/{deal.id}")
            assert detail.status_code == 200
            assert detail.json()["direction"] == "outbound"
            assert detail.json()["rights"][0]["holder_name"] == "Regional Bio"
            assert client.get(f"/api/v1/deal-transactions/{hidden.id}").status_code == 404

            reversed_date = client.get(
                "/api/v1/deal-transactions",
                params={
                    "announced_from": "2026-02-01T00:00:00Z",
                    "announced_to": "2026-01-01T00:00:00Z",
                },
            )
            assert reversed_date.status_code == 422
            assert reversed_date.json()["detail"] == "announced_from must not be after announced_to"

            reversed_amount = client.get(
                "/api/v1/deal-transactions",
                params={"upfront_amount_min": 30_000_000, "upfront_amount_max": 20_000_000},
            )
            assert reversed_amount.status_code == 422
            assert reversed_amount.json()["detail"] == "upfront_amount_min must not exceed upfront_amount_max"

            missing_timezone = client.get(
                "/api/v1/deal-transactions",
                params={"source_updated_from": "2026-03-01T00:00:00"},
            )
            assert missing_timezone.status_code == 422
            assert missing_timezone.json()["detail"] == "source_updated_from must include a timezone offset"

            invalid_analysis_top = client.get("/api/v1/deal-transactions", params={"analysis_top": 7})
            assert invalid_analysis_top.status_code == 422
            assert invalid_analysis_top.json()["detail"] == "analysis_top must be one of 5, 8, 20 or 50"
    finally:
        app.dependency_overrides.clear()


def test_deal_search_sorts_full_result_set_and_requires_currency_for_amounts(
    session: Session,
    tenant: Tenant,
) -> None:
    zeta, _ = _deal(
        session,
        tenant,
        "Zeta transaction",
        deal_type="license",
        territory="global",
        announced_day=1,
    )
    alpha, _ = _deal(
        session,
        tenant,
        "Alpha transaction",
        deal_type="collaboration",
        territory="China",
        announced_day=2,
    )
    zeta.upfront_amount = 30_000_000
    alpha.upfront_amount = 10_000_000
    session.commit()

    service = IntelligenceService(session, tenant.id)
    by_name = service.search_deals(None, None, None, None, 1, 0, sort_by="name", sort_direction="asc")
    by_amount = service.search_deals(
        None,
        None,
        None,
        None,
        1,
        0,
        currency="USD",
        sort_by="upfront_amount",
        sort_direction="desc",
    )

    assert by_name.items[0].id == alpha.id
    assert by_name.sort_by == "name"
    assert by_name.sort_direction == "asc"
    assert by_amount.items[0].id == zeta.id
    multi_sorted = service.search_deals(
        None,
        None,
        None,
        None,
        2,
        0,
        sort=(SortClause(field="status", direction="asc"), SortClause(field="name", direction="desc")),
    )
    assert [item.id for item in multi_sorted.items] == [zeta.id, alpha.id]
    assert [criterion.model_dump() for criterion in multi_sorted.sort] == [
        {"field": "status", "direction": "asc"},
        {"field": "name", "direction": "desc"},
    ]
    with pytest.raises(ValueError, match="currency is required"):
        service.search_deals(None, None, None, None, 1, 0, sort_by="upfront_amount")
    with pytest.raises(ValueError, match="currency is required"):
        service.search_deals(
            None,
            None,
            None,
            None,
            1,
            0,
            sort=(SortClause(field="name", direction="asc"), SortClause(field="upfront_amount", direction="desc")),
        )
