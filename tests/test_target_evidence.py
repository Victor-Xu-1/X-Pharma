from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import Entity, EntityType, TargetEvidenceObservation, Tenant


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


def test_target_evidence_reads_real_rows_with_filters_and_tenant_isolation(
    session: Session,
    tenant: Tenant,
) -> None:
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    lung_cancer = _entity(session, tenant, EntityType.DISEASE, "Non-small cell lung cancer")
    glioblastoma = _entity(session, tenant, EntityType.DISEASE, "Glioblastoma")
    session.add_all(
        [
            TargetEvidenceObservation(
                tenant_id=tenant.id,
                source_system="governed_ai",
                source_record_id="egfr-gwas-1",
                target_entity_id=target.id,
                disease_entity_id=lung_cancer.id,
                evidence_type="genetic_association",
                direction="supports",
                study_name="EGFR NSCLC GWAS",
                population="East Asian",
                variant="rs121434568",
                effect_size=1.8,
                effect_unit="odds_ratio",
                p_value=1.2e-8,
                sample_size=12000,
                summary="A governed genetic association supports the EGFR disease hypothesis.",
                observed_at=datetime(2026, 7, 21, tzinfo=UTC),
            ),
            TargetEvidenceObservation(
                tenant_id=tenant.id,
                source_system="governed_ai",
                source_record_id="egfr-expression-1",
                target_entity_id=target.id,
                disease_entity_id=glioblastoma.id,
                evidence_type="expression",
                direction="opposes",
                tissue="brain",
                summary="Expression evidence does not support the hypothesis in this cohort.",
                observed_at=datetime(2026, 7, 20, tzinfo=UTC),
            ),
        ]
    )
    other_tenant = Tenant(slug="other-target-evidence", name="Other Target Evidence Tenant")
    session.add(other_tenant)
    session.flush()
    hidden_target = _entity(session, other_tenant, EntityType.TARGET, "EGFR")
    session.add(
        TargetEvidenceObservation(
            tenant_id=other_tenant.id,
            source_system="governed_ai",
            source_record_id="hidden-egfr-1",
            target_entity_id=hidden_target.id,
            evidence_type="functional",
            direction="supports",
            summary="This row belongs to another tenant.",
        )
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    all_rows = service.target_evidence_for_entity(target.id, 10)
    filtered = service.target_evidence_for_entity(
        target.id,
        10,
        evidence_type="genetic_association",
        direction="supports",
        disease_entity_id=lung_cancer.id,
    )

    assert [row.source_record_id for row in all_rows] == ["egfr-gwas-1", "egfr-expression-1"]
    assert len(filtered) == 1
    assert filtered[0].target_name == "EGFR"
    assert filtered[0].disease_name == "Non-small cell lung cancer"
    assert filtered[0].effect_size == 1.8
    assert service.target_evidence_for_entity(target.id, 10, direction="neutral") == []
