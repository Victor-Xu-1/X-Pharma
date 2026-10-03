from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import and_, func, literal, or_, select, true
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import (
    _applied_filters,
    _landscape_scalar_buckets,
    _linked_entity_facets,
    _scalar_facet_counts,
)
from pharma_intel.intelligence.scope import _published_optional_entity
from pharma_intel.intelligence.vocabulary import _ordered_sort_expressions, _sort_criteria_read
from pharma_intel.models import (
    Entity,
    EntityType,
    EpidemiologyObservation,
    PatientPopulation,
    PatientPopulationEntityLink,
    ReviewStatus,
)
from pharma_intel.schemas import (
    EPIDEMIOLOGY_SORT_FIELDS,
    EpidemiologyLandscapeBucketRead,
    EpidemiologyLandscapeRead,
    EpidemiologyLinkedEntityRead,
    EpidemiologyObservationRead,
    EpidemiologyObservationSearchItemRead,
    EpidemiologyObservationSearchResult,
    EpidemiologySavedSearchQuery,
    EpidemiologySortField,
    EpidemiologyTrendResult,
    PatientPopulationOptionRead,
    PatientPopulationRead,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def search_epidemiology_observations(
    context: QueryContext,
    query: str | None,
    measure: str | None,
    geography: str | None,
    unit: str | None,
    population_scope: str | None,
    age_group: str | None,
    sex: str | None,
    period_start_from: datetime | None,
    period_end_to: datetime | None,
    limit: int,
    offset: int,
    *,
    disease_entity_id: str | None = None,
    patient_population_id: str | None = None,
    sort_by: EpidemiologySortField = "period_end",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[EpidemiologySortField]] | None = None,
) -> EpidemiologyObservationSearchResult:
    effective_sort = validate_sort_clauses(
        sort,
        EPIDEMIOLOGY_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    filters = _epidemiology_filters(
        context,
        disease_entity_id,
        patient_population_id,
        query,
        measure,
        geography,
        unit,
        population_scope,
        age_group,
        sex,
        period_start_from,
        period_end_to,
    )
    items = _epidemiology_search_items(
        context,
        filters,
        limit,
        offset,
        sort=effective_sort,
    )
    facet_source = (
        select(
            EpidemiologyObservation.id.label("observation_id"),
            EpidemiologyObservation.disease_entity_id.label("disease_entity_id"),
            EpidemiologyObservation.patient_population_id.label("patient_population_id"),
            EpidemiologyObservation.publisher_entity_id.label("publisher_entity_id"),
            EpidemiologyObservation.measure.label("measure"),
            EpidemiologyObservation.geography.label("geography"),
            EpidemiologyObservation.unit.label("unit"),
            EpidemiologyObservation.population_scope.label("population_scope"),
            EpidemiologyObservation.age_group.label("age_group"),
            EpidemiologyObservation.sex.label("sex"),
        )
        .where(*filters)
        .subquery()
    )
    total = context.session.scalar(select(func.count()).select_from(facet_source)) or 0
    facets = {
        name: _scalar_facet_counts(context, facet_source, name)
        for name in ("measure", "geography", "unit", "population_scope", "age_group", "sex")
    }
    facets["disease"] = _linked_entity_facets(context, facet_source, "disease_entity_id", "observation_id")
    facets["publisher"] = _linked_entity_facets(context, facet_source, "publisher_entity_id", "observation_id")
    landscape = EpidemiologyLandscapeRead(
        total_observations=total,
        measure=_landscape_scalar_buckets(context, facet_source, "measure", total, EpidemiologyLandscapeBucketRead),
        geography=_landscape_scalar_buckets(context, facet_source, "geography", total, EpidemiologyLandscapeBucketRead),
        population_scope=_landscape_scalar_buckets(
            context, facet_source, "population_scope", total, EpidemiologyLandscapeBucketRead
        ),
    )
    population_facet_source = (
        select(
            EpidemiologyObservation.id.label("observation_id"),
            EpidemiologyObservation.patient_population_id.label("patient_population_id"),
        )
        .where(
            *_epidemiology_filters(
                context,
                disease_entity_id,
                None,
                query,
                measure,
                geography,
                unit,
                population_scope,
                age_group,
                sex,
                period_start_from,
                period_end_to,
            )
        )
        .subquery()
    )
    population_counts = context.session.execute(
        select(
            PatientPopulation.id,
            PatientPopulation.name,
            func.count(func.distinct(population_facet_source.c.observation_id)),
        )
        .select_from(population_facet_source)
        .join(
            PatientPopulation,
            and_(
                PatientPopulation.tenant_id == context.tenant_id,
                PatientPopulation.id == population_facet_source.c.patient_population_id,
                PatientPopulation.review_status == ReviewStatus.VERIFIED,
            ),
        )
        .group_by(PatientPopulation.id, PatientPopulation.name)
        .order_by(
            func.count(func.distinct(population_facet_source.c.observation_id)).desc(),
            PatientPopulation.name,
        )
    ).all()
    return EpidemiologyObservationSearchResult(
        query_schema_version="pharma.epidemiology.search.v3",
        applied_filters=_applied_filters(
            ("disease_entity_id", "eq", disease_entity_id),
            ("patient_population_id", "eq", patient_population_id),
            ("q", "contains", query.strip() if query else None),
            ("measure", "eq", measure),
            ("geography", "eq", geography),
            ("unit", "eq", unit),
            ("population_scope", "eq", population_scope),
            ("age_group", "eq", age_group),
            ("sex", "eq", sex),
            ("period_start_from", "gte", period_start_from.isoformat() if period_start_from else None),
            ("period_end_to", "lte", period_end_to.isoformat() if period_end_to else None),
        ),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_criteria_read(effective_sort),
        facets=facets,
        landscape=landscape,
        patient_populations=[
            PatientPopulationOptionRead(id=population_id, name=name, count=count)
            for population_id, name, count in population_counts
        ],
        as_of=datetime.now(UTC),
        warnings=["未观察到流行病学估计不代表患者不存在；结果受地域、统计口径、模型方法、来源时效和数据授权限制。"],
    )


def epidemiology_search_items(
    context: QueryContext,
    disease_entity_id: str | None,
    query: str | None,
    measure: str | None,
    geography: str | None,
    unit: str | None,
    population_scope: str | None,
    age_group: str | None,
    sex: str | None,
    period_start_from: datetime | None,
    period_end_to: datetime | None,
    limit: int,
    offset: int = 0,
    *,
    patient_population_id: str | None = None,
    sort_by: EpidemiologySortField = "period_end",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[EpidemiologySortField]] | None = None,
) -> list[EpidemiologyObservationSearchItemRead]:
    filters = _epidemiology_filters(
        context,
        disease_entity_id,
        patient_population_id,
        query,
        measure,
        geography,
        unit,
        population_scope,
        age_group,
        sex,
        period_start_from,
        period_end_to,
    )
    return _epidemiology_search_items(
        context,
        filters,
        limit,
        offset,
        sort=validate_sort_clauses(
            sort,
            EPIDEMIOLOGY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        ),
    )


