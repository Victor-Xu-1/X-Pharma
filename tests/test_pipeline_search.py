from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Session

from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
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
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    EntityIdentifier,
    EntityType,
    ProgramTargetRole,
    RegulatoryEvent,
    ReviewStatus,
    SourceDocument,
    Tenant,
    TrialEntityRole,
    TrialResultEvaluation,
)
from pharma_intel.schemas import PipelineSavedSearchQuery
from pharma_intel.sorting import SortClause


def _entity(session: Session, tenant: Tenant, entity_type: EntityType, name: str) -> Entity:
    entity = Entity(
        tenant_id=tenant.id,
        entity_type=entity_type,
        name=name,
        normalized_name=name.casefold(),
    )
    session.add(entity)
    session.flush()
    return entity


def test_drug_comparison_profiles_aggregate_the_complete_program_set(
    session: Session,
    tenant: Tenant,
) -> None:
    first_drug = _entity(session, tenant, EntityType.DRUG, "Complete Drug")
    second_drug = _entity(session, tenant, EntityType.DRUG, "Reference Drug")
    target = _entity(session, tenant, EntityType.TARGET, "IFNA2")
    organization = _entity(session, tenant, EntityType.ORGANIZATION, "Complete Biopharma")

    for index in range(105):
        disease = _entity(session, tenant, EntityType.DISEASE, f"Indication {index:03d}")
        session.add(
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=first_drug.id,
                target_entity_id=target.id,
                disease_entity_id=disease.id,
                organization_entity_id=organization.id,
                phase=DevelopmentPhase.APPROVED if index == 104 else DevelopmentPhase.PHASE_2,
                global_phase="approved" if index == 104 else "phase_2",
                china_phase="phase_3" if index == 104 else "phase_1",
                program_status="inactive" if index % 10 == 0 else "active",
                status_date=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=second_drug.id,
            target_entity_id=target.id,
            phase=DevelopmentPhase.PRECLINICAL,
            program_status="active",
        )
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).drug_comparison_profiles([second_drug.id, first_drug.id])

    assert result.query_schema_version == "pharma.drug.comparison.v1"
    assert [item.entity.id for item in result.items] == [second_drug.id, first_drug.id]
    complete = result.items[1]
    assert complete.summary.program_count == 105
    assert complete.summary.indication_count == 105
    assert complete.summary.target_count == 1
    assert complete.summary.organization_count == 1
    assert complete.summary.highest_phase == DevelopmentPhase.APPROVED
    assert complete.summary.highest_global_phase == DevelopmentPhase.APPROVED
    assert complete.summary.highest_china_phase == DevelopmentPhase.PHASE_3
    assert len(complete.indication_names) == 105
    assert complete.indication_names[0] == "Indication 000"
    assert complete.indication_names[-1] == "Indication 104"
    assert complete.target_names == ["IFNA2"]
    assert complete.organization_names == ["Complete Biopharma"]
    assert complete.program_status_counts == {"active": 94, "inactive": 11}


def test_public_drug_comparison_resolves_linked_identity_families(
    session: Session,
    tenant: Tenant,
) -> None:
    drug = _entity(session, tenant, EntityType.DRUG, "Identity-linked drug")
    drug.review_status = ReviewStatus.VERIFIED
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    target.review_status = ReviewStatus.VERIFIED
    target_alias = _entity(session, tenant, EntityType.TARGET, "egfr")
    disease = _entity(session, tenant, EntityType.DISEASE, "Non-small cell lung cancer")
    disease.review_status = ReviewStatus.VERIFIED
    disease_alias = _entity(session, tenant, EntityType.DISEASE, "non-small cell lung cancer")
    organization = _entity(session, tenant, EntityType.ORGANIZATION, "Victor Biopharma")
    organization.review_status = ReviewStatus.VERIFIED
    organization_alias = _entity(session, tenant, EntityType.ORGANIZATION, "victor biopharma")
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=drug.id,
            target_entity_id=target_alias.id,
            disease_entity_id=disease_alias.id,
            organization_entity_id=organization_alias.id,
            phase=DevelopmentPhase.APPROVED,
            global_phase="approved",
            china_phase="phase_2",
            program_status="active",
        )
    )
    session.commit()

    result = IntelligenceService(session, tenant.id, include_unpublished=False).drug_comparison_profiles([drug.id])

    assert len(result.items) == 1
    profile = result.items[0]
    assert profile.summary.program_count == 1
    assert profile.summary.highest_phase == DevelopmentPhase.APPROVED
    assert profile.summary.highest_global_phase == DevelopmentPhase.APPROVED
    assert profile.summary.highest_china_phase == DevelopmentPhase.PHASE_2
    assert profile.summary.target_count == 1
    assert profile.summary.indication_count == 1
    assert profile.summary.organization_count == 1
    assert profile.target_names == ["EGFR"]
    assert profile.indication_names == ["Non-small cell lung cancer"]
    assert profile.organization_names == ["Victor Biopharma"]
    assert profile.program_status_counts == {"active": 1}


def test_public_program_reads_project_draft_links_to_verified_identities(
    session: Session,
    tenant: Tenant,
) -> None:
    drug = _entity(session, tenant, EntityType.DRUG, "Published identity drug")
    drug.review_status = ReviewStatus.VERIFIED
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    target.review_status = ReviewStatus.VERIFIED
    target_alias = _entity(session, tenant, EntityType.TARGET, "EGFR")
    disease = _entity(session, tenant, EntityType.DISEASE, "Non-small cell lung cancer")
    disease.review_status = ReviewStatus.VERIFIED
    disease_alias = _entity(session, tenant, EntityType.DISEASE, "Non-small cell lung cancer")
    organization = _entity(session, tenant, EntityType.ORGANIZATION, "Published Biopharma")
    organization.review_status = ReviewStatus.VERIFIED
    organization_alias = _entity(session, tenant, EntityType.ORGANIZATION, "Published Biopharma")
    program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=drug.id,
        target_entity_id=target_alias.id,
        disease_entity_id=disease_alias.id,
        organization_entity_id=organization_alias.id,
        target_set_version=1,
        target_combination_key=target_alias.id,
        organization_set_version=1,
        phase=DevelopmentPhase.PHASE_2,
        program_status="active",
    )
    session.add(program)
    session.flush()
    session.add_all(
        [
            DevelopmentProgramTarget(
                tenant_id=tenant.id,
                program_id=program.id,
                target_set_version=1,
                target_entity_id=target_alias.id,
                role=ProgramTargetRole.PRIMARY,
                position=0,
            ),
            DevelopmentProgramOrganization(
                tenant_id=tenant.id,
                program_id=program.id,
                organization_set_version=1,
                organization_entity_id=organization_alias.id,
                role="originator",
                position=0,
            ),
        ]
    )
    session.commit()

    public_service = IntelligenceService(session, tenant.id, include_unpublished=False)
    public_portfolio = public_service.drug_programs(drug.id, 25)
    assert public_portfolio is not None
    assert len(public_portfolio.items) == 1
    public_program = public_portfolio.items[0]
    assert public_program.target_entity_id == target.id
    assert public_program.target_name == "EGFR"
    assert [item.entity_id for item in public_program.targets] == [target.id]
    assert public_program.target_combination_key == target.id
    assert public_program.disease_entity_id == disease.id
    assert public_program.disease_name == "Non-small cell lung cancer"
    assert public_program.organization_entity_id == organization.id
    assert public_program.organization_name == "Published Biopharma"
    assert [item.entity_id for item in public_program.organizations] == [organization.id]

    public_search = public_service.search_programs(None, None, None, None, 25, 0, drug_entity_id=drug.id)
    assert len(public_search.items) == 1
    assert public_search.items[0].model_dump(
        include={
            "target_entity_id",
            "target_combination_key",
            "disease_entity_id",
            "organization_entity_id",
        }
    ) == {
        "target_entity_id": target.id,
        "target_combination_key": target.id,
        "disease_entity_id": disease.id,
        "organization_entity_id": organization.id,
    }

    internal_service = IntelligenceService(session, tenant.id, include_unpublished=True)
    internal_portfolio = internal_service.drug_programs(drug.id, 25)
    assert internal_portfolio is not None
    internal_program = internal_portfolio.items[0]
    assert internal_program.target_entity_id == target_alias.id
    assert internal_program.targets[0].entity_id == target_alias.id
    assert internal_program.disease_entity_id == disease_alias.id
    assert internal_program.organization_entity_id == organization_alias.id
    assert internal_program.organizations[0].entity_id == organization_alias.id


def test_public_program_reads_hide_records_with_only_unpublished_linked_entities(
    session: Session,
    tenant: Tenant,
) -> None:
    drug = _entity(session, tenant, EntityType.DRUG, "Draft-only relation drug")
    drug.review_status = ReviewStatus.VERIFIED
    target = _entity(session, tenant, EntityType.TARGET, "Undisclosed research target")
    disease = _entity(session, tenant, EntityType.DISEASE, "Undisclosed indication")
    organization = _entity(session, tenant, EntityType.ORGANIZATION, "Undisclosed sponsor")
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=drug.id,
            target_entity_id=target.id,
            disease_entity_id=disease.id,
            organization_entity_id=organization.id,
            phase=DevelopmentPhase.PRECLINICAL,
        )
    )
    session.commit()

    portfolio = IntelligenceService(session, tenant.id, include_unpublished=False).drug_programs(drug.id, 25)

    assert portfolio is not None
    assert portfolio.items == []
    assert portfolio.total == 0


