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
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
    DevelopmentPhase,
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    Entity,
    EntityType,
    Relationship,
    ReviewStatus,
    Tenant,
    TrialEntityRole,
    TrialResultDisclosureType,
    TrialResultEvaluation,
)
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


def _trial(
    session: Session,
    tenant: Tenant,
    registry_id: str,
    title: str,
    *,
    status: str,
    phase: str,
    update_day: int,
    has_results: bool = False,
    result_evaluation: TrialResultEvaluation | None = None,
    acronym: str | None = None,
    initiation_type: str | None = None,
    therapy_lines: list[str] | None = None,
) -> tuple[ClinicalTrialProfile, Entity]:
    entity = _entity(session, tenant, EntityType.CLINICAL_TRIAL, registry_id)
    trial = ClinicalTrialProfile(
        tenant_id=tenant.id,
        entity_id=entity.id,
        registry_name="ClinicalTrials.gov",
        registry_id=registry_id,
        official_title=title,
        acronym=acronym,
        initiation_type=initiation_type,
        therapy_lines=therapy_lines or [],
        overall_status=status,
        phases=[phase],
        study_type="INTERVENTIONAL",
        enrollment=128,
        start_date=datetime(2026, 1, 1, tzinfo=UTC),
        completion_date=datetime(2027, 6, 1, tzinfo=UTC),
        interventions=[{"name": "VX-101", "type": "DRUG"}],
        conditions=["Non-small cell lung cancer"],
        sponsors=[{"name": "Victor Therapeutics", "class": "INDUSTRY"}],
        outcomes=[
            {
                "outcome_type": "PRIMARY",
                "measure": "Objective response rate",
                "time_frame": "24 weeks",
                "results": [
                    {
                        "group_label": "VX-101",
                        "value": "61.9",
                        "unit": "%",
                        "participants": 126,
                    }
                ]
                if has_results
                else [],
                "statistical_analyses": [],
            }
        ],
        locations=[{"country": "China", "city": "Shanghai"}],
        study_design={
            "allocation": "RANDOMIZED",
            "intervention_model": "PARALLEL",
            "primary_purpose": "TREATMENT",
            "masking": "DOUBLE",
            "who_masked": ["PARTICIPANT", "INVESTIGATOR"],
        },
        eligibility={
            "minimum_age": "18 Years",
            "maximum_age": "75 Years",
            "sex": "ALL",
            "healthy_volunteers": False,
            "criteria": "Confirmed EGFR-mutated NSCLC",
        },
        arms=[
            {
                "label": "VX-101",
                "type": "EXPERIMENTAL",
                "description": "VX-101 once daily",
                "intervention_names": ["VX-101"],
            }
        ],
        status_history=[
            {
                "status": status,
                "effective_at": datetime(2026, 7, update_day, tzinfo=UTC).isoformat(),
                "reason": None,
                "source_document_id": None,
            }
        ],
        has_results=has_results,
        result_evaluation=result_evaluation.value if result_evaluation else None,
        results_first_posted=datetime(2026, 7, update_day, tzinfo=UTC) if has_results else None,
        last_update_posted=datetime(2026, 7, update_day, tzinfo=UTC),
    )
    session.add(trial)
    session.flush()
    return trial, entity


