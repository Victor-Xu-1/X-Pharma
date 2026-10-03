from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select

from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.governance.temporal_merge import (
    _optional_decimal,
    _validated_datetime,
)
from pharma_intel.models import (
    Entity,
    EpidemiologyObservation,
    NewsEvent,
    PatientPopulation,
    PatientPopulationEntityLink,
    RegulatoryEvent,
    ReviewStatus,
    StagedFact,
)


def materialize_regulatory(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    subject = context._entity(cast(dict[str, Any], payload["subject"]), staged.source_document_id)
    indication = context._optional_entity(payload.get("indication"), staged.source_document_id)
    organization = context._optional_entity(payload.get("organization"), staged.source_document_id)
    agency = str(payload["agency"])
    event_identifier = str(payload["event_identifier"])
    event = context.session.scalar(
        select(RegulatoryEvent).where(
            RegulatoryEvent.tenant_id == context.tenant_id,
            RegulatoryEvent.agency == agency,
            RegulatoryEvent.event_identifier == event_identifier,
        )
    )
    if event is None:
        event = RegulatoryEvent(
            tenant_id=context.tenant_id,
            subject_entity_id=subject.id,
            agency=agency,
            jurisdiction=str(payload["jurisdiction"]),
            event_identifier=event_identifier,
            event_type=str(payload["event_type"]),
            title=str(payload["title"]),
        )
        context.session.add(event)
    elif event.subject_entity_id != subject.id:
        raise GovernanceError("Regulatory event identifier is already assigned to another normalized entity")
    event.jurisdiction = str(payload["jurisdiction"])
    event.application_number = cast(str | None, payload.get("application_number"))
    event.event_type = str(payload["event_type"])
    event.status = cast(str | None, payload.get("status"))
    event.title = str(payload["title"])
    event.decision_date = _validated_datetime(payload.get("decision_date"))
    event.designation_type = cast(str | None, payload.get("designation_type"))
    event.label_change_type = cast(str | None, payload.get("label_change_type"))
    event.label_version = cast(str | None, payload.get("label_version"))
    event.label_effective_at = _validated_datetime(payload.get("label_effective_at"))
    event.approved_population = cast(str | None, payload.get("approved_population"))
    event.line_of_therapy = cast(str | None, payload.get("line_of_therapy"))
    event.biomarker = cast(str | None, payload.get("biomarker"))
    event.route_of_administration = cast(str | None, payload.get("route_of_administration"))
    event.dosage_form = cast(str | None, payload.get("dosage_form"))
    event.has_boxed_warning = cast(bool | None, payload.get("has_boxed_warning"))
    event.safety_signal_type = cast(str | None, payload.get("safety_signal_type"))
    event.safety_term = cast(str | None, payload.get("safety_term"))
    event.safety_severity = cast(str | None, payload.get("safety_severity"))
    event.safety_status = cast(str | None, payload.get("safety_status"))
    event.safety_identified_at = _validated_datetime(payload.get("safety_identified_at"))
    event.safety_confirmed_at = _validated_datetime(payload.get("safety_confirmed_at"))
    event.safety_resolved_at = _validated_datetime(payload.get("safety_resolved_at"))
    event.affected_population = cast(str | None, payload.get("affected_population"))
    event.risk_actions = [str(action) for action in payload.get("risk_actions") or []]
    event.source_updated_at = _validated_datetime(payload.get("source_updated_at"))
    event.indication_entity_id = indication.id if indication else None
    event.organization_entity_id = organization.id if organization else None
    event.details = dict(payload.get("details") or {})
    event.source_document_id = staged.source_document_id
    if indication:
        context._relationship(subject, "regulatory_indication", indication, staged)
    if organization:
        context._relationship(organization, "regulatory_sponsor", subject, staged)
    context.session.flush()
    return [_projection("regulatory_event", event.id)]


def materialize_epidemiology(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    disease = context._entity(cast(dict[str, Any], payload["disease"]), staged.source_document_id)
    publisher = context._optional_entity(payload.get("publisher"), staged.source_document_id)
    population: PatientPopulation | None = None
    population_payload = payload.get("patient_population")
    if isinstance(population_payload, dict):
        population_key = str(population_payload["population_key"])
        population = context.session.scalar(
            select(PatientPopulation).where(
                PatientPopulation.tenant_id == context.tenant_id,
                PatientPopulation.population_key == population_key,
            )
        )
        if population is None:
            population = PatientPopulation(
                tenant_id=context.tenant_id,
                population_key=population_key,
                name=str(population_payload["name"]),
            )
            context.session.add(population)
            context.session.flush()
        population.name = str(population_payload["name"])
        population.description = cast(str | None, population_payload.get("description"))
        population.attributes = dict(population_payload.get("attributes") or {})
        population.review_status = ReviewStatus.VERIFIED
        population.source_document_id = staged.source_document_id
        linked_entities: dict[tuple[str, str], Entity] = {(disease.id, "disease"): disease}
        for target_payload in cast(list[dict[str, Any]], population_payload.get("targets") or []):
            target = context._entity(target_payload, staged.source_document_id)
            linked_entities[(target.id, "target")] = target
        for (entity_id, relationship), entity in linked_entities.items():
            existing_link = context.session.scalar(
                select(PatientPopulationEntityLink).where(
                    PatientPopulationEntityLink.tenant_id == context.tenant_id,
                    PatientPopulationEntityLink.patient_population_id == population.id,
                    PatientPopulationEntityLink.entity_id == entity_id,
                    PatientPopulationEntityLink.relationship == relationship,
                )
            )
            if existing_link is None:
                context.session.add(
                    PatientPopulationEntityLink(
                        tenant_id=context.tenant_id,
                        patient_population_id=population.id,
                        entity_id=entity.id,
                        relationship=relationship,
                        source_document_id=staged.source_document_id,
                    )
                )
    observation_identifier = str(payload["observation_identifier"])
    observation = context.session.scalar(
        select(EpidemiologyObservation).where(
            EpidemiologyObservation.tenant_id == context.tenant_id,
            EpidemiologyObservation.observation_identifier == observation_identifier,
        )
    )
    if observation is None:
        observation = EpidemiologyObservation(
            tenant_id=context.tenant_id,
            observation_identifier=observation_identifier,
            disease_entity_id=disease.id,
            measure=str(payload["measure"]),
            value=Decimal(str(payload["value"])),
            unit=str(payload["unit"]),
            geography=str(payload["geography"]),
            population_scope=str(payload["population_scope"]),
        )
        context.session.add(observation)
    elif observation.disease_entity_id != disease.id:
        raise GovernanceError("Epidemiology observation identifier is already assigned to another disease")
    observation.measure = str(payload["measure"])
    observation.value = Decimal(str(payload["value"]))
    observation.lower_bound = _optional_decimal(payload.get("lower_bound"))
    observation.upper_bound = _optional_decimal(payload.get("upper_bound"))
    observation.unit = str(payload["unit"])
    observation.geography = str(payload["geography"])
    observation.population_scope = str(payload["population_scope"])
    if population is not None:
        observation.patient_population_id = population.id
    observation.age_group = cast(str | None, payload.get("age_group"))
    observation.sex = cast(str | None, payload.get("sex"))
    observation.period_start = _validated_datetime(payload.get("period_start"))
    observation.period_end = _validated_datetime(payload.get("period_end"))
    observation.sample_size = _optional_decimal(payload.get("sample_size"))
    observation.methodology = cast(str | None, payload.get("methodology"))
    observation.publisher_entity_id = publisher.id if publisher else None
    observation.source_document_id = staged.source_document_id
    if publisher:
        context._relationship(publisher, "epidemiology_publisher", disease, staged)
    context.session.flush()
    projections = [_projection("epidemiology_observation", observation.id)]
    if population is not None:
        projections.append(_projection("patient_population", population.id))
    return projections


def materialize_news(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    publisher = context._optional_entity(payload.get("publisher"), staged.source_document_id)
    related_entities = [
        context._entity(item, staged.source_document_id)
        for item in cast(list[dict[str, Any]], payload.get("related_entities") or [])
    ]
    event_identifier = str(payload["event_identifier"])
    event = context.session.scalar(
        select(NewsEvent).where(
            NewsEvent.tenant_id == context.tenant_id,
            NewsEvent.event_identifier == event_identifier,
        )
    )
    if event is None:
        event = NewsEvent(
            tenant_id=context.tenant_id,
            event_identifier=event_identifier,
            event_type=str(payload["event_type"]),
            title=str(payload["title"]),
        )
        context.session.add(event)
    event.event_type = str(payload["event_type"])
    event.title = str(payload["title"])
    event.summary = cast(str | None, payload.get("summary"))
    event.published_at = _validated_datetime(payload.get("published_at"))
    event.language = cast(str | None, payload.get("language"))
    event.publisher_entity_id = publisher.id if publisher else None
    event.related_entity_ids = [entity.id for entity in related_entities]
    event.canonical_url = str(payload["canonical_url"]) if payload.get("canonical_url") else None
    event.venue = cast(str | None, payload.get("venue"))
    event.details = dict(payload.get("details") or {})
    event.source_document_id = staged.source_document_id
    for related in related_entities:
        if publisher:
            context._relationship(publisher, "announced_about", related, staged)
    context.session.flush()
    return [_projection("news_event", event.id)]