def test_program_target_role_uses_public_enum_values_in_database_contract() -> None:
    role_type = cast(SqlEnum, DevelopmentProgramTarget.__table__.c.role.type)
    assert role_type.enums == ["primary", "combination"]


def test_pipeline_search_filters_real_programs_and_returns_bounded_facets(session: Session, tenant: Tenant) -> None:
    drug = _entity(session, tenant, EntityType.DRUG, "VX-101")
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    disease = _entity(session, tenant, EntityType.DISEASE, "Non-small cell lung cancer")
    organization = _entity(session, tenant, EntityType.ORGANIZATION, "Victor Therapeutics")
    licensee = _entity(session, tenant, EntityType.ORGANIZATION, "Strategic Bio")
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=drug.id,
            target_entity_id=target.id,
            disease_entity_id=disease.id,
            organization_entity_id=organization.id,
            modality="small molecule",
            mechanism_of_action="covalent inhibitor",
            phase=DevelopmentPhase.PHASE_2,
            geography="Global",
            status_date=datetime(2026, 7, 1, tzinfo=UTC),
            global_phase="phase_2",
            china_phase="phase_1",
            global_phase_started_at=datetime(2026, 6, 1, tzinfo=UTC),
            china_phase_started_at=datetime(2025, 3, 1, tzinfo=UTC),
            development_rights_regions=["Global"],
            commercialization_rights_regions=["Greater China"],
            program_tags=["first_in_class"],
            milestones=[
                {
                    "milestone_type": "first_patient_in",
                    "title": "Global Phase II first patient in",
                    "occurred_at": "2026-06-15T00:00:00+00:00",
                    "geography": "Global",
                }
            ],
        )
    )
    session.add(
        RegulatoryEvent(
            tenant_id=tenant.id,
            subject_entity_id=drug.id,
            agency="FDA",
            jurisdiction="US",
            event_identifier="NDA-VX-101-APPROVAL",
            application_number="NDA 219999",
            event_type="approval",
            status="approved",
            title="VX-101 approved for EGFR-positive NSCLC",
            decision_date=datetime(2026, 7, 15, tzinfo=UTC),
            approved_population="Adults with EGFR-positive non-small cell lung cancer",
            line_of_therapy="second_line",
            biomarker="EGFR exon 20 insertion",
            route_of_administration="oral",
            dosage_form="tablet",
            indication_entity_id=disease.id,
            organization_entity_id=organization.id,
        )
    )
    trial_entity = _entity(session, tenant, EntityType.CLINICAL_TRIAL, "NCTPIPELINE001")
    combination_drug = _entity(session, tenant, EntityType.DRUG, "Carboplatin")
    trial = ClinicalTrialProfile(
        tenant_id=tenant.id,
        entity_id=trial_entity.id,
        registry_name="ClinicalTrials.gov",
        registry_id="NCTPIPELINE001",
        official_title="VX-101 randomized Phase II study",
        acronym="VECTOR-2",
        initiation_type="ist",
        therapy_lines=["second_line"],
        overall_status="COMPLETED",
        phases=["PHASE2"],
        study_type="INTERVENTIONAL",
        enrollment=184,
        start_date=datetime(2024, 1, 12, tzinfo=UTC),
        completion_date=datetime(2026, 4, 30, tzinfo=UTC),
        interventions=[{"name": "VX-101", "type": "DRUG"}, {"name": "Carboplatin", "type": "DRUG"}],
        conditions=["EGFR-positive non-small cell lung cancer"],
        sponsors=[{"name": "Victor Therapeutics", "sponsor_class": "INDUSTRY"}],
        outcomes=[
            {
                "outcome_type": "PRIMARY",
                "measure": "Objective response rate",
                "time_frame": "24 weeks",
                "results": [
                    {
                        "group_label": "VX-101 combination",
                        "value": "68.0",
                        "unit": "%",
                        "participants": 92,
                    }
                ],
            }
        ],
        has_results=True,
        result_evaluation=TrialResultEvaluation.POSITIVE.value,
        results_first_posted=datetime(2026, 7, 10, tzinfo=UTC),
        last_update_posted=datetime(2026, 7, 10, tzinfo=UTC),
    )
    session.add(trial)
    session.flush()
    session.add(
        ClinicalTrialEntityRole(
            tenant_id=tenant.id,
            trial_id=trial.id,
            entity_id=drug.id,
            role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
        )
    )
    session.add_all(
        [
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=trial.id,
                entity_id=combination_drug.id,
                role=TrialEntityRole.COMBINATION_DRUG.value,
            ),
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=trial.id,
                entity_id=target.id,
                role=TrialEntityRole.INVESTIGATIONAL_TARGET.value,
            ),
            ClinicalTrialResultDisclosure(
                tenant_id=tenant.id,
                trial_id=trial.id,
                disclosure_key="ASCO-2026-VECTOR-2",
                version=1,
                disclosure_type="conference_presentation",
                external_id="ASCO-2026-9001",
                title="VECTOR-2 primary analysis",
                disclosed_at=datetime(2026, 5, 31, tzinfo=UTC),
                conference_name="ASCO 2026",
                is_key_result=True,
                result_evaluation=TrialResultEvaluation.POSITIVE.value,
                source_locator="Abstract 9001",
            ),
        ]
    )
    deal_entity = _entity(session, tenant, EntityType.TRANSACTION, "VX-101 Global License")
    deal = DealProfile(
        tenant_id=tenant.id,
        entity_id=deal_entity.id,
        deal_type="license",
        status=DealStatus.ACTIVE.value,
        direction=DealDirection.GLOBAL.value,
        announced_at=datetime(2026, 6, 20, tzinfo=UTC),
        asset_entity_ids=[drug.id],
        territory="Global",
        total_potential_amount=500_000_000,
        currency="USD",
    )
    session.add(deal)
    session.flush()
    session.add(
        DealAssetAssociation(
            tenant_id=tenant.id,
            deal_id=deal.id,
            asset_entity_id=drug.id,
            development_phase_at_transaction=DevelopmentPhase.PHASE_2.value,
        )
    )
    session.add_all(
        [
            DealPartyAssociation(
                tenant_id=tenant.id,
                deal_id=deal.id,
                party_entity_id=organization.id,
                role=DealPartyRole.LICENSOR.value,
                country_region="US",
                organization_type="biopharma",
            ),
            DealPartyAssociation(
                tenant_id=tenant.id,
                deal_id=deal.id,
                party_entity_id=licensee.id,
                role=DealPartyRole.LICENSEE.value,
                country_region="CN",
                organization_type="biotech",
            ),
            DealRight(
                tenant_id=tenant.id,
                deal_id=deal.id,
                holder_entity_id=licensee.id,
                right_type=DealRightType.COMMERCIALIZATION.value,
                territory="Greater China",
                exclusive=True,
                scope_description="Exclusive commercialization rights for VX-101",
            ),
        ]
    )
    other_tenant = Tenant(slug="other-pipeline", name="Other Pipeline Tenant")
    session.add(other_tenant)
    session.flush()
    other_drug = _entity(session, other_tenant, EntityType.DRUG, "HIDDEN-1")
    session.add(
        DevelopmentProgram(
            tenant_id=other_tenant.id,
            drug_entity_id=other_drug.id,
            modality="antibody",
            phase=DevelopmentPhase.APPROVED,
            geography="China",
        )
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    result = service.search_programs(
        "egfr",
        ["small molecule", "antibody"],
        DevelopmentPhase.PHASE_2.value,
        "Global",
        25,
        0,
        status_date_from=datetime(2026, 6, 30, tzinfo=UTC),
        status_date_to=datetime(2026, 7, 2, tzinfo=UTC),
        drug_entity_id=drug.id,
        target_entity_id=target.id,
        disease_entity_id=disease.id,
        organization_entity_id=organization.id,
        global_phase=DevelopmentPhase.PHASE_2.value,
        china_phase=DevelopmentPhase.PHASE_1.value,
        global_phase_started_from=datetime(2026, 5, 1, tzinfo=UTC),
        global_phase_started_to=datetime(2026, 7, 1, tzinfo=UTC),
        china_phase_started_from=datetime(2025, 1, 1, tzinfo=UTC),
        china_phase_started_to=datetime(2025, 4, 1, tzinfo=UTC),
        development_rights_region="Global",
        commercialization_rights_region="Greater China",
        program_tag=["first_in_class", "new_modality"],
        milestone_type="first_patient_in",
        milestone_from=datetime(2026, 6, 1, tzinfo=UTC),
        milestone_to=datetime(2026, 6, 30, tzinfo=UTC),
        has_clinical_results=True,
        clinical_result_evaluation=TrialResultEvaluation.POSITIVE.value,
        has_deal=True,
        deal_currency="USD",
        deal_total_potential_amount_min=400_000_000,
        deal_total_potential_amount_max=600_000_000,
    )

    assert result.total == 1
    assert result.limit == 25
    assert result.offset == 0
    assert result.query_schema_version == "pharma.pipeline.search.v13"
    assert result.sort_by == "status_date"
    assert result.sort_direction == "desc"
    assert [item.model_dump() for item in result.applied_filters] == [
        {"field": "q", "operator": "contains", "value": "egfr"},
        {"field": "modality", "operator": "in", "value": ["small molecule", "antibody"]},
        {"field": "phase", "operator": "eq", "value": "phase_2"},
        {"field": "geography", "operator": "eq", "value": "Global"},
        {"field": "status_date_from", "operator": "gte", "value": "2026-06-30T00:00:00+00:00"},
        {"field": "status_date_to", "operator": "lte", "value": "2026-07-02T00:00:00+00:00"},
        {"field": "drug_entity_id", "operator": "eq", "value": drug.id},
        {"field": "target_entity_id", "operator": "eq", "value": target.id},
        {"field": "disease_entity_id", "operator": "eq", "value": disease.id},
        {"field": "organization_entity_id", "operator": "eq", "value": organization.id},
        {"field": "global_phase", "operator": "eq", "value": "phase_2"},
        {"field": "china_phase", "operator": "eq", "value": "phase_1"},
        {
            "field": "global_phase_started_from",
            "operator": "gte",
            "value": "2026-05-01T00:00:00+00:00",
        },
        {
            "field": "global_phase_started_to",
            "operator": "lte",
            "value": "2026-07-01T00:00:00+00:00",
        },
        {
            "field": "china_phase_started_from",
            "operator": "gte",
            "value": "2025-01-01T00:00:00+00:00",
        },
        {
            "field": "china_phase_started_to",
            "operator": "lte",
            "value": "2025-04-01T00:00:00+00:00",
        },
        {"field": "development_rights_region", "operator": "eq", "value": "Global"},
        {"field": "commercialization_rights_region", "operator": "eq", "value": "Greater China"},
        {"field": "program_tag", "operator": "in", "value": ["first_in_class", "new_modality"]},
        {"field": "milestone_type", "operator": "eq", "value": "first_patient_in"},
        {"field": "milestone_from", "operator": "gte", "value": "2026-06-01T00:00:00+00:00"},
        {"field": "milestone_to", "operator": "lte", "value": "2026-06-30T00:00:00+00:00"},
        {"field": "has_clinical_results", "operator": "eq", "value": True},
        {"field": "clinical_result_evaluation", "operator": "eq", "value": "positive"},
        {"field": "has_deal", "operator": "eq", "value": True},
        {"field": "deal_currency", "operator": "eq", "value": "USD"},
        {"field": "deal_total_potential_amount_min", "operator": "gte", "value": 400_000_000},
        {"field": "deal_total_potential_amount_max", "operator": "lte", "value": 600_000_000},
    ]
    assert result.facets == {
        "modality": {"small molecule": 1},
        "innovation_type": {},
        "therapeutic_area": {},
        "drug_category": {},
        "program_status": {"unknown": 1},
        "phase": {"phase_2": 1},
        "geography": {"Global": 1},
        "global_phase": {"phase_2": 1},
        "china_phase": {"phase_1": 1},
        "development_rights_region": {"Global": 1},
        "commercialization_rights_region": {"Greater China": 1},
        "program_tag": {"first_in_class": 1},
        "milestone_type": {"first_patient_in": 1},
        "organization_role": {"originator": 1},
        "organization_type": {},
        "organization_country_region": {},
        "has_clinical_results": {"true": 1},
        "has_deal": {"true": 1},
        "clinical_result_evaluation": {"positive": 1},
        "deal_currency": {"USD": 1},
    }
    assert result.landscape.model_dump() == {
        "total_programs": 1,
        "distinct_drugs": 1,
        "distinct_targets": 1,
        "distinct_diseases": 1,
        "distinct_organizations": 1,
        "limit": 20,
        "stage_scope": "overall",
        "target_aggregation": "all",
        "overall_phase": [
            {"key": "phase_2", "label": "phase_2", "count": 1, "share": 1.0, "entity_id": None, "phase_counts": {}}
        ],
        "global_phase": [
            {"key": "phase_2", "label": "phase_2", "count": 1, "share": 1.0, "entity_id": None, "phase_counts": {}}
        ],
        "china_phase": [
            {"key": "phase_1", "label": "phase_1", "count": 1, "share": 1.0, "entity_id": None, "phase_counts": {}}
        ],
        "targets": [
            {
                "key": target.id,
                "label": "EGFR",
                "count": 1,
                "share": 1.0,
                "entity_id": target.id,
                "phase_counts": {"phase_2": 1},
            }
        ],
        "diseases": [
            {
                "key": disease.id,
                "label": "Non-small cell lung cancer",
                "count": 1,
                "share": 1.0,
                "entity_id": disease.id,
                "phase_counts": {"phase_2": 1},
            }
        ],
        "target_combinations": [
            {
                "key": target.id,
                "label": "EGFR",
                "count": 1,
                "share": 1.0,
                "entity_id": target.id,
                "phase_counts": {"phase_2": 1},
            }
        ],
        "modality": [
            {
                "key": "small molecule",
                "label": "small molecule",
                "count": 1,
                "share": 1.0,
                "entity_id": None,
                "phase_counts": {"phase_2": 1},
            }
        ],
        "geography": [
            {
                "key": "Global",
                "label": "Global",
                "count": 1,
                "share": 1.0,
                "entity_id": None,
                "phase_counts": {"phase_2": 1},
            }
        ],
        "organizations": [
            {
                "key": organization.id,
                "label": "Victor Therapeutics",
                "count": 1,
                "share": 1.0,
                "entity_id": organization.id,
                "phase_counts": {"phase_2": 1},
            }
        ],
    }
    assert result.items[0].global_phase_started_at is not None
    assert result.items[0].global_phase_started_at.replace(tzinfo=UTC) == datetime(2026, 6, 1, tzinfo=UTC)
    assert result.items[0].china_phase_started_at is not None
    assert result.items[0].china_phase_started_at.replace(tzinfo=UTC) == datetime(2025, 3, 1, tzinfo=UTC)
    assert result.items[0].model_dump(exclude={"status_date", "global_phase_started_at", "china_phase_started_at"}) == {
        "id": result.items[0].id,
        "drug_entity_id": drug.id,
        "drug_name": "VX-101",
        "target_entity_id": target.id,
        "target_name": "EGFR",
        "targets": [{"entity_id": target.id, "name": "EGFR", "role": "primary", "position": 0}],
        "target_combination_key": target.id,
        "disease_entity_id": disease.id,
        "disease_name": "Non-small cell lung cancer",
        "organization_entity_id": organization.id,
        "organization_name": "Victor Therapeutics",
        "organizations": [
            {
                "entity_id": organization.id,
                "name": "Victor Therapeutics",
                "role": "originator",
                "country_region": None,
                "organization_type": None,
                "position": 0,
            }
        ],
        "modality": "small molecule",
        "innovation_type": None,
        "therapeutic_area": None,
        "drug_category": None,
        "program_status": None,
        "mechanism_of_action": "covalent inhibitor",
        "phase": "phase_2",
        "status_detail": None,
        "geography": "Global",
        "global_phase": "phase_2",
        "china_phase": "phase_1",
        "development_rights_regions": ["Global"],
        "commercialization_rights_regions": ["Greater China"],
        "program_tags": ["first_in_class"],
        "status_history": [],
        "milestones": [
            {
                "milestone_type": "first_patient_in",
                "title": "Global Phase II first patient in",
                "occurred_at": datetime(2026, 6, 15, tzinfo=UTC),
                "geography": "Global",
                "description": None,
                "source_document_id": None,
            }
        ],
        "clinical_trial_count": 1,
        "has_clinical_results": True,
        "clinical_result_evaluations": ["positive"],
        "deal_count": 1,
        "deal_currencies": ["USD"],
        "source_document_id": None,
        "project_count": 1,
        "indications": [],
        "modalities": [],
        "mechanisms_of_action": [],
        "innovation_types": [],
        "therapeutic_areas": [],
        "drug_categories": [],
        "program_status_counts": {},
    }
    assert result.warnings == ["暂无记录不代表全球不存在；结果受来源授权、更新时间和可见范围影响。"]

    signal_query = PipelineSavedSearchQuery(
        target_entity_id=target.id,
        has_clinical_results=True,
        clinical_result_evaluation=TrialResultEvaluation.POSITIVE,
        has_deal=True,
        deal_currency="USD",
        deal_total_potential_amount_min=400_000_000,
        deal_total_potential_amount_max=600_000_000,
    )
    service = IntelligenceService(session, tenant.id)
    assert service.program_saved_search_matches_entity(trial_entity.id, signal_query) is True
    assert service.program_saved_search_matches_entity(deal_entity.id, signal_query) is True

    drug_dossier = IntelligenceService(session, tenant.id).drug_dossier(drug.id)
    assert drug_dossier is not None
    assert drug_dossier.summary.model_dump() == {
        "program_count": 1,
        "target_count": 1,
        "indication_count": 1,
        "organization_count": 1,
        "modalities": ["small molecule"],
        "highest_phase": "phase_2",
        "highest_global_phase": "phase_2",
        "highest_china_phase": "phase_1",
        "latest_status_date": datetime(2026, 7, 1, tzinfo=UTC),
    }
    assert len(drug_dossier.regulatory_events) == 1
    approval = drug_dossier.regulatory_events[0]
    assert approval.subject_entity.model_dump() == {
        "id": drug.id,
        "name": "VX-101",
        "entity_type": "drug",
    }
    assert approval.indication_entity is not None
    assert approval.indication_entity.model_dump() == {
        "id": disease.id,
        "name": "Non-small cell lung cancer",
        "entity_type": "disease",
    }
    assert approval.organization_entity is not None
    assert approval.organization_entity.name == "Victor Therapeutics"
    assert len(drug_dossier.clinical_trials) == 1
    dossier_trial = drug_dossier.clinical_trials[0]
    assert dossier_trial.registry_id == "NCTPIPELINE001"
    assert dossier_trial.key_result_count == 1
    assert dossier_trial.latest_result_disclosure is not None
    assert dossier_trial.latest_result_disclosure.conference_name == "ASCO 2026"
    assert {(item.name, item.role.value) for item in dossier_trial.entity_roles} == {
        ("VX-101", "investigational_drug"),
        ("Carboplatin", "combination_drug"),
        ("EGFR", "investigational_target"),
    }
    assert dossier_trial.outcomes[0].results[0].value == "68.0"
    assert len(drug_dossier.deals) == 1
    dossier_deal = drug_dossier.deals[0]
    assert dossier_deal.name == "VX-101 Global License"
    assert {(item.name, item.role.value) for item in dossier_deal.party_roles} == {
        ("Victor Therapeutics", "licensor"),
        ("Strategic Bio", "licensee"),
    }
    assert [(item.name, item.development_phase_at_transaction) for item in dossier_deal.asset_stages] == [
        ("VX-101", "phase_2")
    ]
    assert [item.model_dump(exclude={"id"}) for item in dossier_deal.rights] == [
        {
            "holder_entity_id": licensee.id,
            "holder_name": "Strategic Bio",
            "right_type": "commercialization",
            "territory": "Greater China",
            "exclusive": True,
            "scope_description": "Exclusive commercialization rights for VX-101",
            "source_document_id": None,
        }
    ]


def test_pipeline_search_uses_only_current_versioned_target_set(session: Session, tenant: Tenant) -> None:
    drug = _entity(session, tenant, EntityType.DRUG, "VX-DUAL")
    primary = _entity(session, tenant, EntityType.TARGET, "EGFR")
    combination = _entity(session, tenant, EntityType.TARGET, "ERBB2")
    historical = _entity(session, tenant, EntityType.TARGET, "MET")
    target_key = "|".join(sorted((primary.id, combination.id)))
    program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=drug.id,
        target_entity_id=primary.id,
        target_set_version=2,
        target_combination_key=target_key,
        modality="bispecific antibody",
        phase=DevelopmentPhase.PHASE_1,
    )
    session.add(program)
    session.flush()
    session.add_all(
        [
            DevelopmentProgramTarget(
                tenant_id=tenant.id,
                program_id=program.id,
                target_set_version=1,
                target_entity_id=historical.id,
                role=ProgramTargetRole.PRIMARY,
                position=0,
            ),
            DevelopmentProgramTarget(
                tenant_id=tenant.id,
                program_id=program.id,
                target_set_version=2,
                target_entity_id=primary.id,
                role=ProgramTargetRole.PRIMARY,
                position=0,
            ),
            DevelopmentProgramTarget(
                tenant_id=tenant.id,
                program_id=program.id,
                target_set_version=2,
                target_entity_id=combination.id,
                role=ProgramTargetRole.COMBINATION,
                position=1,
            ),
        ]
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    by_secondary = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_entity_id=combination.id,
    )
    assert by_secondary.total == 1
    assert by_secondary.items[0].target_combination_key == target_key
    assert [target.model_dump() for target in by_secondary.items[0].targets] == [
        {"entity_id": primary.id, "name": "EGFR", "role": "primary", "position": 0},
        {"entity_id": combination.id, "name": "ERBB2", "role": "combination", "position": 1},
    ]
    assert by_secondary.landscape.distinct_targets == 2
    assert {bucket.entity_id for bucket in by_secondary.landscape.targets} == {primary.id, combination.id}
    assert by_secondary.landscape.target_combinations[0].key == target_key
    assert by_secondary.landscape.target_combinations[0].count == 1

    primary_only = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        landscape_limit=50,
        landscape_stage_scope="global",
        landscape_target_aggregation="primary",
    )
    assert primary_only.landscape.limit == 50
    assert primary_only.landscape.stage_scope == "global"
    assert primary_only.landscape.target_aggregation == "primary"
    assert primary_only.landscape.distinct_targets == 1
    assert [bucket.entity_id for bucket in primary_only.landscape.targets] == [primary.id]

    assert service.search_programs("erbb2", None, None, None, 25, 0).total == 1
    assert service.search_programs(None, None, None, None, 25, 0, target_combination_key=target_key).total == 1
    assert service.search_programs(None, None, None, None, 25, 0, target_entity_id=historical.id).total == 0
    assert [item.id for item in service.competitive_programs(combination.id, 25)] == [program.id]
    profile = service.target_profile(combination.id)
    assert profile is not None
    assert profile.program_count == 1


