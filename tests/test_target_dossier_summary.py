from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from pharma_intel.intelligence import (
    TARGET_STATUS_VOCABULARY_VERSION,
    IntelligenceService,
    normalize_status_token,
)
from pharma_intel.models import (
    ActivityMeasurement,
    Assay,
    ClinicalTrialProfile,
    CompoundStructure,
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityType,
    MeasurementRelation,
    PatentFamily,
    RegulatoryEvent,
    ReviewStatus,
    TargetProfile,
    Tenant,
)


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


def _seed_target_landscape(session: Session, tenant: Tenant) -> Entity:
    """Seed a target whose landscape defeats both truncation and substring matching.

    Every collection is seeded past the dossier display limit used in the assertions so
    that any count taken from the returned records instead of the database is wrong, and
    the free-text statuses deliberately include tokens that a substring match would
    misclassify ("inactive" contains "active"; "active, not recruiting" contains
    "recruit").
    """

    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    drug = _entity(session, tenant, EntityType.DRUG, "VX-900")

    for index in range(3):
        session.add(
            DevelopmentProgram(
                tenant_id=tenant.id,
                drug_entity_id=drug.id,
                target_entity_id=target.id,
                phase=DevelopmentPhase.PHASE_2 if index < 2 else DevelopmentPhase.PHASE_3,
                status_date=datetime(2026, 3, 1, tzinfo=UTC),
            )
        )

    trial_statuses = [
        "Recruiting",
        "recruiting",
        "Active, not recruiting",
        "Not yet recruiting",
        "Completed",
        "Some Registry Specific Status",
    ]
    for index, status in enumerate(trial_statuses):
        session.add(
            ClinicalTrialProfile(
                tenant_id=tenant.id,
                entity_id=target.id,
                registry_name="ClinicalTrials.gov",
                registry_id=f"NCT9000000{index}",
                official_title=f"Study {index}",
                overall_status=status,
            )
        )

    patent_statuses = ["Active", "granted", "Inactive", "expired", "Some Office Specific Status"]
    for index, status in enumerate(patent_statuses):
        session.add(
            PatentFamily(
                tenant_id=tenant.id,
                entity_id=target.id,
                family_identifier=f"FAM-{index}",
                title=f"Patent family {index}",
                legal_status=status,
            )
        )

    regulatory_types = ["approval", "conditional_approval", "submission", "safety_signal"]
    for index, event_type in enumerate(regulatory_types):
        session.add(
            RegulatoryEvent(
                tenant_id=tenant.id,
                subject_entity_id=target.id,
                agency="FDA",
                jurisdiction="US",
                event_identifier=f"EVT-{index}",
                event_type=event_type,
                title=f"Event {index}",
            )
        )

    session.commit()
    return target


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Active, not recruiting", "active not recruiting"),
        ("ACTIVE_NOT_RECRUITING", "active not recruiting"),
        ("  Recruiting  ", "recruiting"),
        ("in-force", "in force"),
        (None, ""),
        ("", ""),
    ],
)
def test_normalize_status_token_folds_separators_and_case(raw: str | None, expected: str) -> None:
    assert normalize_status_token(raw) == expected