def epidemiology_saved_search_matches_entity(
    context: QueryContext,
    entity_id: str,
    query: EpidemiologySavedSearchQuery,
) -> bool:
    def start(value: Any) -> datetime | None:
        return datetime.combine(value, time.min, tzinfo=UTC) if value else None

    def end(value: Any) -> datetime | None:
        return datetime.combine(value, time.max, tzinfo=UTC) if value else None

    filters = _epidemiology_filters(
        context,
        query.disease_entity_id,
        query.patient_population_id,
        query.q,
        query.measure,
        query.geography,
        query.unit,
        query.population_scope,
        query.age_group,
        query.sex,
        start(query.period_start_from),
        end(query.period_end_to),
    )
    related_populations = select(PatientPopulationEntityLink.patient_population_id).where(
        PatientPopulationEntityLink.tenant_id == context.tenant_id,
        PatientPopulationEntityLink.entity_id == entity_id,
    )
    filters.append(
        or_(
            EpidemiologyObservation.disease_entity_id == entity_id,
            EpidemiologyObservation.publisher_entity_id == entity_id,
            EpidemiologyObservation.patient_population_id.in_(related_populations),
        )
    )
    statement = select(EpidemiologyObservation.id).where(*filters)
    return context.session.scalar(statement.with_only_columns(literal(True)).limit(1)) is True