def test_pipeline_target_combinations_use_canonical_identity_for_buckets_items_and_filters(
    session: Session,
    tenant: Tenant,
) -> None:
    canonical = _entity(session, tenant, EntityType.TARGET, "Epidermal growth factor receptor")
    canonical.review_status = ReviewStatus.VERIFIED
    first_alias = _entity(session, tenant, EntityType.TARGET, "Epidermal growth factor receptor")
    second_alias = _entity(session, tenant, EntityType.TARGET, "Epidermal growth factor receptor")
    combination_target = _entity(session, tenant, EntityType.TARGET, "ERBB2")
    combination_target.review_status = ReviewStatus.VERIFIED
    programs: list[DevelopmentProgram] = []
    for index, targets in enumerate(
        (
            (first_alias,),
            (second_alias,),
            (first_alias, combination_target),
        )
    ):
        drug = _entity(session, tenant, EntityType.DRUG, f"Canonical combination drug {index}")
        drug.review_status = ReviewStatus.VERIFIED
        program = DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=drug.id,
            target_entity_id=targets[0].id,
            target_set_version=1,
            target_combination_key="|".join(sorted(target.id for target in targets)),
            phase=DevelopmentPhase.PHASE_1 if index != 1 else DevelopmentPhase.PHASE_2,
        )
        session.add(program)
        session.flush()
        session.add_all(
            [
                DevelopmentProgramTarget(
                    tenant_id=tenant.id,
                    program_id=program.id,
                    target_set_version=1,
                    target_entity_id=target.id,
                    role=ProgramTargetRole.PRIMARY if position == 0 else ProgramTargetRole.COMBINATION,
                    position=position,
                )
                for position, target in enumerate(targets)
            ]
        )
        programs.append(program)
    session.commit()

    service = IntelligenceService(session, tenant.id, include_unpublished=False)
    result = service.search_programs(None, None, None, None, 25, 0)
    combination_key = "|".join(sorted((canonical.id, combination_target.id)))

    assert [(bucket.key, bucket.label, bucket.count) for bucket in result.landscape.target_combinations] == [
        (canonical.id, "Epidermal growth factor receptor", 2),
        (combination_key, "Epidermal growth factor receptor + ERBB2", 1),
    ]
    assert result.landscape.target_combinations[0].phase_counts == {"phase_1": 1, "phase_2": 1}
    assert result.landscape.target_combinations[1].phase_counts == {"phase_1": 1}
    assert {item.id: item.target_combination_key for item in result.items} == {
        programs[0].id: canonical.id,
        programs[1].id: canonical.id,
        programs[2].id: combination_key,
    }
    assert all(
        item.targets[0].entity_id == canonical.id and item.targets[0].name == canonical.name for item in result.items
    )

    single_target = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_combination_key=canonical.id,
    )
    assert single_target.total == 2
    assert {item.id for item in single_target.items} == {programs[0].id, programs[1].id}

    combination = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_combination_key=combination_key,
    )
    assert combination.total == 1
    assert combination.items[0].id == programs[2].id


