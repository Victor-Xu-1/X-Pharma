from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    Entity,
    EntityType,
    EpidemiologyObservation,
    PatientPopulation,
    PatientPopulationEntityLink,
    Tenant,
)
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


def _observation(
    session: Session,
    tenant: Tenant,
    disease: Entity,
    *,
    identifier: str,
    measure: str,
    value: str,
    year: int,
    geography: str = "China",
    unit: str = "patients",
    population_scope: str = "adults",
    publisher: Entity | None = None,
    patient_population: PatientPopulation | None = None,
) -> EpidemiologyObservation:
    observation = EpidemiologyObservation(
        tenant_id=tenant.id,
        observation_identifier=identifier,
        disease_entity_id=disease.id,
        patient_population_id=patient_population.id if patient_population else None,
        measure=measure,
        value=Decimal(value),
        lower_bound=Decimal(value) * Decimal("0.9"),
        upper_bound=Decimal(value) * Decimal("1.1"),
        unit=unit,
        geography=geography,
        population_scope=population_scope,
        age_group="18+",
        sex="all",
        period_start=datetime(year, 1, 1, tzinfo=UTC),
        period_end=datetime(year, 12, 31, tzinfo=UTC),
        sample_size=Decimal("12500"),
        methodology="registry-calibrated prevalence model",
        publisher_entity_id=publisher.id if publisher else None,
    )
    session.add(observation)
    session.flush()
    return observation


def test_epidemiology_search_filters_facets_links_and_tenant_isolation(
    session: Session,
    tenant: Tenant,
) -> None:
    disease = _entity(session, tenant, EntityType.DISEASE, "EGFR-positive NSCLC")
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    publisher = _entity(session, tenant, EntityType.ORGANIZATION, "WHO")
    population = PatientPopulation(
        tenant_id=tenant.id,
        population_key="egfr-positive-nsclc-cn",
        name="EGFR-positive NSCLC population in China",
        description="Governed biomarker-defined population",
        attributes={"biomarker": "EGFR-positive"},
    )
    session.add(population)
    session.flush()
    session.add_all(
        [
            PatientPopulationEntityLink(
                tenant_id=tenant.id,
                patient_population_id=population.id,
                entity_id=disease.id,
                relationship="disease",
            ),
            PatientPopulationEntityLink(
                tenant_id=tenant.id,
                patient_population_id=population.id,
                entity_id=target.id,
                relationship="target",
            ),
        ]
    )
    alternate_population = PatientPopulation(
        tenant_id=tenant.id,
        population_key="egfr-wild-type-nsclc-cn",
        name="EGFR wild-type NSCLC population in China",
        attributes={"biomarker": "EGFR wild-type"},
    )
    session.add(alternate_population)
    session.flush()
    session.add(
        PatientPopulationEntityLink(
            tenant_id=tenant.id,
            patient_population_id=alternate_population.id,
            entity_id=disease.id,
            relationship="disease",
        )
    )
    observation = _observation(
        session,
        tenant,
        disease,
        identifier="WHO-NSCLC-CN-2025",
        measure="prevalence",
        value="158000",
        year=2025,
        publisher=publisher,
        patient_population=population,
    )
    _observation(
        session,
        tenant,
        disease,
        identifier="WHO-NSCLC-US-2025",
        measure="incidence",
        value="65000",
        year=2025,
        geography="United States",
        unit="cases/year",
        publisher=publisher,
    )
    _observation(
        session,
        tenant,
        disease,
        identifier="WHO-NSCLC-CN-2024-WT",
        measure="prevalence",
        value="130000",
        year=2024,
        publisher=publisher,
        patient_population=alternate_population,
    )

    other_tenant = Tenant(slug="other-epidemiology", name="Other Epidemiology Tenant")
    session.add(other_tenant)
    session.flush()
    hidden_disease = _entity(session, other_tenant, EntityType.DISEASE, "Hidden disease")
    _observation(
        session,
        other_tenant,
        hidden_disease,
        identifier="HIDDEN-2025",
        measure="prevalence",
        value="999999",
        year=2025,
    )
    session.commit()

    result = IntelligenceService(session, tenant.id).search_epidemiology_observations(
        "WHO",
        "prevalence",
        "China",
        "patients",
        "adults",
        "18+",
        "all",
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 12, 31, tzinfo=UTC),
        100,
        0,
    )

    assert result.total == 1
    assert result.query_schema_version == "pharma.epidemiology.search.v3"
    assert result.sort_by == "period_end"
    assert result.sort_direction == "desc"
    assert [item.model_dump() for item in result.applied_filters] == [
        {"field": "q", "operator": "contains", "value": "WHO"},
        {"field": "measure", "operator": "eq", "value": "prevalence"},
        {"field": "geography", "operator": "eq", "value": "China"},
        {"field": "unit", "operator": "eq", "value": "patients"},
        {"field": "population_scope", "operator": "eq", "value": "adults"},
        {"field": "age_group", "operator": "eq", "value": "18+"},
        {"field": "sex", "operator": "eq", "value": "all"},
        {"field": "period_start_from", "operator": "gte", "value": "2025-01-01T00:00:00+00:00"},
        {"field": "period_end_to", "operator": "lte", "value": "2025-12-31T00:00:00+00:00"},
    ]
    assert result.items[0].id == observation.id
    assert result.items[0].disease_entity.name == "EGFR-positive NSCLC"
    assert result.items[0].publisher_entity is not None
    assert result.items[0].publisher_entity.name == "WHO"
    assert result.items[0].methodology == "registry-calibrated prevalence model"
    assert result.items[0].patient_population is not None
    assert result.items[0].patient_population.id == population.id
    assert [entity.name for entity in result.items[0].patient_population.target_entities] == ["EGFR"]
    assert [option.model_dump() for option in result.patient_populations] == [
        {"id": population.id, "name": population.name, "count": 1}
    ]
    assert result.facets == {
        "measure": {"prevalence": 1},
        "geography": {"China": 1},
        "unit": {"patients": 1},
        "population_scope": {"adults": 1},
        "age_group": {"18+": 1},
        "sex": {"all": 1},
        "disease": {"EGFR-positive NSCLC": 1},
        "publisher": {"WHO": 1},
    }

    population_result = IntelligenceService(session, tenant.id).search_epidemiology_observations(
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
        patient_population_id=population.id,
    )
    assert population_result.total == 1
    assert population_result.items[0].id == observation.id
    assert population_result.applied_filters[0].model_dump() == {
        "field": "patient_population_id",
        "operator": "eq",
        "value": population.id,
    }
    assert {option.id for option in population_result.patient_populations} == {
        population.id,
        alternate_population.id,
    }
    by_population_name = IntelligenceService(session, tenant.id).search_epidemiology_observations(
        "EGFR wild-type NSCLC population",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        100,
        0,
    )
    assert by_population_name.total == 1
    assert by_population_name.items[0].patient_population_id == alternate_population.id