def test_trial_search_filters_facets_and_returns_linked_entities(session: Session, tenant: Tenant) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    drug = _entity(session, tenant, EntityType.DRUG, "VX-101")
    combination_drug = _entity(session, tenant, EntityType.DRUG, "Pembrolizumab")
    combination_target = _entity(session, tenant, EntityType.TARGET, "PD-1")
    trial, trial_entity = _trial(
        session,
        tenant,
        "NCT00000001",
        "A randomized study in advanced lung cancer",
        status="RECRUITING",
        phase="PHASE2",
        update_day=10,
        has_results=True,
        result_evaluation=TrialResultEvaluation.POSITIVE,
        acronym="KEYNOTE-VX101",
        initiation_type="ist",
        therapy_lines=["first_line"],
    )
    for linked in (target, drug, combination_drug, combination_target):
        session.add(
            Relationship(
                tenant_id=tenant.id,
                subject_id=trial_entity.id,
                predicate="trial_links_entity",
                object_id=linked.id,
            )
        )
    session.add_all(
        [
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=trial.id,
                entity_id=drug.id,
                role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
            ),
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
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=trial.id,
                entity_id=combination_target.id,
                role=TrialEntityRole.COMBINATION_TARGET.value,
            ),
            ClinicalTrialResultDisclosure(
                tenant_id=tenant.id,
                trial_id=trial.id,
                disclosure_key="trial-1",
                version=2,
                disclosure_type=TrialResultDisclosureType.JOURNAL_ARTICLE.value,
                external_id="PMID:12345678",
                title="VX-101 Phase 2 results",
                disclosed_at=datetime(2026, 7, 10, tzinfo=UTC),
                conference_name="ASCO 2026",
                is_key_result=True,
                result_evaluation=TrialResultEvaluation.POSITIVE.value,
                source_locator="page 12",
                source_quote="VX-101 demonstrated positive Phase 2 results.",
            ),
        ]
    )
    combination_trial, _ = _trial(
        session,
        tenant,
        "NCT00000002",
        "A completed healthy volunteer study",
        status="COMPLETED",
        phase="PHASE1",
        update_day=5,
    )
    session.add(
        ClinicalTrialEntityRole(
            tenant_id=tenant.id,
            trial_id=combination_trial.id,
            entity_id=drug.id,
            role=TrialEntityRole.COMBINATION_DRUG.value,
        )
    )
    other_tenant = Tenant(slug="other-trial", name="Other Trial Tenant")
    session.add(other_tenant)
    session.flush()
    _trial(
        session,
        other_tenant,
        "NCT99999999",
        "Hidden tenant study",
        status="RECRUITING",
        phase="PHASE2",
        update_day=20,
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_clinical_trials(
        "egfr",
        "ClinicalTrials.gov",
        "RECRUITING",
        "PHASE2",
        "INTERVENTIONAL",
        True,
        100,
        0,
        results_posted_from=datetime(2026, 7, 9, tzinfo=UTC),
        results_posted_to=datetime(2026, 7, 11, tzinfo=UTC),
        result_evaluation=TrialResultEvaluation.POSITIVE.value,
        acronym="KEYNOTE",
        initiation_type="ist",
        therapy_line="first_line",
        investigational_drug="VX-101",
        combination_drug="Pembrolizumab",
        investigational_target="EGFR",
        combination_target="PD-1",
        role_entity_id=drug.id,
        role_entity_role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
        has_key_result=True,
        publication_id="PMID:12345678",
        conference="ASCO",
        disclosed_from=datetime(2026, 7, 9, tzinfo=UTC),
        disclosed_to=datetime(2026, 7, 11, tzinfo=UTC),
    )

    assert result.total == 1
    assert result.limit == 100
    assert result.offset == 0
    assert result.query_schema_version == "pharma.clinical_trial.search.v10"
    assert result.sort_by == "last_update_posted"
    assert result.sort_direction == "desc"
    assert [item.model_dump() for item in result.applied_filters] == [
        {"field": "q", "operator": "contains", "value": "egfr"},
        {"field": "registry", "operator": "eq", "value": "ClinicalTrials.gov"},
        {"field": "status", "operator": "eq", "value": "RECRUITING"},
        {"field": "phase", "operator": "eq", "value": "PHASE2"},
        {"field": "study_type", "operator": "eq", "value": "INTERVENTIONAL"},
        {"field": "acronym", "operator": "contains", "value": "KEYNOTE"},
        {"field": "initiation_type", "operator": "eq", "value": "ist"},
        {"field": "therapy_line", "operator": "eq", "value": "first_line"},
        {"field": "has_results", "operator": "eq", "value": True},
        {"field": "result_evaluation", "operator": "eq", "value": "positive"},
        {"field": "investigational_drug", "operator": "contains", "value": "VX-101"},
        {"field": "combination_drug", "operator": "contains", "value": "Pembrolizumab"},
        {"field": "investigational_target", "operator": "contains", "value": "EGFR"},
        {"field": "combination_target", "operator": "contains", "value": "PD-1"},
        {"field": "role_entity_id", "operator": "eq", "value": drug.id},
        {"field": "role_entity_role", "operator": "eq", "value": "investigational_drug"},
        {"field": "has_key_result", "operator": "eq", "value": True},
        {"field": "publication_id", "operator": "eq", "value": "PMID:12345678"},
        {"field": "conference", "operator": "contains", "value": "ASCO"},
        {"field": "disclosed_from", "operator": "gte", "value": "2026-07-09T00:00:00+00:00"},
        {"field": "disclosed_to", "operator": "lte", "value": "2026-07-11T00:00:00+00:00"},
        {"field": "results_posted_from", "operator": "gte", "value": "2026-07-09T00:00:00+00:00"},
        {"field": "results_posted_to", "operator": "lte", "value": "2026-07-11T00:00:00+00:00"},
    ]
    assert result.facets == {
        "registry": {"ClinicalTrials.gov": 1},
        "overall_status": {"RECRUITING": 1},
        "study_type": {"INTERVENTIONAL": 1},
        "initiation_type": {"ist": 1},
        "has_results": {"true": 1},
        "result_evaluation": {"positive": 1},
        "has_key_result": {"true": 1},
        "phase": {"PHASE2": 1},
        "therapy_line": {"first_line": 1},
    }
    assert result.landscape.model_dump() == {
        "total_trials": 1,
        "publication_year_phase": [{"key": "2026", "total": 1, "values": {"PHASE2": 1}}],
        "phase_evaluation": [{"key": "PHASE2", "total": 1, "values": {"positive": 1}}],
    }
    assert result.items[0].id == trial.id
    assert result.items[0].registry_id == "NCT00000001"
    assert result.items[0].has_results is True
    assert result.items[0].result_evaluation is TrialResultEvaluation.POSITIVE
    assert result.items[0].acronym == "KEYNOTE-VX101"
    assert result.items[0].initiation_type == "ist"
    assert result.items[0].therapy_lines == ["first_line"]
    assert result.items[0].key_result_count == 1
    assert result.items[0].latest_result_disclosure is not None
    assert result.items[0].latest_result_disclosure.external_id == "PMID:12345678"
    assert {(item.role.value, item.name) for item in result.items[0].entity_roles} == {
        ("investigational_drug", "VX-101"),
        ("combination_drug", "Pembrolizumab"),
        ("investigational_target", "EGFR"),
        ("combination_target", "PD-1"),
    }
    detail = IntelligenceService(session, tenant.id).clinical_trial_detail(trial.id)
    assert detail is not None
    assert detail.study_design.allocation == "RANDOMIZED"
    assert detail.eligibility.minimum_age == "18 Years"
    assert detail.arms[0].label == "VX-101"
    assert detail.outcomes[0].results[0].value == "61.9"
    assert detail.result_disclosures[0].source_quote == "VX-101 demonstrated positive Phase 2 results."
    assert {(item.entity_type.value, item.name) for item in result.items[0].linked_entities} == {
        ("drug", "VX-101"),
        ("drug", "Pembrolizumab"),
        ("target", "EGFR"),
        ("target", "PD-1"),
    }
    assert result.warnings == ["未观察到试验不代表全球不存在；结果受数据授权、注册平台时效和治理状态限制。"]
    any_drug_role = IntelligenceService(session, tenant.id).search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        role_entity_id=drug.id,
    )
    assert {item.id for item in any_drug_role.items} == {trial.id, combination_trial.id}
    investigational_only = IntelligenceService(session, tenant.id).search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        role_entity_id=drug.id,
        role_entity_role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
    )
    assert [item.id for item in investigational_only.items] == [trial.id]