def test_target_pipeline_aggregates_unresolved_same_name_aliases_from_verified_identity(
    session: Session,
    tenant: Tenant,
) -> None:
    canonical = _entity(session, tenant, EntityType.TARGET, "EGFR")
    canonical.review_status = ReviewStatus.VERIFIED
    unresolved_alias = _entity(session, tenant, EntityType.TARGET, "EGFR")
    drug = _entity(session, tenant, EntityType.DRUG, "Alias-linked EGFR drug")
    drug.review_status = ReviewStatus.VERIFIED
    program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=drug.id,
        phase=DevelopmentPhase.PRECLINICAL,
        program_status="active",
    )
    session.add(program)
    session.flush()
    session.add(
        DevelopmentProgramTarget(
            tenant_id=tenant.id,
            program_id=program.id,
            target_set_version=program.target_set_version,
            target_entity_id=unresolved_alias.id,
            role=ProgramTargetRole.PRIMARY,
            position=0,
        )
    )
    session.commit()

    service = IntelligenceService(session, tenant.id, include_unpublished=False)

    programs = service.competitive_programs(canonical.id, 25)
    assert [item.id for item in programs] == [program.id]
    assert programs[0].targets[0].entity_id == canonical.id
    profile = service.target_profile(canonical.id)
    assert profile is not None
    assert profile.program_count == 1
    dossier = service.target_dossier(canonical.id)
    assert dossier is not None
    assert dossier.summary.program_count == 1
    assert [item.id for item in dossier.programs] == [program.id]


