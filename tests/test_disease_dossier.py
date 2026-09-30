from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityType,
    EpidemiologyObservation,
    PatientPopulation,
    PatientPopulationEntityLink,
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


def _seed_disease_dossier(session: Session, tenant: Tenant) -> tuple[Entity, Entity]:
    disease = _entity(session, tenant, EntityType.DISEASE, "EGFR-positive NSCLC")
    drug = _entity(session, tenant, EntityType.DRUG, "VX-201")
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    organization = _entity(session, tenant, EntityType.ORGANIZATION, "Victor Oncology")
    publisher = _entity(session, tenant, EntityType.ORGANIZATION, "National Cancer Registry")
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=drug.id,
            target_entity_id=target.id,
            disease_entity_id=disease.id,
            organization_entity_id=organization.id,
            modality="small molecule",
            phase=DevelopmentPhase.PHASE_2,
            status_date=datetime(2026, 2, 1, tzinfo=UTC),
        )
    )
    population = PatientPopulation(
        tenant_id=tenant.id,
        population_key="egfr-positive-nsclc-cn",
        name="EGFR-positive NSCLC population in China",
        attributes={"biomarker": "EGFR-positive"},
    )
    session.add(population)
    session.flush()
    session.add(
        PatientPopulationEntityLink(
            tenant_id=tenant.id,
            patient_population_id=population.id,
            entity_id=disease.id,
            relationship="disease",
        )
    )
    session.add(
        EpidemiologyObservation(
            tenant_id=tenant.id,
            observation_identifier="NSCLC-CN-2025",
            disease_entity_id=disease.id,
            patient_population_id=population.id,
            measure="prevalence",
            value=Decimal("158000"),
            unit="patients",
            geography="China",
            population_scope="adults",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 12, 31, tzinfo=UTC),
            publisher_entity_id=publisher.id,
        )
    )
    session.commit()
    return disease, drug


def test_disease_dossier_aggregates_pipeline_and_epidemiology_with_tenant_isolation(
    session: Session,
    tenant: Tenant,
) -> None:
    disease, drug = _seed_disease_dossier(session, tenant)
    other_tenant = Tenant(slug="other-disease-dossier", name="Other Disease Dossier")
    session.add(other_tenant)
    session.flush()
    hidden_disease = _entity(session, other_tenant, EntityType.DISEASE, "Hidden disease")
    session.commit()

    service = IntelligenceService(session, tenant.id)
    dossier = service.disease_dossier(disease.id, 100)

    assert dossier is not None
    assert dossier.entity.id == disease.id
    assert dossier.summary.model_dump() == {
        "program_count": 1,
        "drug_count": 1,
        "target_count": 1,
        "organization_count": 1,
        "clinical_trial_count": 0,
        "patent_count": 0,
        "epidemiology_observation_count": 1,
        "patient_population_count": 1,
        "modalities": ["small molecule"],
        "phase_distribution": {"phase_2": 1},
        "highest_phase": DevelopmentPhase.PHASE_2,
        "measures": ["prevalence"],
        "geographies": ["China"],
        "latest_activity_at": datetime(2026, 2, 1, tzinfo=UTC),
    }
    assert dossier.epidemiology.total == 1
    assert dossier.epidemiology.items[0].disease_entity.id == disease.id
    assert dossier.epidemiology.patient_populations[0].name == "EGFR-positive NSCLC population in China"
    assert service.disease_dossier(drug.id, 100) is None
    assert service.disease_dossier(hidden_disease.id, 100) is None


def test_disease_dossier_api_requires_epidemiology_and_pipeline_scopes(session: Session, tenant: Tenant) -> None:
    disease, drug = _seed_disease_dossier(session, tenant)

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "analyst",
        "user",
        frozenset({"dossiers:read", "pipelines:read"}),
    )
    try:
        with TestClient(app) as client:
            denied = client.get(f"/api/v1/diseases/{disease.id}/dossier")
            assert denied.status_code == 403

            app.dependency_overrides[require_principal] = lambda: Principal(
                tenant.id,
                "analyst",
                "user",
                frozenset({"dossiers:read", "pipelines:read", "epidemiology:read"}),
            )
            response = client.get(f"/api/v1/diseases/{disease.id}/dossier")
            assert response.status_code == 200
            assert response.json()["summary"]["highest_phase"] == "phase_2"
            assert response.json()["epidemiology"]["total"] == 1

            filtered = client.get(f"/api/v1/epidemiology-observations?disease_entity_id={disease.id}")
            assert filtered.status_code == 200
            assert filtered.json()["total"] == 1
            assert filtered.json()["applied_filters"][0] == {
                "field": "disease_entity_id",
                "operator": "eq",
                "value": disease.id,
            }

            not_disease = client.get(f"/api/v1/diseases/{drug.id}/dossier")
            assert not_disease.status_code == 404
    finally:
        app.dependency_overrides.clear()