def test_trial_search_matches_any_normalized_role_entity_id(session: Session, tenant: Tenant) -> None:
    originator = _entity(session, tenant, EntityType.DRUG, "Originator Drug")
    biosimilar = _entity(session, tenant, EntityType.DRUG, "Biosimilar Drug")
    unrelated = _entity(session, tenant, EntityType.DRUG, "Unrelated Drug")
    expected_registry_ids: set[str] = set()
    for index, drug in enumerate((originator, biosimilar, unrelated), start=1):
        trial, _ = _trial(
            session,
            tenant,
            f"NCT0000010{index}",
            f"Normalized drug trial {index}",
            status="RECRUITING",
            phase="PHASE2",
            update_day=index,
        )
        session.add(
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=trial.id,
                entity_id=drug.id,
                role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
            )
        )
        if drug.id in {originator.id, biosimilar.id}:
            expected_registry_ids.add(trial.registry_id)
    session.commit()

    result = IntelligenceService(session, tenant.id).search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        role_entity_ids=[biosimilar.id, originator.id],
        role_entity_role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
    )

    assert result.query_schema_version == "pharma.clinical_trial.search.v10"
    assert result.total == 2
    assert {item.registry_id for item in result.items} == expected_registry_ids
    assert [item.model_dump() for item in result.applied_filters] == [
        {
            "field": "role_entity_ids",
            "operator": "in",
            "value": [biosimilar.id, originator.id],
        },
        {
            "field": "role_entity_role",
            "operator": "eq",
            "value": TrialEntityRole.INVESTIGATIONAL_DRUG.value,
        },
    ]

    with pytest.raises(ValueError, match="cannot be combined"):
        IntelligenceService(session, tenant.id).search_clinical_trials(
            None,
            None,
            None,
            None,
            None,
            None,
            100,
            0,
            role_entity_id=originator.id,
            role_entity_ids=[biosimilar.id],
        )