def test_public_target_pipeline_search_covers_direct_programs_across_identity_family(
    session: Session,
    tenant: Tenant,
) -> None:
    canonical = _entity(session, tenant, EntityType.TARGET, "EGFR")
    canonical.review_status = ReviewStatus.VERIFIED
    unresolved_alias = _entity(session, tenant, EntityType.TARGET, "EGFR")
    canonical_drug = _entity(session, tenant, EntityType.DRUG, "Canonical EGFR drug")
    canonical_drug.review_status = ReviewStatus.VERIFIED
    alias_drug = _entity(session, tenant, EntityType.DRUG, "Alias-linked EGFR drug")
    alias_drug.review_status = ReviewStatus.VERIFIED
    session.add_all(
        [
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=canonical_drug.id,
                target_entity_id=canonical.id,
                phase=DevelopmentPhase.PHASE_2,
                program_status="active",
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=alias_drug.id,
                target_entity_id=unresolved_alias.id,
                phase=DevelopmentPhase.PHASE_1,
                program_status="active",
            ),
        ]
    )
    session.commit()

    service = IntelligenceService(session, tenant.id, include_unpublished=False)

    profile = service.target_profile(canonical.id)
    assert profile is not None
    assert profile.program_count == 2
    program_result = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_entity_id=canonical.id,
        result_grain="program",
    )
    drug_result = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_entity_id=canonical.id,
        result_grain="drug",
    )

    assert program_result.project_total == profile.program_count
    assert program_result.total == 2
    assert {item.drug_name for item in program_result.items} == {
        "Canonical EGFR drug",
        "Alias-linked EGFR drug",
    }
    assert drug_result.project_total == profile.program_count
    assert drug_result.total == 2


def test_pipeline_landscape_merges_linked_same_name_aliases_under_verified_identity(
    session: Session,
    tenant: Tenant,
) -> None:
    canonical = _entity(session, tenant, EntityType.TARGET, "EGFR")
    canonical.review_status = ReviewStatus.VERIFIED
    first_alias = _entity(session, tenant, EntityType.TARGET, "EGFR")
    second_alias = _entity(session, tenant, EntityType.TARGET, "EGFR")
    first_drug = _entity(session, tenant, EntityType.DRUG, "First EGFR drug")
    second_drug = _entity(session, tenant, EntityType.DRUG, "Second EGFR drug")
    first_program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=first_drug.id,
        target_entity_id=first_alias.id,
        target_set_version=1,
        phase=DevelopmentPhase.PRECLINICAL,
    )
    second_program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=second_drug.id,
        target_entity_id=second_alias.id,
        target_set_version=1,
        phase=DevelopmentPhase.PHASE_1,
    )
    session.add_all([first_program, second_program])
    session.flush()
    session.add_all(
        [
            DevelopmentProgramTarget(
                tenant_id=tenant.id,
                program_id=first_program.id,
                target_set_version=1,
                target_entity_id=first_alias.id,
                role=ProgramTargetRole.PRIMARY,
                position=0,
            ),
            DevelopmentProgramTarget(
                tenant_id=tenant.id,
                program_id=second_program.id,
                target_set_version=1,
                target_entity_id=second_alias.id,
                role=ProgramTargetRole.PRIMARY,
                position=0,
            ),
        ]
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_programs(None, None, None, None, 25, 0)

    assert result.landscape.distinct_targets == 1
    assert [bucket.model_dump() for bucket in result.landscape.targets] == [
        {
            "key": canonical.id,
            "label": "EGFR",
            "count": 2,
            "share": 1.0,
            "entity_id": canonical.id,
            "phase_counts": {"phase_1": 1, "preclinical": 1},
        }
    ]


def test_pipeline_landscape_merges_same_name_disease_aliases_under_verified_identity(
    session: Session,
    tenant: Tenant,
) -> None:
    canonical = _entity(session, tenant, EntityType.DISEASE, "实体瘤")
    first_alias = _entity(session, tenant, EntityType.DISEASE, "实体瘤")
    second_alias = _entity(session, tenant, EntityType.DISEASE, "实体瘤")
    first_drug = _entity(session, tenant, EntityType.DRUG, "First indication drug")
    second_drug = _entity(session, tenant, EntityType.DRUG, "Second indication drug")
    for entity in (canonical, first_alias, second_alias, first_drug, second_drug):
        entity.review_status = ReviewStatus.VERIFIED
    session.add_all(
        [
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=first_drug.id,
                disease_entity_id=first_alias.id,
                phase=DevelopmentPhase.PRECLINICAL,
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=second_drug.id,
                disease_entity_id=second_alias.id,
                phase=DevelopmentPhase.PHASE_1,
            ),
        ]
    )
    session.commit()

    result = IntelligenceService(session, tenant.id, include_unpublished=False).search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
    )

    representative_id = min(entity.id for entity in (canonical, first_alias, second_alias))
    assert result.landscape.distinct_diseases == 1
    assert [bucket.model_dump() for bucket in result.landscape.diseases] == [
        {
            "key": representative_id,
            "label": "实体瘤",
            "count": 2,
            "share": 1.0,
            "entity_id": representative_id,
            "phase_counts": {"phase_1": 1, "preclinical": 1},
        }
    ]


def test_target_pipeline_deduplicates_identical_rows_from_one_source_document(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    target.review_status = ReviewStatus.VERIFIED
    drug = _entity(session, tenant, EntityType.DRUG, "Duplicate-source drug")
    drug.review_status = ReviewStatus.VERIFIED
    source = SourceDocument(
        tenant_id=tenant.id,
        title="Pipeline workbook",
        source_type="xlsx",
        source_uri="file:///sources/pipeline.xlsx",
        content_sha256="a" * 64,
    )
    session.add(source)
    session.flush()
    program_values = {
        "tenant_id": tenant.id,
        "drug_entity_id": drug.id,
        "target_entity_id": target.id,
        "phase": DevelopmentPhase.PHASE_1,
        "program_status": "active",
        "modality": "small molecule",
        "mechanism_of_action": "EGFR inhibitor",
        "source_document_id": source.id,
    }
    session.add_all([DevelopmentProgram(**program_values), DevelopmentProgram(**program_values)])
    session.commit()

    service = IntelligenceService(session, tenant.id, include_unpublished=False)

    assert len(service.competitive_programs(target.id, 25)) == 1
    search_result = service.search_programs(None, None, None, None, 25, 0, target_entity_id=target.id)
    assert search_result.total == 1
    assert len(search_result.items) == 1
    profile = service.target_profile(target.id)
    assert profile is not None
    assert profile.program_count == 1
    dossier = service.target_dossier(target.id)
    assert dossier is not None
    assert dossier.summary.program_count == 1
    assert len(dossier.programs) == 1


def test_pipeline_search_excludes_placeholder_targets_from_public_programs_and_landscape(
    session: Session,
    tenant: Tenant,
) -> None:
    drug = _entity(session, tenant, EntityType.DRUG, "Placeholder-cleaned drug")
    placeholder = _entity(session, tenant, EntityType.TARGET, "not available")
    target = _entity(session, tenant, EntityType.TARGET, "IFNA2")
    program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=drug.id,
        target_entity_id=placeholder.id,
        target_set_version=1,
        target_combination_key="|".join(sorted((placeholder.id, target.id))),
        phase=DevelopmentPhase.PHASE_2,
    )
    session.add(program)
    session.flush()
    session.add_all(
        [
            DevelopmentProgramTarget(
                tenant_id=tenant.id,
                program_id=program.id,
                target_set_version=1,
                target_entity_id=placeholder.id,
                role=ProgramTargetRole.PRIMARY,
                position=0,
            ),
            DevelopmentProgramTarget(
                tenant_id=tenant.id,
                program_id=program.id,
                target_set_version=1,
                target_entity_id=target.id,
                role=ProgramTargetRole.COMBINATION,
                position=1,
            ),
        ]
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_entity_id=target.id,
    )

    assert result.total == 1
    assert [item.model_dump() for item in result.items[0].targets] == [
        {"entity_id": target.id, "name": "IFNA2", "role": "primary", "position": 0}
    ]
    assert result.items[0].target_entity_id == target.id
    assert result.items[0].target_name == "IFNA2"
    assert result.items[0].target_combination_key == target.id
    assert result.landscape.distinct_targets == 1
    assert [bucket.label for bucket in result.landscape.targets] == ["IFNA2"]
    assert [bucket.label for bucket in result.landscape.target_combinations] == ["IFNA2"]