def epidemiology_trend(
    context: QueryContext,
    disease_entity_id: str,
    measure: str | None,
    geography: str | None,
    unit: str | None,
    population_scope: str | None,
    age_group: str | None,
    sex: str | None,
    limit: int,
    *,
    patient_population_id: str | None = None,
    anchor_observation_id: str | None = None,
) -> EpidemiologyTrendResult | None:
    disease = context.session.scalar(
        select(Entity).where(
            Entity.tenant_id == context.tenant_id,
            Entity.id == disease_entity_id,
            Entity.entity_type == EntityType.DISEASE,
        )
    )
    if disease is None:
        return None
    anchor = None
    if anchor_observation_id:
        anchor = context.session.scalar(
            select(EpidemiologyObservation).where(
                EpidemiologyObservation.tenant_id == context.tenant_id,
                EpidemiologyObservation.id == anchor_observation_id,
                EpidemiologyObservation.disease_entity_id == disease_entity_id,
            )
        )
        if anchor is None:
            return None
        filters = _epidemiology_filters(
            context,
            disease_entity_id,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
        for column, value in (
            (EpidemiologyObservation.patient_population_id, anchor.patient_population_id),
            (EpidemiologyObservation.measure, anchor.measure),
            (EpidemiologyObservation.geography, anchor.geography),
            (EpidemiologyObservation.unit, anchor.unit),
            (EpidemiologyObservation.population_scope, anchor.population_scope),
            (EpidemiologyObservation.age_group, anchor.age_group),
            (EpidemiologyObservation.sex, anchor.sex),
            (EpidemiologyObservation.publisher_entity_id, anchor.publisher_entity_id),
            (EpidemiologyObservation.methodology, anchor.methodology),
        ):
            filters.append(column.is_(None) if value is None else column == value)
    else:
        filters = _epidemiology_filters(
            context,
            disease_entity_id,
            patient_population_id,
            None,
            measure,
            geography,
            unit,
            population_scope,
            age_group,
            sex,
            None,
            None,
        )
    total = int(context.session.scalar(select(func.count()).select_from(EpidemiologyObservation).where(*filters)) or 0)
    items = _epidemiology_search_items(
        context,
        filters,
        limit,
        0,
        sort_by="period_end",
        sort_direction="asc",
    )
    return EpidemiologyTrendResult(
        disease=EpidemiologyLinkedEntityRead(
            id=disease.id,
            name=disease.name,
            entity_type=disease.entity_type,
        ),
        anchor_observation_id=anchor.id if anchor else None,
        items=items,
        total=total,
        truncated=total > len(items),
        as_of=datetime.now(UTC),
        warnings=["趋势仅比较相同指标、单位和人群口径；不同来源或方法学估计不可直接合并。"],
    )


def _epidemiology_search_items(
    context: QueryContext,
    filters: list[ColumnElement[bool]],
    limit: int,
    offset: int,
    *,
    sort_by: EpidemiologySortField = "period_end",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[EpidemiologySortField]] | None = None,
) -> list[EpidemiologyObservationSearchItemRead]:
    effective_sort = validate_sort_clauses(
        sort,
        EPIDEMIOLOGY_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    disease_name = (
        select(func.lower(Entity.name))
        .where(
            Entity.tenant_id == context.tenant_id,
            Entity.id == EpidemiologyObservation.disease_entity_id,
        )
        .correlate(EpidemiologyObservation)
        .scalar_subquery()
    )
    publisher_name = (
        select(func.lower(Entity.name))
        .where(
            Entity.tenant_id == context.tenant_id,
            Entity.id == EpidemiologyObservation.publisher_entity_id,
        )
        .correlate(EpidemiologyObservation)
        .scalar_subquery()
    )
    sort_expressions: dict[EpidemiologySortField, Any] = {
        "period_end": EpidemiologyObservation.period_end,
        "period_start": EpidemiologyObservation.period_start,
        "disease": disease_name,
        "measure": func.lower(EpidemiologyObservation.measure),
        "value": EpidemiologyObservation.value,
        "geography": func.lower(EpidemiologyObservation.geography),
        "unit": func.lower(EpidemiologyObservation.unit),
        "publisher": publisher_name,
        "sample_size": EpidemiologyObservation.sample_size,
    }
    ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
    rows = context.session.scalars(
        select(EpidemiologyObservation)
        .where(*filters)
        .order_by(*ordered_sort, EpidemiologyObservation.observation_identifier, EpidemiologyObservation.id)
        .limit(limit)
        .offset(offset)
    ).all()
    population_ids = {row.patient_population_id for row in rows if row.patient_population_id}
    populations = (
        context.session.scalars(
            select(PatientPopulation).where(
                PatientPopulation.tenant_id == context.tenant_id,
                PatientPopulation.id.in_(population_ids),
                PatientPopulation.review_status == ReviewStatus.VERIFIED,
            )
        ).all()
        if population_ids
        else []
    )
    population_links = (
        context.session.scalars(
            select(PatientPopulationEntityLink).where(
                PatientPopulationEntityLink.tenant_id == context.tenant_id,
                PatientPopulationEntityLink.patient_population_id.in_(population_ids),
            )
        ).all()
        if population_ids
        else []
    )
    entity_ids = {
        entity_id for row in rows for entity_id in (row.disease_entity_id, row.publisher_entity_id) if entity_id
    }
    entity_ids.update(link.entity_id for link in population_links)
    entities = (
        context.session.scalars(
            select(Entity)
            .where(Entity.tenant_id == context.tenant_id, Entity.id.in_(entity_ids))
            .order_by(Entity.entity_type, Entity.name, Entity.id)
        ).all()
        if entity_ids
        else []
    )
    linked_by_id = {
        entity.id: EpidemiologyLinkedEntityRead(
            id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
        )
        for entity in entities
    }
    population_reads: dict[str, PatientPopulationRead] = {}
    for population in populations:
        links = [link for link in population_links if link.patient_population_id == population.id]
        population_reads[population.id] = PatientPopulationRead(
            id=population.id,
            population_key=population.population_key,
            name=population.name,
            description=population.description,
            attributes=population.attributes,
            disease_entities=[
                linked_by_id[link.entity_id]
                for link in links
                if link.relationship == "disease"
                and link.entity_id in linked_by_id
                and linked_by_id[link.entity_id].entity_type == EntityType.DISEASE
            ],
            target_entities=[
                linked_by_id[link.entity_id]
                for link in links
                if link.relationship == "target"
                and link.entity_id in linked_by_id
                and linked_by_id[link.entity_id].entity_type == EntityType.TARGET
            ],
        )
    return [
        EpidemiologyObservationSearchItemRead(
            **EpidemiologyObservationRead.model_validate(row).model_dump(),
            disease_entity=linked_by_id[row.disease_entity_id],
            publisher_entity=linked_by_id.get(row.publisher_entity_id or ""),
            patient_population=population_reads.get(row.patient_population_id or ""),
        )
        for row in rows
    ]


def _epidemiology_filters(
    context: QueryContext,
    disease_entity_id: str | None,
    patient_population_id: str | None,
    query: str | None,
    measure: str | None,
    geography: str | None,
    unit: str | None,
    population_scope: str | None,
    age_group: str | None,
    sex: str | None,
    period_start_from: datetime | None,
    period_end_to: datetime | None,
) -> list[ColumnElement[bool]]:
    disease_guard = aliased(Entity)
    population_guard = aliased(PatientPopulation)
    filters = [
        EpidemiologyObservation.tenant_id == context.tenant_id,
        select(disease_guard.id)
        .where(
            disease_guard.tenant_id == context.tenant_id,
            disease_guard.id == EpidemiologyObservation.disease_entity_id,
            disease_guard.entity_type == EntityType.DISEASE,
            disease_guard.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
        )
        .exists(),
        or_(
            EpidemiologyObservation.patient_population_id.is_(None),
            select(population_guard.id)
            .where(
                population_guard.tenant_id == context.tenant_id,
                population_guard.id == EpidemiologyObservation.patient_population_id,
                population_guard.review_status == ReviewStatus.VERIFIED,
            )
            .exists(),
        ),
    ]
    if not context.include_unpublished:
        filters.append(_published_optional_entity(context, EpidemiologyObservation.publisher_entity_id))
    if disease_entity_id:
        filters.append(EpidemiologyObservation.disease_entity_id == disease_entity_id)
    if patient_population_id:
        filters.append(EpidemiologyObservation.patient_population_id == patient_population_id)
    if measure:
        filters.append(EpidemiologyObservation.measure == measure)
    if geography:
        filters.append(EpidemiologyObservation.geography == geography)
    if unit:
        filters.append(EpidemiologyObservation.unit == unit)
    if population_scope:
        filters.append(EpidemiologyObservation.population_scope == population_scope)
    if age_group:
        filters.append(EpidemiologyObservation.age_group == age_group)
    if sex:
        filters.append(EpidemiologyObservation.sex == sex)
    if period_start_from:
        filters.append(EpidemiologyObservation.period_end >= period_start_from)
    if period_end_to:
        filters.append(EpidemiologyObservation.period_start <= period_end_to)
    if query:
        pattern = query.strip()
        disease = aliased(Entity)
        publisher = aliased(Entity)
        patient_population = aliased(PatientPopulation)
        filters.append(
            or_(
                EpidemiologyObservation.observation_identifier.icontains(pattern, autoescape=True),
                EpidemiologyObservation.measure.icontains(pattern, autoescape=True),
                EpidemiologyObservation.geography.icontains(pattern, autoescape=True),
                EpidemiologyObservation.population_scope.icontains(pattern, autoescape=True),
                EpidemiologyObservation.methodology.icontains(pattern, autoescape=True),
                select(disease.id)
                .where(
                    disease.tenant_id == context.tenant_id,
                    disease.id == EpidemiologyObservation.disease_entity_id,
                    disease.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                    disease.name.icontains(pattern, autoescape=True),
                )
                .exists(),
                select(publisher.id)
                .where(
                    publisher.tenant_id == context.tenant_id,
                    publisher.id == EpidemiologyObservation.publisher_entity_id,
                    publisher.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                    publisher.name.icontains(pattern, autoescape=True),
                )
                .exists(),
                select(patient_population.id)
                .where(
                    patient_population.tenant_id == context.tenant_id,
                    patient_population.id == EpidemiologyObservation.patient_population_id,
                    patient_population.review_status == ReviewStatus.VERIFIED,
                    or_(
                        patient_population.name.icontains(pattern, autoescape=True),
                        patient_population.population_key.icontains(pattern, autoescape=True),
                    ),
                )
                .exists(),
            )
        )
    return filters