def test_trial_linked_drug_program_filters_bind_one_current_program(session: Session, tenant: Tenant) -> None:
    primary_drug = _entity(session, tenant, EntityType.DRUG, "Program-matched antibody")
    decoy_drug = _entity(session, tenant, EntityType.DRUG, "Cross-program decoy")
    current_org = _entity(session, tenant, EntityType.ORGANIZATION, "Current China developer")
    historical_org = _entity(session, tenant, EntityType.ORGANIZATION, "Historical US developer")
    decoy_org = _entity(session, tenant, EntityType.ORGANIZATION, "Current Canada developer")
    trial, _ = _trial(
        session,
        tenant,
        "NCT-PROGRAM-001",
        "Program attribute binding trial",
        status="RECRUITING",
        phase="PHASE3",
        update_day=12,
    )
    session.add_all(
        [
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=trial.id,
                entity_id=primary_drug.id,
                role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
            ),
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=trial.id,
                entity_id=decoy_drug.id,
                role=TrialEntityRole.COMBINATION_DRUG.value,
            ),
        ]
    )
    primary_program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=primary_drug.id,
        organization_entity_id=current_org.id,
        modality="antibody",
        innovation_type="innovative",
        drug_category="biologic",
        phase=DevelopmentPhase.PHASE_3,
        global_phase=DevelopmentPhase.PHASE_3.value,
        organization_set_version=2,
        program_tags=["first_in_class"],
    )
    decoy_program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=decoy_drug.id,
        organization_entity_id=decoy_org.id,
        modality="small_molecule",
        innovation_type="generic",
        drug_category="chemical",
        phase=DevelopmentPhase.PHASE_1,
        global_phase=DevelopmentPhase.PHASE_1.value,
        program_tags=["fast_follow"],
    )
    session.add_all([primary_program, decoy_program])
    session.flush()
    session.add_all(
        [
            DevelopmentProgramOrganization(
                tenant_id=tenant.id,
                program_id=primary_program.id,
                organization_set_version=1,
                organization_entity_id=historical_org.id,
                role="originator",
                country_region="US",
                organization_type="biotech",
                position=0,
            ),
            DevelopmentProgramOrganization(
                tenant_id=tenant.id,
                program_id=primary_program.id,
                organization_set_version=2,
                organization_entity_id=current_org.id,
                role="originator",
                country_region="CN",
                organization_type="biotech",
                position=0,
            ),
            DevelopmentProgramOrganization(
                tenant_id=tenant.id,
                program_id=decoy_program.id,
                organization_set_version=1,
                organization_entity_id=decoy_org.id,
                role="originator",
                country_region="CA",
                organization_type="biotech",
                position=0,
            ),
        ]
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    matched = service.search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        linked_drug_modality=["antibody"],
        linked_drug_innovation_type=["innovative"],
        linked_drug_category=["biologic"],
        linked_drug_program_tag=["first_in_class"],
        linked_drug_global_phase=DevelopmentPhase.PHASE_3.value,
        linked_drug_organization_country_region="CN",
    )
    assert matched.query_schema_version == "pharma.clinical_trial.search.v10"
    assert [item.id for item in matched.items] == [trial.id]
    assert [item.model_dump() for item in matched.applied_filters] == [
        {"field": "linked_drug_modality", "operator": "in", "value": ["antibody"]},
        {"field": "linked_drug_innovation_type", "operator": "in", "value": ["innovative"]},
        {"field": "linked_drug_category", "operator": "in", "value": ["biologic"]},
        {"field": "linked_drug_program_tag", "operator": "in", "value": ["first_in_class"]},
        {"field": "linked_drug_global_phase", "operator": "eq", "value": "phase_3"},
        {"field": "linked_drug_organization_country_region", "operator": "eq", "value": "CN"},
    ]
    assert matched.facets["linked_drug_modality"] == {"antibody": 1, "small_molecule": 1}
    assert matched.facets["linked_drug_innovation_type"] == {"generic": 1, "innovative": 1}
    assert matched.facets["linked_drug_category"] == {"biologic": 1, "chemical": 1}
    assert matched.facets["linked_drug_program_tag"] == {"fast_follow": 1, "first_in_class": 1}
    assert matched.facets["linked_drug_global_phase"] == {"phase_1": 1, "phase_3": 1}
    assert matched.facets["linked_drug_organization_country_region"] == {"CA": 1, "CN": 1}

    cross_program = service.search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        linked_drug_modality=["antibody"],
        linked_drug_organization_country_region="CA",
    )
    assert cross_program.total == 0
    historical_program = service.search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        linked_drug_modality=["antibody"],
        linked_drug_organization_country_region="US",
    )
    assert historical_program.total == 0