def test_public_target_programs_exclude_unpublished_linked_entities(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "Published target")
    published_drug = _entity(session, tenant, EntityType.DRUG, "Published drug")
    draft_drug = _entity(session, tenant, EntityType.DRUG, "Draft drug")
    target.review_status = ReviewStatus.VERIFIED
    published_drug.review_status = ReviewStatus.VERIFIED
    published_program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=published_drug.id,
        target_entity_id=target.id,
        phase=DevelopmentPhase.PHASE_2,
    )
    draft_program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=draft_drug.id,
        target_entity_id=target.id,
        phase=DevelopmentPhase.PRECLINICAL,
    )
    session.add_all([published_program, draft_program])
    session.commit()

    public_service = IntelligenceService(session, tenant.id, include_unpublished=False)
    public_profile = public_service.target_profile(target.id)

    assert public_profile is not None
    assert public_profile.program_count == 1
    assert [item.id for item in public_service.competitive_programs(target.id, 25)] == [published_program.id]

    internal_service = IntelligenceService(session, tenant.id, include_unpublished=True)
    internal_profile = internal_service.target_profile(target.id)

    assert internal_profile is not None
    assert internal_profile.program_count == 2
    assert {item.id for item in internal_service.competitive_programs(target.id, 25)} == {
        published_program.id,
        draft_program.id,
    }


def test_pipeline_search_escapes_wildcards_and_paginates_deterministically(session: Session, tenant: Tenant) -> None:
    for index in range(2):
        drug = _entity(session, tenant, EntityType.DRUG, f"Drug-{index}")
        session.add(
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug.id,
                phase=DevelopmentPhase.PHASE_1 if index == 0 else DevelopmentPhase.PHASE_2,
                mechanism_of_action="zeta mechanism" if index == 0 else "alpha mechanism",
                status_detail="paused" if index == 0 else "active",
                geography="US" if index == 0 else "China",
                global_phase=DevelopmentPhase.PHASE_1 if index == 0 else DevelopmentPhase.PHASE_2,
                china_phase=DevelopmentPhase.PHASE_1 if index == 0 else DevelopmentPhase.PHASE_2,
                global_phase_started_at=datetime(2026, 6, index + 1, tzinfo=UTC),
                china_phase_started_at=datetime(2025, 3, index + 1, tzinfo=UTC),
                status_date=datetime(2026, 7, index + 1, tzinfo=UTC),
            )
        )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    assert service.search_programs("%", None, None, None, 10, 0).total == 0
    first = service.search_programs(None, None, None, None, 1, 0)
    second = service.search_programs(None, None, None, None, 1, 1)
    assert first.total == second.total == 2
    assert first.items[0].drug_name == "Drug-1"
    assert second.items[0].drug_name == "Drug-0"
    assert first.landscape.total_programs == second.landscape.total_programs == 2
    assert first.landscape.organizations[0].key == "__missing__"
    assert first.landscape.organizations[0].count == 2
    assert first.landscape.targets[0].key == "__missing__"
    assert first.landscape.targets[0].count == 2
    assert first.landscape.diseases[0].key == "__missing__"
    assert first.landscape.diseases[0].count == 2

    name_ascending_first = service.search_programs(
        None,
        None,
        None,
        None,
        1,
        0,
        sort_by="drug_name",
        sort_direction="asc",
    )
    name_ascending_second = service.search_programs(
        None,
        None,
        None,
        None,
        1,
        1,
        sort_by="drug_name",
        sort_direction="asc",
    )
    assert name_ascending_first.sort_by == "drug_name"
    assert name_ascending_first.sort_direction == "asc"
    assert name_ascending_first.items[0].drug_name == "Drug-0"
    assert name_ascending_second.items[0].drug_name == "Drug-1"

    multi_sorted = service.search_programs(
        None,
        None,
        None,
        None,
        2,
        0,
        sort=(SortClause(field="modality", direction="asc"), SortClause(field="drug_name", direction="desc")),
    )
    assert [item.drug_name for item in multi_sorted.items] == ["Drug-1", "Drug-0"]
    assert [criterion.model_dump() for criterion in multi_sorted.sort] == [
        {"field": "modality", "direction": "asc"},
        {"field": "drug_name", "direction": "desc"},
    ]

    phase_descending = service.search_programs(
        None,
        None,
        None,
        None,
        2,
        0,
        sort_by="global_phase",
        sort_direction="desc",
    )
    assert [item.drug_name for item in phase_descending.items] == ["Drug-1", "Drug-0"]

    for sort_by in (
        "mechanism_of_action",
        "phase",
        "status_detail",
        "geography",
        "global_phase_started_at",
        "china_phase_started_at",
    ):
        sorted_result = service.search_programs(
            None,
            None,
            None,
            None,
            2,
            0,
            sort_by=sort_by,
            sort_direction="asc",
        )
        assert sorted_result.sort_by == sort_by
        assert len(sorted_result.items) == 2


def test_pipeline_drug_grain_groups_all_matching_indications_before_pagination(
    session: Session, tenant: Tenant
) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "IFNA2")
    drug_a = _entity(session, tenant, EntityType.DRUG, "Drug-A")
    drug_b = _entity(session, tenant, EntityType.DRUG, "Drug-B")
    disease_a = _entity(session, tenant, EntityType.DISEASE, "Disease-A")
    disease_b = _entity(session, tenant, EntityType.DISEASE, "Disease-B")
    organization = _entity(session, tenant, EntityType.ORGANIZATION, "Shared Developer")
    session.add_all(
        [
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug_a.id,
                target_entity_id=target.id,
                disease_entity_id=disease_a.id,
                organization_entity_id=organization.id,
                phase=DevelopmentPhase.PHASE_1,
                global_phase=DevelopmentPhase.PHASE_1,
                program_status="active",
                modality="protein",
                development_rights_regions=["Global"],
                program_tags=["priority"],
                milestones=[
                    {
                        "milestone_type": "first_patient_in",
                        "title": "First patient in",
                        "occurred_at": "2026-06-01T00:00:00+00:00",
                    }
                ],
                status_date=datetime(2026, 6, 1, tzinfo=UTC),
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug_a.id,
                target_entity_id=target.id,
                disease_entity_id=disease_b.id,
                organization_entity_id=organization.id,
                phase=DevelopmentPhase.PHASE_3,
                global_phase=DevelopmentPhase.PHASE_3,
                program_status="inactive",
                modality="protein",
                development_rights_regions=["Global"],
                program_tags=["priority"],
                milestones=[
                    {
                        "milestone_type": "first_patient_in",
                        "title": "First patient in",
                        "occurred_at": "2026-07-01T00:00:00+00:00",
                    }
                ],
                status_date=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug_b.id,
                target_entity_id=target.id,
                disease_entity_id=disease_a.id,
                organization_entity_id=organization.id,
                phase=DevelopmentPhase.PHASE_2,
                global_phase=DevelopmentPhase.PHASE_2,
                program_status="active",
                modality="antibody",
                development_rights_regions=["Global"],
                program_tags=["priority"],
                milestones=[
                    {
                        "milestone_type": "first_patient_in",
                        "title": "First patient in",
                        "occurred_at": "2026-08-01T00:00:00+00:00",
                    }
                ],
                status_date=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        ]
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_programs(
        None,
        None,
        None,
        None,
        1,
        0,
        target_entity_id=target.id,
        sort_by="phase",
        sort_direction="desc",
        result_grain="drug",
    )

    assert result.result_grain == "drug"
    assert result.project_total == 3
    assert result.total == 2
    assert result.limit == 1
    assert len(result.items) == 1
    assert result.items[0].drug_name == "Drug-A"
    assert result.items[0].project_count == 2
    assert result.items[0].phase == "phase_3"
    assert [item.disease_name for item in result.items[0].indications] == ["Disease-B", "Disease-A"]
    assert result.items[0].program_status_counts == {"active": 1, "inactive": 1}
    assert result.facets["modality"] == {"protein": 1, "antibody": 1}
    assert result.facets["development_rights_region"] == {"Global": 2}
    assert result.facets["program_tag"] == {"priority": 2}
    assert result.facets["milestone_type"] == {"first_patient_in": 2}
    assert result.facets["organization_role"] == {"originator": 2}
    assert result.facets["has_clinical_results"] == {"false": 2}
    assert result.facets["has_deal"] == {"false": 2}

    second_page = IntelligenceService(session, tenant.id).search_programs(
        None,
        None,
        None,
        None,
        1,
        1,
        target_entity_id=target.id,
        sort_by="phase",
        sort_direction="desc",
        result_grain="drug",
    )
    assert second_page.total == 2
    assert second_page.project_total == 3
    assert [item.drug_name for item in second_page.items] == ["Drug-B"]


def test_pipeline_drug_grain_groups_unpublished_same_name_aliases_under_verified_identity(
    session: Session, tenant: Tenant
) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "TNF")
    canonical = _entity(session, tenant, EntityType.DRUG, "TNF blocker")
    canonical.review_status = ReviewStatus.VERIFIED
    first_alias = _entity(session, tenant, EntityType.DRUG, "TNF blocker")
    second_alias = _entity(session, tenant, EntityType.DRUG, "TNF blocker")
    session.add_all(
        [
            EntityIdentifier(
                tenant_id=tenant.id,
                entity_id=canonical.id,
                entity_type=EntityType.DRUG,
                namespace="pharmcube_npuid",
                value="DR000001",
                normalized_value="DR000001",
                trusted_namespace=True,
                review_status=ReviewStatus.VERIFIED,
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=canonical.id,
                target_entity_id=target.id,
                phase=DevelopmentPhase.PHASE_2,
                program_status="active",
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=first_alias.id,
                target_entity_id=target.id,
                phase=DevelopmentPhase.PHASE_1,
                program_status="inactive",
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=second_alias.id,
                target_entity_id=target.id,
                phase=DevelopmentPhase.APPROVED,
                program_status="active",
            ),
        ]
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    result = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_entity_id=target.id,
        result_grain="drug",
    )

    assert result.project_total == 3
    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].drug_entity_id == canonical.id
    assert result.items[0].drug_name == "TNF blocker"
    assert result.items[0].project_count == 3
    assert result.items[0].program_status_counts == {"active": 2, "inactive": 1}

    project_result = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_entity_id=target.id,
        result_grain="program",
    )
    assert project_result.total == 3
    assert project_result.landscape.distinct_drugs == 1
    assert {item.drug_entity_id for item in project_result.items} == {canonical.id}
    assert {item.drug_name for item in project_result.items} == {"TNF blocker"}

    dossier = service.drug_dossier(canonical.id, limit=25)
    assert dossier is not None
    assert dossier.summary.program_count == 3
    assert len(dossier.programs) == 3
    assert next(item for item in dossier.coverage if item.domain == "programs").total == 3

    first_page = service.drug_programs(canonical.id, limit=2, offset=0)
    second_page = service.drug_programs(canonical.id, limit=2, offset=2)
    assert first_page is not None
    assert second_page is not None
    assert first_page.total == second_page.total == 3
    assert first_page.offset == 0
    assert second_page.offset == 2
    assert len(first_page.items) == 2
    assert len(second_page.items) == 1
    assert {item.id for item in first_page.items}.isdisjoint(item.id for item in second_page.items)

    comparison = service.drug_comparison_profiles([canonical.id])
    assert len(comparison.items) == 1
    assert comparison.items[0].summary.program_count == 3
    assert comparison.items[0].program_status_counts == {"active": 2, "inactive": 1}