def test_epidemiology_search_escapes_wildcards_paginates_and_builds_trend(
    session: Session,
    tenant: Tenant,
) -> None:
    disease = _entity(session, tenant, EntityType.DISEASE, "NSCLC")
    publisher = _entity(session, tenant, EntityType.ORGANIZATION, "National Registry")
    first_observation = _observation(
        session,
        tenant,
        disease,
        identifier="NSCLC-CN-2024",
        measure="patient_count",
        value="145000",
        year=2024,
        publisher=publisher,
    )
    second_observation = _observation(
        session,
        tenant,
        disease,
        identifier="NSCLC-CN-2025",
        measure="patient_count",
        value="158000",
        year=2025,
        publisher=publisher,
    )
    incompatible_publisher = _entity(session, tenant, EntityType.ORGANIZATION, "Alternative Registry")
    incompatible_observation = _observation(
        session,
        tenant,
        disease,
        identifier="NSCLC-CN-2023-ALTERNATIVE",
        measure="patient_count",
        value="139000",
        year=2023,
        publisher=incompatible_publisher,
    )
    incompatible_observation.methodology = "incompatible claims-derived model"
    session.commit()
    service = IntelligenceService(session, tenant.id)

    assert (
        service.search_epidemiology_observations("%", None, None, None, None, None, None, None, None, 100, 0).total == 0
    )
    by_disease = service.search_epidemiology_observations(
        "NSCLC", None, None, None, None, None, None, None, None, 100, 0
    )
    assert by_disease.total == 3
    first_page = service.search_epidemiology_observations(None, None, None, None, None, None, None, None, None, 1, 0)
    second_page = service.search_epidemiology_observations(None, None, None, None, None, None, None, None, None, 1, 1)
    assert first_page.total == second_page.total == 3
    assert first_page.items[0].id == second_observation.id
    assert second_page.items[0].id == first_observation.id

    trend = service.epidemiology_trend(
        disease.id,
        "patient_count",
        "China",
        "patients",
        "adults",
        "18+",
        "all",
        1,
        patient_population_id=None,
        anchor_observation_id=first_observation.id,
    )
    assert trend is not None
    assert trend.disease.name == "NSCLC"
    assert trend.total == 2
    assert trend.truncated is True
    assert [item.observation_identifier for item in trend.items] == ["NSCLC-CN-2024"]
    assert trend.anchor_observation_id == first_observation.id
    assert incompatible_observation.id not in {item.id for item in trend.items}

    missing = service.epidemiology_trend(
        "missing-disease",
        None,
        None,
        None,
        None,
        None,
        None,
        100,
    )
    assert missing is None