def test_trial_search_applies_role_groups_as_and_with_or_inside_each_group(
    session: Session,
    tenant: Tenant,
) -> None:
    drug_a = _entity(session, tenant, EntityType.DRUG, "Role Group Drug A")
    drug_b = _entity(session, tenant, EntityType.DRUG, "Role Group Drug B")
    combination = _entity(session, tenant, EntityType.DRUG, "Role Group Combination")
    target = _entity(session, tenant, EntityType.TARGET, "Role Group Target")
    unrelated = _entity(session, tenant, EntityType.DRUG, "Role Group Unrelated")

    expected_ids: set[str] = set()
    for index, investigational in enumerate((drug_a, drug_b, unrelated), start=1):
        trial, _ = _trial(
            session,
            tenant,
            f"NCT0000020{index}",
            f"Role-group trial {index}",
            status="RECRUITING",
            phase="PHASE2",
            update_day=index,
        )
        roles = [
            (investigational, TrialEntityRole.INVESTIGATIONAL_DRUG.value),
            (combination, TrialEntityRole.COMBINATION_DRUG.value),
            (target, TrialEntityRole.INVESTIGATIONAL_TARGET.value),
        ]
        for entity, role in roles:
            session.add(
                ClinicalTrialEntityRole(
                    tenant_id=tenant.id,
                    trial_id=trial.id,
                    entity_id=entity.id,
                    role=role,
                )
            )
        if investigational.id in {drug_a.id, drug_b.id}:
            expected_ids.add(trial.id)
    incomplete, _ = _trial(
        session,
        tenant,
        "NCT00000204",
        "Missing combination role",
        status="RECRUITING",
        phase="PHASE2",
        update_day=4,
    )
    session.add_all(
        [
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=incomplete.id,
                entity_id=drug_a.id,
                role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
            ),
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=incomplete.id,
                entity_id=target.id,
                role=TrialEntityRole.INVESTIGATIONAL_TARGET.value,
            ),
        ]
    )
    swapped, _ = _trial(
        session,
        tenant,
        "NCT00000205",
        "All requested entities in incorrect roles",
        status="RECRUITING",
        phase="PHASE2",
        update_day=5,
    )
    session.add_all(
        [
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=swapped.id,
                entity_id=drug_a.id,
                role=TrialEntityRole.COMBINATION_DRUG.value,
            ),
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=swapped.id,
                entity_id=combination.id,
                role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
            ),
            ClinicalTrialEntityRole(
                tenant_id=tenant.id,
                trial_id=swapped.id,
                entity_id=target.id,
                role=TrialEntityRole.COMBINATION_TARGET.value,
            ),
        ]
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        investigational_drug_entity_ids=[drug_b.id, drug_a.id],
        combination_drug_entity_ids=[combination.id],
        investigational_target_entity_ids=[target.id],
    )

    assert {item.id for item in result.items} == expected_ids
    assert swapped.id not in {item.id for item in result.items}
    assert [item.model_dump() for item in result.applied_filters] == [
        {
            "field": "investigational_drug_entity_ids",
            "operator": "in",
            "value": [drug_b.id, drug_a.id],
        },
        {
            "field": "combination_drug_entity_ids",
            "operator": "in",
            "value": [combination.id],
        },
        {
            "field": "investigational_target_entity_ids",
            "operator": "in",
            "value": [target.id],
        },
    ]