def test_pipeline_drug_identity_prefers_trusted_verified_representative_over_uuid_order(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    target.review_status = ReviewStatus.VERIFIED
    unqualified_verified = Entity(
        id="00000000-0000-4000-8000-000000000001",
        tenant_id=tenant.id,
        entity_type=EntityType.DRUG,
        name="osimertinib",
        normalized_name="osimertinib",
        review_status=ReviewStatus.VERIFIED,
    )
    trusted_verified = Entity(
        id="ffffffff-ffff-4fff-8fff-fffffffffff1",
        tenant_id=tenant.id,
        entity_type=EntityType.DRUG,
        name="OSIMERTINIB",
        normalized_name="osimertinib",
        external_ids={"chembl": "CHEMBL3353410"},
        review_status=ReviewStatus.VERIFIED,
    )
    imported_alias = Entity(
        id="11111111-1111-4111-8111-111111111111",
        tenant_id=tenant.id,
        entity_type=EntityType.DRUG,
        name="osimertinib",
        normalized_name="osimertinib",
    )
    session.add_all([unqualified_verified, trusted_verified, imported_alias])
    session.flush()
    session.add_all(
        [
            EntityIdentifier(
                tenant_id=tenant.id,
                entity_id=trusted_verified.id,
                entity_type=EntityType.DRUG,
                namespace="chembl",
                value="CHEMBL3353410",
                normalized_value="CHEMBL3353410",
                trusted_namespace=True,
                review_status=ReviewStatus.VERIFIED,
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=trusted_verified.id,
                target_entity_id=target.id,
                phase=DevelopmentPhase.APPROVED,
                program_status="active",
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=imported_alias.id,
                target_entity_id=target.id,
                phase=DevelopmentPhase.PHASE_3,
                program_status="active",
            ),
        ]
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    result = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        target_entity_id=target.id,
        result_grain="drug",
    )

    assert result.total == 1
    assert result.project_total == 2
    assert len(result.items) == 1
    assert result.items[0].drug_entity_id == trusted_verified.id
    assert result.items[0].drug_name == "OSIMERTINIB"
    assert result.items[0].project_count == 2


def test_pipeline_multi_select_modality_and_tags_apply_or_within_and_between_dimensions(
    session: Session, tenant: Tenant
) -> None:
    """Multi-value modality/program_tag are OR within a dimension and AND across dimensions."""

    drug_a = _entity(session, tenant, EntityType.DRUG, "MULTI-A")
    drug_b = _entity(session, tenant, EntityType.DRUG, "MULTI-B")
    drug_c = _entity(session, tenant, EntityType.DRUG, "MULTI-C")
    session.add_all(
        [
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug_a.id,
                modality="small molecule",
                phase=DevelopmentPhase.PHASE_1,
                program_tags=["first_in_class"],
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug_b.id,
                modality="antibody",
                phase=DevelopmentPhase.PHASE_2,
                program_tags=["new_modality"],
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug_c.id,
                modality="cell therapy",
                phase=DevelopmentPhase.PHASE_3,
                program_tags=["fast_follow"],
            ),
        ]
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    two_modalities = service.search_programs(None, ["small molecule", "antibody"], None, None, 25, 0)
    assert two_modalities.total == 2
    assert {item.drug_name for item in two_modalities.items} == {"MULTI-A", "MULTI-B"}

    two_tags = service.search_programs(None, None, None, None, 25, 0, program_tag=["first_in_class", "fast_follow"])
    assert two_tags.total == 2
    assert {item.drug_name for item in two_tags.items} == {"MULTI-A", "MULTI-C"}

    # AND between dimensions: antibody AND first_in_class matches no seeded program even
    # though each condition alone matches one.
    cross = service.search_programs(None, ["antibody"], None, None, 25, 0, program_tag=["first_in_class"])
    assert cross.total == 0


def test_public_pipeline_hides_technical_source_and_phase_metadata_from_program_tags(
    session: Session,
    tenant: Tenant,
) -> None:
    drug = _entity(session, tenant, EntityType.DRUG, "Public tag boundary drug")
    drug.review_status = ReviewStatus.VERIFIED
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=drug.id,
            phase=DevelopmentPhase.PHASE_2,
            global_phase=DevelopmentPhase.PHASE_2,
            modality="INHIBITOR",
            drug_category="Small molecule",
            program_tags=["ChEMBL", "maximum clinical phase 2", "first_in_class"],
        )
    )
    session.commit()

    service = IntelligenceService(session, tenant.id, include_unpublished=False)
    result = service.search_programs(None, None, None, None, 25, 0)

    assert result.items[0].program_tags == ["first_in_class"]
    assert result.items[0].modality == "Small molecule"
    assert result.items[0].drug_category == "chemical_drug"
    assert result.facets["program_tag"] == {"first_in_class": 1}
    assert result.facets["modality"] == {"Small molecule": 1}
    assert result.facets["drug_category"] == {"chemical_drug": 1}
    assert service.programs_for_entity(drug.id, 25)[0].program_tags == ["first_in_class"]
    dossier = service.drug_dossier(drug.id)
    assert dossier is not None
    assert dossier.summary.modalities == ["Small molecule"]
    assert service.drug_comparison_profiles([drug.id]).items[0].summary.modalities == ["Small molecule"]
    assert (
        service.search_programs(
            None,
            None,
            None,
            None,
            25,
            0,
            program_tag=["ChEMBL", "maximum clinical phase 2"],
        ).total
        == 0
    )
    assert (
        service.search_programs(
            None,
            None,
            None,
            None,
            25,
            0,
            program_tag=["first_in_class"],
        ).total
        == 1
    )
    assert service.search_programs(None, ["Small molecule"], None, None, 25, 0).total == 1
    assert service.search_programs(None, ["INHIBITOR"], None, None, 25, 0).total == 0
    assert service.search_programs(None, None, None, None, 25, 0, drug_category=["chemical_drug"]).total == 1


def test_pipeline_saved_query_normalizes_legacy_single_values_and_rejects_empty_lists(
    session: Session, tenant: Tenant
) -> None:
    legacy = PipelineSavedSearchQuery.model_validate({"modality": "antibody", "program_tag": "first_in_class"})
    assert legacy.modality == ["antibody"]
    assert legacy.program_tag == ["first_in_class"]

    import pytest as _pytest

    # An empty multi-select must not satisfy the at-least-one-filter rule: that would be
    # a full-library subscription that applies no condition.
    with _pytest.raises(ValueError):
        PipelineSavedSearchQuery.model_validate({"modality": []})
    with _pytest.raises(ValueError):
        PipelineSavedSearchQuery.model_validate({"program_tag": []})