def test_epidemiology_search_sorts_full_result_set_by_disease_and_value(
    session: Session,
    tenant: Tenant,
) -> None:
    zeta = _entity(session, tenant, EntityType.DISEASE, "Zeta disease")
    alpha = _entity(session, tenant, EntityType.DISEASE, "Alpha disease")
    zeta_observation = _observation(
        session,
        tenant,
        zeta,
        identifier="ZETA-2025",
        measure="patient_count",
        value="10",
        year=2025,
    )
    alpha_observation = _observation(
        session,
        tenant,
        alpha,
        identifier="ALPHA-2025",
        measure="patient_count",
        value="20",
        year=2025,
    )
    session.commit()

    service = IntelligenceService(session, tenant.id)
    by_disease = service.search_epidemiology_observations(
        None, None, None, None, None, None, None, None, None, 1, 0, sort_by="disease", sort_direction="asc"
    )
    by_value = service.search_epidemiology_observations(
        None, None, None, None, None, None, None, None, None, 1, 0, sort_by="value", sort_direction="desc"
    )

    assert by_disease.items[0].id == alpha_observation.id
    assert by_value.items[0].id == alpha_observation.id
    assert by_value.items[0].id != zeta_observation.id
    assert by_value.sort_by == "value"
    assert by_value.sort_direction == "desc"
    multi_sorted = service.search_epidemiology_observations(
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        2,
        0,
        sort=(SortClause(field="measure", direction="asc"), SortClause(field="value", direction="desc")),
    )
    assert [item.id for item in multi_sorted.items] == [alpha_observation.id, zeta_observation.id]
    assert [criterion.model_dump() for criterion in multi_sorted.sort] == [
        {"field": "measure", "direction": "asc"},
        {"field": "value", "direction": "desc"},
    ]


def test_epidemiology_landscape_aggregates_full_hit_set(session: Session, tenant: Tenant) -> None:
    """Landscape buckets come from the complete filtered set, not the returned page."""

    disease = _entity(session, tenant, EntityType.DISEASE, "NSCLC-L")
    _observation(session, tenant, disease, identifier="EPI-L1", measure="incidence", value="100", year=2025)
    _observation(
        session, tenant, disease, identifier="EPI-L2", measure="incidence", value="200", year=2025, geography="US"
    )
    _observation(session, tenant, disease, identifier="EPI-L3", measure="prevalence", value="300", year=2024)
    session.commit()

    result = IntelligenceService(session, tenant.id).search_epidemiology_observations(
        None, None, None, None, None, None, None, None, None, 1, 0
    )

    assert len(result.items) == 1
    assert result.landscape.total_observations == 3
    assert {(b.key, b.count) for b in result.landscape.measure} == {("incidence", 2), ("prevalence", 1)}
    assert {(b.key, b.count) for b in result.landscape.geography} == {("China", 2), ("US", 1)}

    filtered = IntelligenceService(session, tenant.id).search_epidemiology_observations(
        None, "prevalence", None, None, None, None, None, None, None, 25, 0
    )
    assert filtered.landscape.total_observations == 1
    assert [b.key for b in filtered.landscape.measure] == ["prevalence"]