def test_trial_search_escapes_wildcards_and_paginates_deterministically(session: Session, tenant: Tenant) -> None:
    for index in range(2):
        _trial(
            session,
            tenant,
            f"NCT0000000{index + 1}",
            f"Trial {index}",
            status="RECRUITING",
            phase="PHASE2",
            update_day=index + 1,
        )
    session.commit()
    service = IntelligenceService(session, tenant.id)

    assert service.search_clinical_trials("%", None, None, None, None, None, 100, 0).total == 0
    first = service.search_clinical_trials(None, None, None, None, None, None, 1, 0)
    second = service.search_clinical_trials(None, None, None, None, None, None, 1, 1)
    assert first.total == second.total == 2
    assert first.items[0].registry_id == "NCT00000002"
    assert second.items[0].registry_id == "NCT00000001"
    ascending = service.search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        2,
        0,
        sort_by="registry_id",
        sort_direction="asc",
    )
    assert [item.registry_id for item in ascending.items] == ["NCT00000001", "NCT00000002"]
    assert ascending.sort_by == "registry_id"
    assert ascending.sort_direction == "asc"
    multi_sorted = service.search_clinical_trials(
        None,
        None,
        None,
        None,
        None,
        None,
        2,
        0,
        sort=(
            SortClause(field="overall_status", direction="asc"),
            SortClause(field="registry_id", direction="desc"),
        ),
    )
    assert [item.registry_id for item in multi_sorted.items] == ["NCT00000002", "NCT00000001"]
    assert [criterion.model_dump() for criterion in multi_sorted.sort] == [
        {"field": "overall_status", "direction": "asc"},
        {"field": "registry_id", "direction": "desc"},
    ]
    assert first.facets["phase"] == {"PHASE2": 2}
    assert first.facets["has_results"] == {"false": 2}
    assert first.facets["initiation_type"] == {}
    assert first.facets["therapy_line"] == {}
    assert first.landscape.total_trials == 2
    assert first.landscape.publication_year_phase[0].model_dump() == {
        "key": "__missing__",
        "total": 2,
        "values": {"PHASE2": 2},
    }
    assert first.landscape.phase_evaluation[0].model_dump() == {
        "key": "PHASE2",
        "total": 2,
        "values": {"__missing__": 2},
    }
    assert service.clinical_trial_detail("missing") is None