def test_pipeline_classification_filters_apply_or_within_and_between_dimensions(
    session: Session, tenant: Tenant
) -> None:
    """Classification dimensions are OR within and AND across, and never invent values."""

    drug_a = _entity(session, tenant, EntityType.DRUG, "CLASS-A")
    drug_b = _entity(session, tenant, EntityType.DRUG, "CLASS-B")
    session.add_all(
        [
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug_a.id,
                phase=DevelopmentPhase.PHASE_1,
                innovation_type="novel",
                therapeutic_area="oncology",
                drug_category="small molecule drug",
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug_b.id,
                phase=DevelopmentPhase.PHASE_2,
                innovation_type="biosimilar",
                therapeutic_area="oncology",
            ),
        ]
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    both = service.search_programs(None, None, None, None, 25, 0, innovation_type=["novel", "biosimilar"])
    assert both.total == 2

    cross = service.search_programs(
        None, None, None, None, 25, 0, innovation_type=["biosimilar"], therapeutic_area=["oncology"]
    )
    assert cross.total == 1
    assert cross.items[0].drug_name == "CLASS-B"

    none = service.search_programs(None, None, None, None, 25, 0, drug_category=["biologic"])
    assert none.total == 0
    assert {f.field for f in cross.applied_filters} == {"innovation_type", "therapeutic_area"}
    assert both.facets["innovation_type"] == {"novel": 1, "biosimilar": 1}


def test_pipeline_program_status_facets_expose_missing_status_as_unknown(session: Session, tenant: Tenant) -> None:
    """Missing controlled status is searchable as unknown; free-text detail stays ungoverned.

    The previous product behaviour rendered `status_detail` free text through a label map,
    so any unmapped value silently displayed as its raw token and could not be filtered.
    A missing governed status is now an explicit unknown bucket, without guessing active
    or inactive; the raw status_detail remains separate and unfilterable.
    """

    active = _entity(session, tenant, EntityType.DRUG, "STATUS-ACTIVE")
    halted = _entity(session, tenant, EntityType.DRUG, "STATUS-INACTIVE")
    freeform = _entity(session, tenant, EntityType.DRUG, "STATUS-FREEFORM")
    session.add_all(
        [
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=active.id,
                phase=DevelopmentPhase.PHASE_2,
                status_detail="active",
                program_status="active",
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=halted.id,
                phase=DevelopmentPhase.PHASE_1,
                status_detail="inactive",
                program_status="inactive",
            ),
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=freeform.id,
                phase=DevelopmentPhase.PHASE_3,
                status_detail="paused pending partner decision",
                program_status=None,
            ),
        ]
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    only_active = service.search_programs(None, None, None, None, 25, 0, program_status="active")
    assert only_active.total == 1
    assert only_active.items[0].drug_name == "STATUS-ACTIVE"
    assert {f.field for f in only_active.applied_filters} == {"program_status"}

    unknown = service.search_programs(None, None, None, None, 25, 0, program_status="unknown")
    assert unknown.total == 1
    assert unknown.items[0].drug_name == "STATUS-FREEFORM"

    # The ungoverned free-text program is reachable through the explicit unknown
    # bucket, but its raw detail is never used as a governed status.
    everything = service.search_programs(None, None, None, None, 25, 0)
    assert everything.total == 3
    assert everything.facets["program_status"] == {"active": 1, "inactive": 1, "unknown": 1}
    freeform_item = next(item for item in everything.items if item.drug_name == "STATUS-FREEFORM")
    assert freeform_item.program_status is None
    assert freeform_item.status_detail == "paused pending partner decision"


def test_pipeline_program_status_rejects_values_outside_the_controlled_vocabulary(
    session: Session, tenant: Tenant
) -> None:
    import pytest as _pytest

    from pharma_intel.schemas import PipelineSavedSearchQuery

    assert PipelineSavedSearchQuery.model_validate({"program_status": "active"}).program_status == "active"
    with _pytest.raises(ValueError):
        PipelineSavedSearchQuery.model_validate({"program_status": "paused"})


def test_pipeline_organization_roles_are_versioned_and_superseded_rows_never_widen_results(
    session: Session, tenant: Tenant
) -> None:
    """Role conditions must bind to the program's current organization set only.

    A superseded row is the dangerous case: if the existence subquery forgot to pin
    `organization_set_version`, the old collaborator would keep matching forever and the
    query would silently return programs whose governed relationship no longer holds.
    """

    drug = _entity(session, tenant, EntityType.DRUG, "ORG-PROGRAM")
    originator = _entity(session, tenant, EntityType.ORGANIZATION, "Origin Bio")
    former = _entity(session, tenant, EntityType.ORGANIZATION, "Former Partner")
    current_partner = _entity(session, tenant, EntityType.ORGANIZATION, "Current Partner")
    program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=drug.id,
        phase=DevelopmentPhase.PHASE_2,
        organization_entity_id=originator.id,
        organization_set_version=2,
    )
    session.add(program)
    session.flush()
    session.add_all(
        [
            # Superseded version 1: the former collaborator.
            DevelopmentProgramOrganization(
                tenant_id=tenant.id,
                program_id=program.id,
                organization_set_version=1,
                organization_entity_id=former.id,
                role="collaborator",
                organization_type="biotech",
                country_region="US",
                position=0,
            ),
            # Current version 2: originator plus a different collaborator.
            DevelopmentProgramOrganization(
                tenant_id=tenant.id,
                program_id=program.id,
                organization_set_version=2,
                organization_entity_id=originator.id,
                role="originator",
                organization_type="biopharma",
                country_region="CN",
                position=0,
            ),
            DevelopmentProgramOrganization(
                tenant_id=tenant.id,
                program_id=program.id,
                organization_set_version=2,
                organization_entity_id=current_partner.id,
                role="collaborator",
                organization_type="cro",
                country_region="US",
                position=1,
            ),
        ]
    )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    assert service.search_programs(None, None, None, None, 25, 0, organization_role="originator").total == 1
    assert service.search_programs(None, None, None, None, 25, 0, organization_type="cro").total == 1
    assert service.search_programs(None, None, None, None, 25, 0, organization_country_region="CN").total == 1
    assert service.search_programs(None, None, None, None, 25, 0, organization_entity_id=current_partner.id).total == 1
    assert service.search_programs("current partner", None, None, None, 25, 0).total == 1

    # Entity, role, type and geography describe one relationship. Independent
    # EXISTS clauses would incorrectly combine the originator entity with a
    # different collaborator row from the same program.
    exact_relationship = service.search_programs(
        None,
        None,
        None,
        None,
        25,
        0,
        organization_entity_id=current_partner.id,
        organization_role="collaborator",
        organization_type="cro",
        organization_country_region="US",
    )
    assert exact_relationship.total == 1
    assert {item.drug_entity_id for item in exact_relationship.items} == {drug.id}
    assert {item.field for item in exact_relationship.applied_filters} == {
        "organization_entity_id",
        "organization_role",
        "organization_type",
        "organization_country_region",
    }
    assert (
        service.search_programs(
            None,
            None,
            None,
            None,
            25,
            0,
            organization_entity_id=originator.id,
            organization_role="collaborator",
        ).total
        == 0
    )
    assert (
        service.search_programs(
            None,
            None,
            None,
            None,
            25,
            0,
            organization_entity_id=current_partner.id,
            organization_role="originator",
        ).total
        == 0
    )

    # The superseded collaborator's attributes must not match any longer.
    assert service.search_programs(None, None, None, None, 25, 0, organization_type="biotech").total == 0
    assert service.search_programs(None, None, None, None, 25, 0, organization_entity_id=former.id).total == 0

    # Conditions combine with AND across dimensions.
    assert (
        service.search_programs(
            None, None, None, None, 25, 0, organization_role="originator", organization_country_region="US"
        ).total
        == 0
    )
    applied = service.search_programs(None, None, None, None, 25, 0, organization_role="collaborator")
    assert {f.field for f in applied.applied_filters} == {"organization_role"}
    assert [organization.model_dump() for organization in applied.items[0].organizations] == [
        {
            "entity_id": originator.id,
            "name": "Origin Bio",
            "role": "originator",
            "country_region": "CN",
            "organization_type": "biopharma",
            "position": 0,
        },
        {
            "entity_id": current_partner.id,
            "name": "Current Partner",
            "role": "collaborator",
            "country_region": "US",
            "organization_type": "cro",
            "position": 1,
        },
    ]
    assert applied.facets["organization_role"] == {"collaborator": 1, "originator": 1}
    assert applied.facets["organization_type"] == {"biopharma": 1, "cro": 1}
    assert applied.facets["organization_country_region"] == {"CN": 1, "US": 1}
    assert applied.landscape.distinct_organizations == 2
    assert {bucket.entity_id for bucket in applied.landscape.organizations} == {originator.id, current_partner.id}


def test_pipeline_organization_saved_contract_rejects_roles_outside_the_vocabulary() -> None:
    import pytest as _pytest

    from pharma_intel.schemas import PipelineSavedSearchQuery

    assert PipelineSavedSearchQuery.model_validate({"organization_role": "licensee"}).organization_role == "licensee"
    with _pytest.raises(ValueError):
        PipelineSavedSearchQuery.model_validate({"organization_role": "partner"})
