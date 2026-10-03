from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import String, and_, cast, func, literal, or_, select, true
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import _applied_filters, _json_array_facets, _scalar_facet_counts
from pharma_intel.intelligence.scope import _published_entity_exists
from pharma_intel.intelligence.vocabulary import (
    _ordered_sort_expressions,
    _saved_date_end,
    _saved_date_start,
    _sort_criteria_read,
)
from pharma_intel.models import Entity, PatentFamily, Relationship, ReviewStatus
from pharma_intel.schemas import (
    PATENT_SORT_FIELDS,
    PatentFamilyLinkedEntityRead,
    PatentFamilyRead,
    PatentFamilySearchItemRead,
    PatentFamilySearchResult,
    PatentLandscapeBucketRead,
    PatentLandscapeRead,
    PatentSavedSearchQuery,
    PatentSortField,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def patents(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    limit: int,
    offset: int = 0,
    applicant: str | None = None,
    legal_status: str | None = None,
) -> list[PatentFamilyRead]:
    filters = _patent_filters(context, entity_id, query, applicant=applicant, legal_status=legal_status)
    rows = context.session.scalars(
        select(PatentFamily)
        .where(*filters)
        .order_by(PatentFamily.priority_date.desc().nullslast(), PatentFamily.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [PatentFamilyRead.model_validate(row) for row in rows]


def search_patent_families(
    context: QueryContext,
    query: str | None,
    applicant: str | None,
    legal_status: str | None,
    limit: int,
    offset: int,
    *,
    entity_id: str | None = None,
    priority_from: datetime | None = None,
    priority_to: datetime | None = None,
    expiration_from: datetime | None = None,
    expiration_to: datetime | None = None,
    sort_by: PatentSortField = "priority_date",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[PatentSortField]] | None = None,
) -> PatentFamilySearchResult:
    effective_sort = validate_sort_clauses(
        sort,
        PATENT_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    filters = _patent_filters(
        context,
        entity_id,
        query,
        applicant=applicant,
        legal_status=legal_status,
        priority_from=priority_from,
        priority_to=priority_to,
        expiration_from=expiration_from,
        expiration_to=expiration_to,
    )
    items = _patent_search_items(
        context,
        filters,
        limit,
        offset,
        sort=effective_sort,
    )

    facet_source = (
        select(
            PatentFamily.id.label("patent_id"),
            PatentFamily.legal_status.label("legal_status"),
            PatentFamily.applicants.label("applicants"),
            PatentFamily.priority_date.label("priority_date"),
        )
        .where(*filters)
        .subquery()
    )
    total = context.session.scalar(select(func.count()).select_from(facet_source)) or 0
    facets = {
        "legal_status": _scalar_facet_counts(context, facet_source, "legal_status"),
        "applicant": _json_array_facets(context, facet_source, "applicants", "patent_id"),
    }
    landscape = _patent_landscape(context, facet_source, total, applicant_counts=facets["applicant"])
    return PatentFamilySearchResult(
        query_schema_version="pharma.patent.search.v2",
        applied_filters=_applied_filters(
            ("entity_id", "eq", entity_id),
            ("q", "contains", query.strip() if query else None),
            ("applicant", "eq", applicant),
            ("legal_status", "eq", legal_status),
            ("priority_from", "gte", priority_from.isoformat() if priority_from else None),
            ("priority_to", "lte", priority_to.isoformat() if priority_to else None),
            ("expiration_from", "gte", expiration_from.isoformat() if expiration_from else None),
            ("expiration_to", "lte", expiration_to.isoformat() if expiration_to else None),
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
        as_of=datetime.now(UTC),
        warnings=["未观察到专利族不代表不存在；结果受司法辖区、数据授权、法律状态时效和治理状态限制。"],
    )


def _patent_landscape(
    context: QueryContext,
    source: Any,
    total: int,
    *,
    applicant_counts: dict[str, int],
    top_limit: int = 8,
) -> PatentLandscapeRead:
    """Aggregate the complete filtered patent set for the same-query statistics view."""

    def bucket(key: str, count: int) -> PatentLandscapeBucketRead:
        return PatentLandscapeBucketRead(
            key=key,
            label="未披露" if key == "__missing__" else key,
            count=count,
            share=(count / total) if total else 0.0,
        )

    status_column = func.coalesce(source.c.legal_status, "__missing__")
    status_rows = context.session.execute(
        select(status_column.label("status"), func.count())
        .select_from(source)
        .group_by("status")
        .order_by(func.count().desc(), status_column)
    ).all()
    legal_status = [bucket(str(status), int(count)) for status, count in status_rows]

    top_applicants = [
        bucket(name, count)
        for name, count in sorted(applicant_counts.items(), key=lambda item: (-item[1], item[0]))[:top_limit]
    ]

    year_column = func.extract("year", source.c.priority_date)
    year_rows = context.session.execute(
        select(year_column.label("priority_year"), func.count()).select_from(source).group_by("priority_year")
    ).all()
    priority_year = sorted(
        (bucket("__missing__" if year is None else str(int(year)), int(count)) for year, count in year_rows),
        key=lambda item: (item.key == "__missing__", item.key),
        reverse=True,
    )

    return PatentLandscapeRead(
        total_families=total,
        legal_status=legal_status,
        top_applicants=top_applicants,
        priority_year=priority_year,
    )


def patent_saved_search_matches_entity(
    context: QueryContext,
    entity_id: str,
    query: PatentSavedSearchQuery,
) -> bool:
    filters = _patent_filters(
        context,
        entity_id,
        query.q,
        applicant=query.applicant,
        legal_status=query.legal_status,
        priority_from=_saved_date_start(query.priority_from),
        priority_to=_saved_date_end(query.priority_to),
        expiration_from=_saved_date_start(query.expiration_from),
        expiration_to=_saved_date_end(query.expiration_to),
    )
    statement = select(PatentFamily.id).where(*filters).limit(1)
    return context.session.scalar(statement.with_only_columns(literal(True))) is True


def patent_search_items(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    applicant: str | None,
    legal_status: str | None,
    limit: int,
    offset: int = 0,
    *,
    sort_by: PatentSortField = "priority_date",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[PatentSortField]] | None = None,
) -> list[PatentFamilySearchItemRead]:
    filters = _patent_filters(context, entity_id, query, applicant=applicant, legal_status=legal_status)
    return _patent_search_items(
        context,
        filters,
        limit,
        offset,
        sort=validate_sort_clauses(
            sort,
            PATENT_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        ),
    )


def patent_family_detail(context: QueryContext, family_id: str) -> PatentFamilySearchItemRead | None:
    items = _patent_search_items(
        context,
        [
            PatentFamily.tenant_id == context.tenant_id,
            PatentFamily.id == family_id,
            _published_entity_exists(context, PatentFamily.entity_id),
        ],
        1,
        0,
    )
    return items[0] if items else None


def _patent_search_items(
    context: QueryContext,
    filters: list[ColumnElement[bool]],
    limit: int,
    offset: int,
    *,
    sort_by: PatentSortField = "priority_date",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[PatentSortField]] | None = None,
) -> list[PatentFamilySearchItemRead]:
    effective_sort = validate_sort_clauses(
        sort,
        PATENT_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    sort_expressions: dict[PatentSortField, Any] = {
        "priority_date": PatentFamily.priority_date,
        "family_identifier": func.lower(PatentFamily.family_identifier),
        "legal_status": func.lower(PatentFamily.legal_status),
        "expiration_date": PatentFamily.expiration_date,
    }
    ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
    rows = context.session.scalars(
        select(PatentFamily)
        .where(*filters)
        .order_by(*ordered_sort, PatentFamily.family_identifier, PatentFamily.id)
        .limit(limit)
        .offset(offset)
    ).all()
    linked_by_patent: dict[str, dict[str, PatentFamilyLinkedEntityRead]] = {row.entity_id: {} for row in rows}
    patent_entity_ids = list(linked_by_patent)
    if patent_entity_ids:
        linked_rows = context.session.execute(
            select(Relationship.subject_id, Entity)
            .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == Relationship.object_id))
            .where(
                Relationship.tenant_id == context.tenant_id,
                Relationship.predicate == "patent_links_entity",
                Relationship.subject_id.in_(patent_entity_ids),
            )
            .order_by(Relationship.subject_id, Entity.entity_type, Entity.name, Entity.id)
        ).all()
        for patent_entity_id, entity in linked_rows:
            linked_by_patent[patent_entity_id][entity.id] = PatentFamilyLinkedEntityRead(
                id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
            )
        legacy_ids = {entity_id for row in rows for entity_id in row.linked_entity_ids}
        if legacy_ids:
            legacy_entities = context.session.scalars(
                select(Entity)
                .where(Entity.tenant_id == context.tenant_id, Entity.id.in_(legacy_ids))
                .order_by(Entity.entity_type, Entity.name, Entity.id)
            ).all()
            entity_by_id = {entity.id: entity for entity in legacy_entities}
            for row in rows:
                for entity_id in row.linked_entity_ids:
                    if entity := entity_by_id.get(entity_id):
                        linked_by_patent[row.entity_id].setdefault(
                            entity.id,
                            PatentFamilyLinkedEntityRead(
                                id=entity.id,
                                name=entity.name,
                                entity_type=entity.entity_type,
                            ),
                        )
    return [
        PatentFamilySearchItemRead(
            **PatentFamilyRead.model_validate(row).model_dump(),
            linked_entities=list(linked_by_patent[row.entity_id].values()),
        )
        for row in rows
    ]


def _patent_filters(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    *,
    applicant: str | None = None,
    legal_status: str | None = None,
    priority_from: datetime | None = None,
    priority_to: datetime | None = None,
    expiration_from: datetime | None = None,
    expiration_to: datetime | None = None,
) -> list[ColumnElement[bool]]:
    filters = [
        PatentFamily.tenant_id == context.tenant_id,
        _published_entity_exists(context, PatentFamily.entity_id),
    ]
    if entity_id:
        linked_patent_ids = select(Relationship.subject_id).where(
            Relationship.tenant_id == context.tenant_id,
            Relationship.predicate == "patent_links_entity",
            Relationship.object_id == entity_id,
        )
        filters.append(
            or_(
                PatentFamily.entity_id == entity_id,
                PatentFamily.entity_id.in_(linked_patent_ids),
                cast(PatentFamily.linked_entity_ids, String).contains(f'"{entity_id}"', autoescape=True),
            )
        )
    if query and (normalized_query := query.strip().casefold()):
        linked_entity_match = (
            select(Relationship.id)
            .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == Relationship.object_id))
            .where(
                Relationship.tenant_id == context.tenant_id,
                Relationship.predicate == "patent_links_entity",
                Relationship.subject_id == PatentFamily.entity_id,
                Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                func.lower(Entity.name).contains(normalized_query, autoescape=True),
            )
            .exists()
        )
        filters.append(
            or_(
                func.lower(PatentFamily.title).contains(normalized_query, autoescape=True),
                func.lower(PatentFamily.family_identifier).contains(normalized_query, autoescape=True),
                func.lower(cast(PatentFamily.applicants, String)).contains(normalized_query, autoescape=True),
                func.lower(cast(PatentFamily.inventors, String)).contains(normalized_query, autoescape=True),
                func.lower(cast(PatentFamily.publications, String)).contains(normalized_query, autoescape=True),
                linked_entity_match,
            )
        )
    if applicant:
        filters.append(cast(PatentFamily.applicants, String).contains(f'"{applicant}"', autoescape=True))
    if legal_status:
        filters.append(PatentFamily.legal_status == legal_status)
    if priority_from:
        filters.append(PatentFamily.priority_date >= priority_from)
    if priority_to:
        filters.append(PatentFamily.priority_date <= priority_to)
    if expiration_from:
        filters.append(PatentFamily.expiration_date >= expiration_from)
    if expiration_to:
        filters.append(PatentFamily.expiration_date <= expiration_to)
    return filters