def test_trial_detail_api_is_tenant_scoped_and_filters_result_availability(session: Session, tenant: Tenant) -> None:
    trial, _ = _trial(
        session,
        tenant,
        "NCT00000421",
        "A result-bearing precision oncology trial",
        status="COMPLETED",
        phase="PHASE2",
        update_day=21,
        has_results=True,
        result_evaluation=TrialResultEvaluation.POSITIVE,
    )
    drug = _entity(session, tenant, EntityType.DRUG, "VX-421")
    session.add(
        ClinicalTrialEntityRole(
            tenant_id=tenant.id,
            trial_id=trial.id,
            entity_id=drug.id,
            role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
        )
    )
    other_tenant = Tenant(slug="other-api-trial", name="Other API Trial")
    session.add(other_tenant)
    session.flush()
    hidden, _ = _trial(
        session,
        other_tenant,
        "NCT99999421",
        "Hidden result-bearing trial",
        status="COMPLETED",
        phase="PHASE2",
        update_day=21,
        has_results=True,
    )
    session.add(
        ClinicalTrialResultDisclosure(
            tenant_id=tenant.id,
            trial_id=trial.id,
            disclosure_key="trial-api-1",
            version=1,
            disclosure_type=TrialResultDisclosureType.JOURNAL_ARTICLE.value,
            external_id="PMID:12345678",
            title="API trial result disclosure",
            disclosed_at=datetime(2026, 7, 21, tzinfo=UTC),
            conference_name="ASCO 2026",
            is_key_result=True,
            result_evaluation=TrialResultEvaluation.POSITIVE.value,
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "trial-api-test", "api_key", frozenset({"trials:read"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            search = client.get(
                "/api/v1/trials",
                params={
                    "has_results": True,
                    "result_evaluation": "positive",
                    "results_posted_from": "2026-07-20T00:00:00Z",
                    "results_posted_to": "2026-07-21T23:59:59.999Z",
                    "has_key_result": "true",
                    "publication_id": "PMID:12345678",
                    "disclosed_from": "2026-07-20T00:00:00Z",
                    "disclosed_to": "2026-07-21T23:59:59.999Z",
                },
            )
            assert search.status_code == 200
            search_body = search.json()
            assert [item["id"] for item in search_body["items"]] == [trial.id]
            assert search_body["query_schema_version"] == "pharma.clinical_trial.search.v10"
            assert search_body["sort_by"] == "last_update_posted"
            assert search_body["sort_direction"] == "desc"
            assert search_body["applied_filters"] == [
                {"field": "has_results", "operator": "eq", "value": True},
                {"field": "result_evaluation", "operator": "eq", "value": "positive"},
                {"field": "has_key_result", "operator": "eq", "value": True},
                {"field": "publication_id", "operator": "eq", "value": "PMID:12345678"},
                {
                    "field": "disclosed_from",
                    "operator": "gte",
                    "value": "2026-07-20T00:00:00+00:00",
                },
                {
                    "field": "disclosed_to",
                    "operator": "lte",
                    "value": "2026-07-21T23:59:59.999000+00:00",
                },
                {
                    "field": "results_posted_from",
                    "operator": "gte",
                    "value": "2026-07-20T00:00:00+00:00",
                },
                {
                    "field": "results_posted_to",
                    "operator": "lte",
                    "value": "2026-07-21T23:59:59.999000+00:00",
                },
            ]
            reversed_range = client.get(
                "/api/v1/trials",
                params={
                    "results_posted_from": "2026-07-22T00:00:00Z",
                    "results_posted_to": "2026-07-21T23:59:59Z",
                },
            )
            assert reversed_range.status_code == 422
            assert reversed_range.json()["detail"] == "results_posted_from must not be after results_posted_to"
            missing_timezone = client.get(
                "/api/v1/trials",
                params={"results_posted_from": "2026-07-20T00:00:00"},
            )
            assert missing_timezone.status_code == 422
            assert missing_timezone.json()["detail"] == "results_posted_from must include a timezone offset"
            any_role_filter = client.get("/api/v1/trials", params={"role_entity_id": drug.id})
            assert any_role_filter.status_code == 200
            assert [item["id"] for item in any_role_filter.json()["items"]] == [trial.id]
            multi_role_filter = client.get(
                "/api/v1/trials",
                params=[
                    ("role_entity_ids", "550e8400-e29b-41d4-a716-446655440099"),
                    ("role_entity_ids", drug.id),
                    ("role_entity_role", TrialEntityRole.INVESTIGATIONAL_DRUG.value),
                ],
            )
            assert multi_role_filter.status_code == 200
            assert [item["id"] for item in multi_role_filter.json()["items"]] == [trial.id]
            grouped_role_filter = client.get(
                "/api/v1/trials",
                params=[
                    ("investigational_drug_entity_ids", "550e8400-e29b-41d4-a716-446655440099"),
                    ("investigational_drug_entity_ids", drug.id),
                ],
            )
            assert grouped_role_filter.status_code == 200
            assert [item["id"] for item in grouped_role_filter.json()["items"]] == [trial.id]
            invalid_grouped_role_filter = client.get(
                "/api/v1/trials",
                params={"investigational_drug_entity_ids": "not-a-uuid"},
            )
            assert invalid_grouped_role_filter.status_code == 422
            assert invalid_grouped_role_filter.json()["detail"] == (
                "investigational_drug_entity_ids contains an invalid entity ID"
            )
            conflicting_role_filters = client.get(
                "/api/v1/trials",
                params=[("role_entity_id", drug.id), ("role_entity_ids", drug.id)],
            )
            assert conflicting_role_filters.status_code == 422
            assert conflicting_role_filters.json()["detail"] == (
                "role_entity_id cannot be combined with role_entity_ids"
            )
            missing_role_entity = client.get(
                "/api/v1/trials",
                params={"role_entity_role": TrialEntityRole.INVESTIGATIONAL_DRUG.value},
            )
            assert missing_role_entity.status_code == 422
            assert missing_role_entity.json()["detail"] == (
                "role_entity_role requires role_entity_id or role_entity_ids"
            )
            assert client.get("/api/v1/trials?sort_by=unsupported").status_code == 422
            assert client.get("/api/v1/trials?sort_direction=sideways").status_code == 422
            detail = client.get(f"/api/v1/trials/{trial.id}")
            assert detail.status_code == 200
            assert detail.json()["study_design"]["allocation"] == "RANDOMIZED"
            assert detail.json()["outcomes"][0]["results"][0]["value"] == "61.9"
            assert detail.json()["result_evaluation"] == "positive"
            assert detail.json()["linked_entities"] == []
            assert client.get(f"/api/v1/trials/{hidden.id}").status_code == 404
            assert client.get("/api/v1/trials/not-a-trial").status_code == 404
    finally:
        app.dependency_overrides.clear()