def test_target_dossier_summary_counts_full_result_set_not_returned_records(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _seed_target_landscape(session, tenant)

    # A display limit far below every seeded collection: a summary derived from the
    # returned records would report the limit, not the authoritative total.
    dossier = IntelligenceService(session, tenant.id).target_dossier(target.id, limit=1)

    assert dossier is not None
    assert len(dossier.programs) == 1
    assert len(dossier.clinical_trials) == 1
    assert len(dossier.patents) == 1
    assert len(dossier.regulatory_events) == 1

    summary = dossier.summary
    assert summary.program_count == 3
    assert summary.clinical_trial_count == 6
    assert summary.patent_count == 5
    assert summary.regulatory_event_count == 4
    assert summary.phase_distribution == {"phase_2": 2, "phase_3": 1}
    assert summary.highest_phase == DevelopmentPhase.PHASE_3
    assert summary.status_vocabulary_version == TARGET_STATUS_VOCABULARY_VERSION


def test_target_dossier_returns_structures_from_target_activity_compounds(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    compound = _entity(session, tenant, EntityType.DRUG, "VX-900")
    structure = CompoundStructure(
        tenant_id=tenant.id,
        entity_id=compound.id,
        canonical_smiles="CCO",
        isomeric_smiles="CCO",
        standard_inchi="InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
        standard_inchi_key="LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        molecular_formula="C2H6O",
        molecular_weight=46.069,
        exact_mass=46.0419,
        structure_version="test-v1",
        standardization_version="test-v1",
        fingerprint_version="test-v1",
    )
    assay = Assay(
        tenant_id=tenant.id,
        source_system="test",
        source_assay_id="assay-egfr-1",
        target_entity_id=target.id,
        assay_type="binding",
        assay_format="biochemical",
        organism="Homo sapiens",
    )
    session.add_all([structure, assay])
    session.flush()
    session.add(
        ActivityMeasurement(
            tenant_id=tenant.id,
            source_system="test",
            source_activity_id="activity-egfr-1",
            assay_id=assay.id,
            compound_entity_id=compound.id,
            target_entity_id=target.id,
            reported_type="IC50",
            reported_relation=MeasurementRelation.EQUAL,
            reported_value="10",
            reported_units="nM",
            standard_type="IC50",
            standard_relation=MeasurementRelation.EQUAL,
            standard_value=10,
            standard_units="nM",
            pchembl_value=8.0,
            qualifiers={},
        )
    )
    session.commit()

    dossier = IntelligenceService(session, tenant.id).target_dossier(target.id, limit=10)

    assert dossier is not None
    assert len(dossier.activities) == 1
    assert [item.id for item in dossier.structures] == [structure.id]
    assert dossier.structures[0].standard_inchi_key == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"


def test_target_profile_reuses_exact_external_id_profile_from_duplicate_entity(
    session: Session,
    tenant: Tenant,
) -> None:
    verified_target = _entity(session, tenant, EntityType.TARGET, "Epidermal growth factor receptor")
    verified_target.review_status = ReviewStatus.VERIFIED
    verified_target.external_ids = {"chembl": "CHEMBL203"}
    duplicate_target = _entity(session, tenant, EntityType.TARGET, "Epidermal growth factor receptor")
    duplicate_target.review_status = ReviewStatus.DRAFT
    duplicate_target.external_ids = {"ChEMBL": "chembl203"}
    profile = TargetProfile(
        tenant_id=tenant.id,
        entity_id=duplicate_target.id,
        gene_symbol="EGFR",
        uniprot_accession="P00533",
        organism="Homo sapiens",
        target_class="SINGLE PROTEIN",
    )
    session.add(profile)
    session.commit()

    result = IntelligenceService(session, tenant.id).target_profile(verified_target.id)

    assert result is not None
    assert result.entity.id == verified_target.id
    assert result.profile_id == profile.id
    assert result.gene_symbol == "EGFR"
    assert result.uniprot_accession == "P00533"
    assert result.target_class == "SINGLE PROTEIN"


def test_target_dossier_summary_rejects_substring_status_matches(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _seed_target_landscape(session, tenant)

    summary = IntelligenceService(session, tenant.id).target_dossier(target.id, limit=100).summary  # type: ignore[union-attr]

    # "Recruiting" and "recruiting" only. "Active, not recruiting" and "Not yet
    # recruiting" both contain "recruit" but are not recruiting.
    assert summary.recruiting_trial_count == 2
    # "Active" and "granted" only. A substring match would also count "Inactive".
    assert summary.active_patent_count == 2
    # Governed event vocabulary: approval and conditional_approval.
    assert summary.approval_event_count == 2


def test_target_dossier_summary_reports_ungoverned_statuses_as_unclassified(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _seed_target_landscape(session, tenant)

    summary = IntelligenceService(session, tenant.id).target_dossier(target.id, limit=100).summary  # type: ignore[union-attr]

    # Exactly the one registry-specific and one office-specific status per domain; known
    # negative statuses must not inflate the unclassified gap.
    assert summary.unclassified_trial_status_count == 1
    assert summary.unclassified_patent_status_count == 1


def test_target_dossier_summary_is_tenant_isolated(session: Session, tenant: Tenant) -> None:
    target = _seed_target_landscape(session, tenant)
    other_tenant = Tenant(slug="other-target-summary", name="Other Target Summary")
    session.add(other_tenant)
    session.flush()
    other_target = _entity(session, other_tenant, EntityType.TARGET, "EGFR")
    session.add(
        PatentFamily(
            tenant_id=other_tenant.id,
            entity_id=other_target.id,
            family_identifier="FAM-OTHER",
            title="Other tenant patent",
            legal_status="Active",
        )
    )
    session.commit()

    summary = IntelligenceService(session, tenant.id).target_dossier(target.id, limit=100).summary  # type: ignore[union-attr]

    assert summary.patent_count == 5
    assert summary.active_patent_count == 2
    assert IntelligenceService(session, tenant.id).target_dossier(other_target.id, limit=100) is None
